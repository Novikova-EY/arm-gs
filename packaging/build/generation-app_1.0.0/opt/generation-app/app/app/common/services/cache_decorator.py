# -*- coding: utf-8 -*-
"""
Декораторы и утилиты для кэширования данных.
Оптимизация производительности при параллельной работе пользователей.
"""
from functools import wraps
from app.extensions import cache
from flask import request
import hashlib
import json


def make_cache_key(*args, **kwargs):
    """
    Создает уникальный ключ для кэша на основе аргументов.
    
    Args:
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы
    
    Returns:
        str: Уникальный ключ для кэша
    """
    # Создаем уникальный ключ на основе пути запроса и аргументов
    key_parts = [request.path]
    
    # Добавляем позиционные аргументы
    for arg in args:
        if isinstance(arg, (dict, list)):
            key_parts.append(json.dumps(arg, sort_keys=True))
        else:
            key_parts.append(str(arg))
    
    # Добавляем именованные аргументы
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (dict, list)):
            key_parts.append(f"{k}={json.dumps(v, sort_keys=True)}")
        else:
            key_parts.append(f"{k}={v}")
    
    # Создаем хеш для ключа
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached_route(timeout=300, key_prefix='view'):
    """
    Декоратор для кэширования результатов маршрутов.
    
    Args:
        timeout: Время жизни кэша в секундах (по умолчанию 5 минут)
        key_prefix: Префикс для ключа кэша
    
    Использование:
        @app.route('/stations')
        @cached_route(timeout=600)
        def list_stations():
            return render_template('stations.html', stations=stations)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем уникальный ключ для кэша
            cache_key = f"{key_prefix}:{make_cache_key(*args, **kwargs)}"
            
            # Пытаемся получить данные из кэша
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return cached_data
            
            # Выполняем функцию и сохраняем результат в кэш
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result
        
        return wrapper
    return decorator


def cached_query(timeout=300, key_prefix='query'):
    """
    Декоратор для кэширования результатов запросов к БД.
    
    Args:
        timeout: Время жизни кэша в секундах (по умолчанию 5 минут)
        key_prefix: Префикс для ключа кэша
    
    Использование:
        @cached_query(timeout=600, key_prefix='station')
        def get_station_by_id(station_id):
            return Station.query.get(station_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Создаем уникальный ключ для кэша
            cache_key = f"{key_prefix}:{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            # Пытаемся получить данные из кэша
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return cached_data
            
            # Выполняем функцию и сохраняем результат в кэш
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout=timeout)
            return result
        
        return wrapper
    return decorator


def invalidate_cache(key_prefix, *args, **kwargs):
    """
    Инвалидация кэша по ключу.
    
    Args:
        key_prefix: Префикс ключа кэша
        *args: Позиционные аргументы для создания ключа
        **kwargs: Именованные аргументы для создания ключа
    
    Использование:
        # После обновления станции
        invalidate_cache('station', station_id=123)
    """
    cache_key = f"{key_prefix}:{make_cache_key(*args, **kwargs)}"
    cache.delete(cache_key)


def invalidate_cache_pattern(pattern):
    """
    Инвалидация кэша по шаблону (работает только с Redis).
    
    Args:
        pattern: Шаблон для поиска ключей (например, 'station:*')
    
    Использование:
        # После обновления любой станции
        invalidate_cache_pattern('station:*')
    """
    try:
        # Получаем Redis клиент из кэша
        if hasattr(cache.cache, '_client'):
            redis_client = cache.cache._client
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
    except Exception as e:
        # Если Redis недоступен или используется другой бэкенд
        pass


class CacheManager:
    """
    Менеджер кэша для групповых операций.
    """
    
    @staticmethod
    def clear_all():
        """Очистка всего кэша."""
        cache.clear()
    
    @staticmethod
    def clear_by_prefix(prefix):
        """
        Очистка кэша по префиксу.
        
        Args:
            prefix: Префикс ключей для удаления
        """
        invalidate_cache_pattern(f"{prefix}:*")
    
    @staticmethod
    def warm_cache(func, items, key_prefix, timeout=300):
        """
        Предварительный прогрев кэша.
        
        Args:
            func: Функция для получения данных
            items: Список элементов для прогрева
            key_prefix: Префикс для ключей кэша
            timeout: Время жизни кэша в секундах
        
        Использование:
            # Прогрев кэша для списка станций
            CacheManager.warm_cache(
                func=get_station_by_id,
                items=[1, 2, 3, 4, 5],
                key_prefix='station',
                timeout=600
            )
        """
        for item in items:
            cache_key = f"{key_prefix}:{func.__name__}:{item}"
            if cache.get(cache_key) is None:
                result = func(item)
                cache.set(cache_key, result, timeout=timeout)

