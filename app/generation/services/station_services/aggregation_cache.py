"""Простой кэш для агрегаций."""

import hashlib
import pickle
from functools import wraps
from datetime import datetime, timedelta

# Простой in-memory кэш
_cache = {}
_cache_timeout = timedelta(minutes=30)  # Кэш на 30 минут


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
    """Очищает весь кэш агрегаций."""
    global _cache, _sorted_stations_cache, _page_positions_cache
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


# Кэш для отсортированных списков станций
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
    return hashlib.md5(key_data.encode()).hexdigest()

def cache_sorted_stations(filters, sorted_station_ids):
    """Кэширует отсортированный список ID станций."""
    cache_key = get_sorted_stations_cache_key(filters)
    # Проверяем, не закэширован ли уже этот список
    if cache_key in _sorted_stations_cache:
        print(f"[SORTED CACHE] Список уже закэширован, пропускаем")
        return
    _sorted_stations_cache[cache_key] = (sorted_station_ids, datetime.now())
    print(f"[SORTED CACHE] Закэширован отсортированный список из {len(sorted_station_ids)} станций")

def get_cached_sorted_stations(filters):
    """Получает закэшированный отсортированный список ID станций."""
    cache_key = get_sorted_stations_cache_key(filters)
    if cache_key in _sorted_stations_cache:
        sorted_ids, cached_time = _sorted_stations_cache[cache_key]
        if datetime.now() - cached_time < _cache_timeout:
            print(f"[SORTED CACHE HIT] Используется закэшированный список из {len(sorted_ids)} станций")
            return sorted_ids
        else:
            del _sorted_stations_cache[cache_key]
    return None


# Кэш для отслеживания реальных позиций страниц (где заканчивается каждая страница)
_page_positions_cache = {}

def cache_page_position(filters, page, end_position, last_station_info=None):
    """Кэширует реальную конечную позицию страницы и информацию о последней станции."""
    cache_key = get_sorted_stations_cache_key(filters)
    if cache_key not in _page_positions_cache:
        _page_positions_cache[cache_key] = {}
    _page_positions_cache[cache_key][page] = (end_position, last_station_info, datetime.now())
    print(f"[PAGE POSITION] Сохранена позиция page={page}, end_position={end_position}, cache_key={cache_key[:8]}...")

def get_cached_page_position(filters, page):
    """Получает реальную позицию начала страницы и информацию о последней станции предыдущей страницы."""
    cache_key = get_sorted_stations_cache_key(filters)
    print(f"[GET PAGE POSITION] Page {page}, cache_key={cache_key[:8]}..., cache exists: {cache_key in _page_positions_cache}")
    
    if cache_key in _page_positions_cache:
        print(f"[GET PAGE POSITION] Cached pages for this key: {list(_page_positions_cache[cache_key].keys())}")
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
                print(f"[PAGE POSITION CACHE HIT] Page {page} starts at {end_pos}")
                return end_pos, last_station_info
        else:
            print(f"[PAGE POSITION] Page {page-1} not found in cache")
    else:
        print(f"[PAGE POSITION] Cache key not found")
    
    return None, None

