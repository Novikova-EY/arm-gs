"""Кэш для агрегаций с использованием Redis."""

import hashlib
import pickle
from functools import wraps
from datetime import datetime, timedelta
import redis
from flask import current_app

# Fallback in-memory кэш (если Redis недоступен)
_cache = {}
_cache_timeout = timedelta(minutes=30)  # Кэш на 30 минут

# Версия ключей кэша агрегаций.
# Инкрементируйте при изменении структуры строк/запросов агрегации, чтобы избежать
# использования старых закэшированных результатов с несовместимыми полями.
# v3: инвалидация после исправлений filter_by_db_version в get_regional_districts_*
# v4: MachinePower/PGUMachinePower — fallback на NULL (legacy данные без version_id)
# v5: территориальные справочники (РЭС, ОЭС) не фильтруются по версии — общие
AGGREGATION_CACHE_KEY_VERSION = 5

# Версия ключей кэша сортировки станций.
# Инкрементируйте при изменении логики сортировки station_list, чтобы не использовать
# устаревший порядок из Redis/in-memory кэша.
STATIONS_SORT_CACHE_KEY_VERSION = 1

# Отдельный Redis‑клиент для кэша (не тот, что используется Flask‑Session)
_redis_client = None


def get_redis_client():
    """
    Получает Redis‑клиент для кэша или None, если Redis недоступен.
    Использует отдельное соединение, чтобы не блокировать сохранение сессий.
    """
    global _redis_client

    # Если уже инициализировали и он не None — просто возвращаем
    if _redis_client is not None:
        return _redis_client

    try:
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(
            redis_url,
            socket_connect_timeout=5,  # можно дать больше времени, чем для сессий
            socket_timeout=10,
            decode_responses=False,
        )
        # Одна проверка на этапе инициализации
        client.ping()
        _redis_client = client
        return _redis_client
    except (redis.ConnectionError, redis.TimeoutError, Exception):
        # Если не удалось подключиться — работаем через in‑memory кэш
        _redis_client = None
        return None


def get_cache_key(start_year, end_year, station_ids, filters=None):
    """Генерирует ключ кэша на основе параметров запроса."""
    from app.common.services.database_version_filter import get_current_db_version_id
    
    # Сортируем station_ids для консистентности
    sorted_ids = tuple(sorted(station_ids))
    
    # Получаем текущую версию БД
    current_version = get_current_db_version_id()
    
    # Добавляем фильтры в ключ кэша
    if filters:
        # Берем только релевантные фильтры для агрегатов
        relevant_filters = {
            k: tuple(sorted(v)) if isinstance(v, list) else v
            for k, v in filters.items()
            if k in [
                "station_type_filter", "station_name_filter", "gen_company_filter",
                "tes_type_filter", "tes_machine_type_filter",
                "fuel_type_filter", "condition_type_filter",
                "machines_without_equipment_group",
                "date_commission_filter", "date_exploitation_filter",
                "date_decompressing_expected_filter", "date_modernization_expected_filter",
                "date_modernization_no_power_expected_filter", "relabing_outcome_filter",
            ] and v
        }
        filters_str = str(sorted(relevant_filters.items()))
    else:
        filters_str = ""
    
    # Добавляем версию БД в ключ кэша
    key_data = f"agg{AGGREGATION_CACHE_KEY_VERSION}_v{current_version or 'all'}_{start_year}_{end_year}_{sorted_ids}_{filters_str}"
    return hashlib.md5(key_data.encode()).hexdigest()


def cache_aggregation(func):
    """Декоратор для кэширования результатов агрегации."""
    @wraps(func)
    def wrapper(start_year, end_year, station_ids, filters=None):
        # Генерируем ключ кэша
        cache_key = get_cache_key(start_year, end_year, station_ids, filters)
        
        # Проверяем, есть ли данные в кэше и не устарели ли они
        if cache_key in _cache:
            cached_data, cached_time = _cache[cache_key]
            if datetime.now() - cached_time < _cache_timeout:
                print(f"[CACHE HIT] Используются кэшированные данные агрегации")
                return cached_data
            else:
                # Удаляем устаревшие данные
                del _cache[cache_key]
        
        # Вызываем оригинальную функцию
        result = func(start_year, end_year, station_ids, filters)
        
        # Сохраняем в кэш
        _cache[cache_key] = (result, datetime.now())
        print(f"[CACHE MISS] Данные агрегации закэшированы")
        
        return result
    
    return wrapper


