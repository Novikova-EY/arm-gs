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


def get_redis_client():
    """Получает Redis клиент или None если недоступен."""
    try:
        redis_client = current_app.config.get('SESSION_REDIS')
        if redis_client:
            redis_client.ping()
            return redis_client
    except (redis.ConnectionError, redis.TimeoutError, Exception):
        pass
    return None


def get_cache_key(start_year, end_year, station_ids, filters=None):
    """Генерирует ключ кэша на основе параметров запроса."""
    # Сортируем station_ids для консистентности
    sorted_ids = tuple(sorted(station_ids))
    
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
                "date_exploitation_filter", 
                "date_decompressing_expected_filter", "date_modernization_expected_filter"
            ] and v
        }
        filters_str = str(sorted(relevant_filters.items()))
    else:
        filters_str = ""
    
    key_data = f"{start_year}_{end_year}_{sorted_ids}_{filters_str}"
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
    """Очищает весь кэш агрегаций (Redis + memory fallback)."""
    global _cache, _sorted_stations_cache, _page_positions_cache
    
    redis_client = get_redis_client()
    if redis_client:
        try:
            # ОПТИМИЗАЦИЯ: Используем SCAN вместо KEYS для избежания блокировки Redis
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
        
        # Загружаем только ID станций и минимум данных для сортировки
        stations = Station.query.options(
            selectinload(Station.regional_district)
                .selectinload(RegionalDistrict.regional_energy_systems)
                .joinedload(RegionalEnergySystem.union_energy_system)
                .joinedload(UnionEnergySystem.energy_system_type),
            joinedload(Station.energy_unit),
            joinedload(Station.station_type)
        ).all()
        
        print(f"[CACHE WARMUP] Загружено {len(stations)} станций")
        
        # Сортируем станции
        def get_sorting_key(station):
            energy_system_type_id = 0
            union_energy_system_order = float('inf')
            regional_energy_system_id = 0
            regional_district_name = ""
            energy_unit_id = station.id_energy_unit or 0
            
            min_type = station.id_station_type if station.id_station_type is not None else float('inf')
            
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
            
            return (
                energy_system_type_id,
                union_energy_system_order,
                regional_energy_system_id,
                regional_district_name,
                energy_unit_id,
                min_type,
                station.id
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
    # Берем только фильтры, которые влияют на выборку станций
    # Исключаем start_year, end_year, page - они не влияют на список станций
    relevant_filters = {
        k: tuple(sorted(v)) if isinstance(v, list) else v
        for k, v in (filters or {}).items()
        if k not in ['start_year', 'end_year', 'page', 'sort_by', 'sort_dir']
    }
    filter_items = sorted(relevant_filters.items())
    key_data = str(filter_items)
    hash_key = hashlib.md5(key_data.encode()).hexdigest()
    return f"stations:sorted:{hash_key}"

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
    """Кэширует реальную конечную позицию страницы и информацию о последней станции в Redis."""
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
    """Получает реальную позицию начала страницы и информацию о последней станции предыдущей страницы из Redis."""
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