def clear_aggregation_cache():
    """Очищает весь кэш агрегаций (Redis + memory fallback + LRU кэши)."""
    global _cache, _sorted_stations_cache, _page_positions_cache
    
    redis_client = get_redis_client()
    if redis_client:
        try:
            # ИСПРАВЛЕНО: Используем более широкий паттерн для очистки ВСЕХ версий кэша
            keys_to_delete = []
            for pattern in ['stations:sorted:*', 'stations:page:*']:
                cursor = 0
                while True:
                    cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
                    keys_to_delete.extend(keys)
                    if cursor == 0:
                        break
            
            # Удаляем ключи батчами по 100 для ускорения
            if keys_to_delete:
                batch_size = 100
                for i in range(0, len(keys_to_delete), batch_size):
                    batch = keys_to_delete[i:i+batch_size]
                    redis_client.delete(*batch)
                print(f"[🗑 CACHE CLEARED REDIS] Удалено {len(keys_to_delete)} ключей из Redis")
        except Exception as e:
            print(f"[CACHE CLEAR ERROR] Redis error: {e}")
    
    # Очищаем memory fallback
    _cache = {}
    _sorted_stations_cache = {}
    _page_positions_cache = {}
    print("[🗑 CACHE CLEARED] Кэш агрегаций, отсортированных списков и позиций страниц очищен")
    
    # Очищаем LRU кэши для предотвращения DetachedInstanceError
    cache_functions = []
    
    # Импортируем функции по отдельности для лучшей диагностики ошибок
    try:
        from app.common.services.get_services.energy_systems.energy_unit_get_services import (
            get_energy_unit_list,
        )
        cache_functions.extend([get_energy_unit_list])
    except Exception as e:
        print(f"[LRU CACHE CLEAR ERROR] Ошибка импорта energy_unit_get_services: {e}")
    
    try:
        from app.common.services.get_services.stations.station_type_get_services import (
            get_station_type_list_full, get_station_type_list
        )
        cache_functions.extend([get_station_type_list_full, get_station_type_list])
    except Exception as e:
        print(f"[LRU CACHE CLEAR ERROR] Ошибка импорта station_type_get_services: {e}")
    
    try:
        from app.common.services.get_services.stations.tes_type_get_services import (
            get_tes_type_list_full, get_tes_type_list
        )
        cache_functions.extend([get_tes_type_list_full, get_tes_type_list])
    except Exception as e:
        print(f"[LRU CACHE CLEAR ERROR] Ошибка импорта tes_type_get_services: {e}")
    
    try:
        from app.common.services.get_services.stations.tes_machine_type_get_services import (
            get_tes_machine_type_list_full, get_tes_machine_type_list
        )
        cache_functions.extend([get_tes_machine_type_list_full, get_tes_machine_type_list])
    except Exception as e:
        print(f"[LRU CACHE CLEAR ERROR] Ошибка импорта tes_machine_type_get_services: {e}")
    
    try:
        from app.common.services.get_services.stations.pgu_tes_machine_type_get_services import (
            get_pgu_tes_machine_type_list_full, get_pgu_tes_machine_type_list
        )
        cache_functions.extend([get_pgu_tes_machine_type_list_full, get_pgu_tes_machine_type_list])
    except Exception as e:
        print(f"[LRU CACHE CLEAR ERROR] Ошибка импорта pgu_tes_machine_type_get_services: {e}")
    
    try:
        from app.common.services.get_services.fuels.fuel_type_get_services import (
            get_fuel_type_list_full, get_fuel_type_list
        )
        cache_functions.extend([get_fuel_type_list_full, get_fuel_type_list])
    except Exception as e:
        print(f"[LRU CACHE CLEAR ERROR] Ошибка импорта fuel_type_get_services: {e}")
    
    try:
        from app.common.services.get_services.refdata_for_stations.condition_type_get_services import (
            get_condition_type_list_full, get_condition_type_list
        )
        cache_functions.extend([get_condition_type_list_full, get_condition_type_list])
    except Exception as e:
        print(f"[LRU CACHE CLEAR ERROR] Ошибка импорта condition_type_get_services: {e}")
    
    # Очищаем все LRU кэши
    if cache_functions:
        cleared_count = 0
        for func in cache_functions:
            try:
                if hasattr(func, 'cache_clear'):
                    func.cache_clear()
                    cleared_count += 1
            except Exception as e:
                print(f"[LRU CACHE CLEAR ERROR] Ошибка при очистке кэша функции {func.__name__}: {e}")
        
        print(f"[🗑 LRU CACHE CLEARED] Очищено LRU кэшей: {cleared_count}")


def clear_old_cache_entries():
    """Удаляет устаревшие записи из кэша."""
    global _cache
    current_time = datetime.now()
    keys_to_delete = []
    
    for key, (data, cached_time) in _cache.items():
        if current_time - cached_time >= _cache_timeout:
            keys_to_delete.append(key)
    
    for key in keys_to_delete:
        del _cache[key]
    
    if keys_to_delete:
        print(f"[🗑 CACHE CLEANUP] Удалено устаревших записей: {len(keys_to_delete)}")


def warmup_station_cache(force=False):
    """
    Прогревает кэш при запуске приложения.
    Загружает и кэширует отсортированный список станций без фильтров.
    
    Args:
        force: Если True, обновляет кэш даже если он уже существует
    
    Note:
        Должна вызываться внутри app.app_context()
    """
    import time
    
    try:
        # Проверяем, есть ли уже кэш
        cached = get_cached_sorted_stations({})
        if cached and not force:
            print(f"[CACHE WARMUP] Кэш уже существует ({len(cached)} станций), пропускаем прогрев")
            return
        
        print("[CACHE WARMUP] Начинается прогрев кэша станций...")
        start_time = time.time()
        
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from app.generation.models.station.station_model import Station
        from app.generation.models.machine.machine_model import Machine
        from app.refdata.models.territories.regional_district_model import RegionalDistrict
        from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
        from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
        from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
        from app.extensions import db
        from sqlalchemy.orm import selectinload, joinedload
        from app.common.services.database_version_filter import filter_by_db_version
        
        # Загружаем только ID станций и минимум данных для сортировки
        # Применяем фильтрацию по версии БД
        query = Station.query.options(
            selectinload(Station.regional_district)
                .selectinload(RegionalDistrict.regional_energy_systems)
                .joinedload(RegionalEnergySystem.union_energy_system)
                .joinedload(UnionEnergySystem.energy_system_type),
            joinedload(Station.energy_unit),
            joinedload(Station.station_type)
        )
        query = filter_by_db_version(query, Station)
        stations = query.all()
        
        print(f"[CACHE WARMUP] Загружено {len(stations)} станций")
        
        # Сортируем электростанции как на station_list: территориальная иерархия + нижний уровень (тип/название)
        def get_sorting_key(station):
            station_type_name = ""
            if getattr(station, "station_type", None) is not None and getattr(station.station_type, "name", None):
                station_type_name = station.station_type.name.strip()

            def _station_type_rank(name: str) -> int:
                s = (name or "").strip().upper()
                ordered = ["АЭС", "ГАЭС", "ГЭС", "ТЭС", "ВЭС", "СЭС"]  # "ГАЭС" раньше "ГЭС"
                direct = {abbr: idx for idx, abbr in enumerate(ordered)}
                if s in direct:
                    return direct[s]
                for idx, abbr in enumerate(ordered):
                    if abbr in s:
                        return idx
                return 999

            station_type_rank = _station_type_rank(station_type_name)

            energy_system_type_id = 0
            union_energy_system_order = float('inf')
            regional_energy_system_id = 0
            regional_district_name = ""
            energy_unit_id = station.id_energy_unit or 0

            if station.regional_district:
                regional_district_name = (station.regional_district.name or "").lower()
                if station.regional_district.regional_energy_systems:
                    res = station.regional_district.regional_energy_systems[0]
                    if res:
                        regional_energy_system_id = res.id
                        if res.union_energy_system:
                            union_energy_system_order = (
                                res.union_energy_system.display_order
                                if res.union_energy_system.display_order is not None else float('inf')
                            )
                            if res.union_energy_system.energy_system_type:
                                energy_system_type_id = res.union_energy_system.energy_system_type.id

            station_name = (station.name or "").strip().lower()

            return (
                energy_system_type_id,
                union_energy_system_order,
                regional_energy_system_id,
                regional_district_name,
                energy_unit_id,
                station_type_rank,
                station_name,
                station.id,
            )
        
        sorted_stations = sorted(stations, key=get_sorting_key)
        sorted_ids = [s.id for s in sorted_stations]
        
        # Кэшируем отсортированный список
        cache_sorted_stations({}, sorted_ids)
        
        elapsed = time.time() - start_time
        print(f"[CACHE WARMUP] ✅ Прогрев кэша завершен за {elapsed:.2f} сек ({len(sorted_ids)} станций)")
        
    except Exception as e:
        print(f"[CACHE WARMUP] ❌ Ошибка при прогреве кэша: {e}")
        import traceback
        traceback.print_exc()


# Глобальная переменная для управления фоновым обновлением
_background_refresh_active = False


def start_background_cache_refresh(app, interval_minutes=25):
    """
    Запускает фоновое обновление кэша каждые interval_minutes минут.
    Кэш обновляется за 5 минут до истечения TTL (30 минут).
    
    Args:
        app: Flask application instance для app_context
        interval_minutes: Интервал обновления в минутах (по умолчанию 25)
    """
    global _background_refresh_active
    import threading
    import time
    
    def refresh_task():
        """Задача для обновления кэша."""
        while _background_refresh_active:
            try:
                # Ждем interval_minutes минут
                time.sleep(interval_minutes * 60)
                
                if not _background_refresh_active:
                    break
                
                print("[CACHE REFRESH] Запуск периодического обновления кэша...")
                # Принудительно обновляем кэш с app context
                with app.app_context():
                    warmup_station_cache(force=True)
                
            except Exception as e:
                print(f"[CACHE REFRESH] ❌ Ошибка при обновлении кэша: {e}")
                import traceback
                traceback.print_exc()
    
    if _background_refresh_active:
        print("[CACHE REFRESH] Фоновое обновление кэша уже запущено")
        return
    
    _background_refresh_active = True
    refresh_thread = threading.Thread(target=refresh_task, daemon=True, name="CacheRefreshThread")
    refresh_thread.start()
    print(f"[CACHE REFRESH] ✅ Запущено фоновое обновление кэша каждые {interval_minutes} минут")


def stop_background_cache_refresh():
    """Останавливает фоновое обновление кэша."""
    global _background_refresh_active
    _background_refresh_active = False
    print("[CACHE REFRESH] Фоновое обновление кэша остановлено")


# Кэш для отсортированных списков станций (fallback)
_sorted_stations_cache = {}

def get_sorted_stations_cache_key(filters):
    """Генерирует ключ кэша для отсортированного списка станций."""
    from app.common.services.database_version_filter import get_current_db_version_id
    
    # Берем только фильтры, которые влияют на выборку станций
    # Исключаем start_year, end_year, page - они не влияют на список станций
    relevant_filters = {
        k: tuple(sorted(v)) if isinstance(v, list) else v
        for k, v in (filters or {}).items()
        if k not in ['start_year', 'end_year', 'page', 'sort_by', 'sort_dir']
    }
    
    # Добавляем текущую версию БД в ключ кэша
    current_version = get_current_db_version_id()
    relevant_filters['_db_version'] = current_version
    relevant_filters['_sort_v'] = STATIONS_SORT_CACHE_KEY_VERSION
    
    filter_items = sorted(relevant_filters.items())
    key_data = str(filter_items)
    hash_key = hashlib.md5(key_data.encode()).hexdigest()
    return f"stations:sorted:sv{STATIONS_SORT_CACHE_KEY_VERSION}:v{current_version or 'all'}:{hash_key}"

def cache_sorted_stations(filters, sorted_station_ids):
    """Кэширует отсортированный список ID станций в Redis."""
    cache_key = get_sorted_stations_cache_key(filters)
    redis_client = get_redis_client()
    
    if redis_client:
        try:
            # Проверяем, существует ли уже ключ
            if redis_client.exists(cache_key):
                print(f"[SORTED CACHE] Список уже закэширован, пропускаем")
                return
            
            # Сериализуем и сохраняем в Redis с TTL 30 минут
            serialized = pickle.dumps(sorted_station_ids)
            redis_client.setex(cache_key, int(_cache_timeout.total_seconds()), serialized)
            print(f"[SORTED CACHE REDIS] Закэширован отсортированный список из {len(sorted_station_ids)} станций")
            return
        except Exception as e:
            print(f"[SORTED CACHE ERROR] Redis error: {e}, falling back to memory")
    
    # Fallback to in-memory cache
    if cache_key in _sorted_stations_cache:
        print(f"[SORTED CACHE] Список уже закэширован, пропускаем")
        return
    _sorted_stations_cache[cache_key] = (sorted_station_ids, datetime.now())
    print(f"[SORTED CACHE MEMORY] Закэширован отсортированный список из {len(sorted_station_ids)} станций")

def get_cached_sorted_stations(filters):
    """Получает закэшированный отсортированный список ID станций из Redis."""
    cache_key = get_sorted_stations_cache_key(filters)
    redis_client = get_redis_client()
    
    if redis_client:
        try:
            serialized = redis_client.get(cache_key)
            if serialized:
                sorted_ids = pickle.loads(serialized)
                print(f"[SORTED CACHE HIT REDIS] Используется закэшированный список из {len(sorted_ids)} станций")
                return sorted_ids
        except Exception as e:
            print(f"[SORTED CACHE ERROR] Redis error: {e}, trying memory cache")
    
    # Fallback to in-memory cache
    if cache_key in _sorted_stations_cache:
        sorted_ids, cached_time = _sorted_stations_cache[cache_key]
        if datetime.now() - cached_time < _cache_timeout:
            print(f"[SORTED CACHE HIT MEMORY] Используется закэшированный список из {len(sorted_ids)} станций")
            return sorted_ids
        else:
            del _sorted_stations_cache[cache_key]
    
    return None


# Кэш для отслеживания реальных позиций страниц (fallback)
_page_positions_cache = {}

def cache_page_position(filters, page, end_position, last_station_info=None):
    """Кэширует реальную конечную позицию страницы и информацию о последней электростанции в Redis."""
    base_key = get_sorted_stations_cache_key(filters).replace('stations:sorted:', 'stations:page:')
    page_key = f"{base_key}:{page}"
    redis_client = get_redis_client()
    
    if redis_client:
        try:
            # Сохраняем данные о позиции страницы
            data = {
                'end_position': end_position,
                'last_station_info': last_station_info,
                'cached_time': datetime.now().isoformat()
            }
            serialized = pickle.dumps(data)
            redis_client.setex(page_key, int(_cache_timeout.total_seconds()), serialized)
            print(f"[PAGE POSITION REDIS] Сохранена позиция page={page}, end_position={end_position}")
            return
        except Exception as e:
            print(f"[PAGE POSITION ERROR] Redis error: {e}, falling back to memory")
    
    # Fallback to in-memory cache
    cache_key = get_sorted_stations_cache_key(filters)
    if cache_key not in _page_positions_cache:
        _page_positions_cache[cache_key] = {}
    _page_positions_cache[cache_key][page] = (end_position, last_station_info, datetime.now())
    print(f"[PAGE POSITION MEMORY] Сохранена позиция page={page}, end_position={end_position}")

def get_cached_page_position(filters, page):
    """Получает реальную позицию начала страницы и информацию о последней электростанции предыдущей страницы из Redis."""
    base_key = get_sorted_stations_cache_key(filters).replace('stations:sorted:', 'stations:page:')
    prev_page_key = f"{base_key}:{page - 1}"
    redis_client = get_redis_client()
    
    if redis_client:
        try:
            serialized = redis_client.get(prev_page_key)
            if serialized:
                data = pickle.loads(serialized)
                end_pos = data['end_position']
                last_station_info = data.get('last_station_info')
                print(f"[PAGE POSITION CACHE HIT REDIS] Page {page} starts at {end_pos}")
                return end_pos, last_station_info
        except Exception as e:
            print(f"[PAGE POSITION ERROR] Redis error: {e}, trying memory cache")
    
    # Fallback to in-memory cache
    cache_key = get_sorted_stations_cache_key(filters)
    
    if cache_key in _page_positions_cache:
        # Начало страницы N = конец страницы N-1
        if page > 1 and (page - 1) in _page_positions_cache[cache_key]:
            cached_data = _page_positions_cache[cache_key][page - 1]
            if len(cached_data) == 3:
                end_pos, last_station_info, cached_time = cached_data
            else:
                # Старый формат кэша (без last_station_info)
                end_pos, cached_time = cached_data
                last_station_info = None
            
            if datetime.now() - cached_time < _cache_timeout:
                print(f"[PAGE POSITION CACHE HIT MEMORY] Page {page} starts at {end_pos}")
                return end_pos, last_station_info
    
    return None, None

