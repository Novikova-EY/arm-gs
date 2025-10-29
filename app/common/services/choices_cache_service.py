# -*- coding: utf-8 -*-
"""
Универсальный сервис кэширования для выпадающих списков с фильтрацией по версии БД.
"""

from functools import lru_cache
from typing import List, Tuple, Any
from app.extensions import db
from app.common.services.database_version_filter import filter_by_db_version


class ChoicesCacheService:
    """Универсальный сервис для кэширования choices с фильтрацией по версии БД."""
    
    _cache = {}
    
    @classmethod
    def get_choices(cls, model_class, order_by_field, cache_key: str = None) -> List[Tuple[int, str]]:
        """
        Получает choices для модели с фильтрацией по версии БД.
        
        Args:
            model_class: Класс модели SQLAlchemy
            order_by_field: Поле для сортировки
            cache_key: Ключ кэша (если не указан, используется имя модели)
            
        Returns:
            List[Tuple[int, str]]: Список кортежей (id, name)
        """
        if cache_key is None:
            cache_key = model_class.__name__.lower()
            
        if cache_key not in cls._cache:
            print(f"[CHOICES_CACHE] Загружаем {cache_key} из БД (с фильтрацией по версии)")
            query = model_class.query.order_by(order_by_field)
            query = filter_by_db_version(query, model_class)
            cls._cache[cache_key] = [(item.id, item.name) for item in query.all()]
        else:
            print(f"[CHOICES_CACHE] Используем кэшированные {cache_key}: {len(cls._cache[cache_key])} записей")
            
        return cls._cache[cache_key]
    
    @classmethod
    def get_choices_with_default(cls, model_class, order_by_field, default_text: str = "не указано", cache_key: str = None) -> List[Tuple[int, str]]:
        """
        Получает choices с добавлением значения по умолчанию.
        
        Args:
            model_class: Класс модели SQLAlchemy
            order_by_field: Поле для сортировки
            default_text: Текст для значения по умолчанию
            cache_key: Ключ кэша
            
        Returns:
            List[Tuple[int, str]]: Список кортежей с добавленным значением по умолчанию
        """
        choices = cls.get_choices(model_class, order_by_field, cache_key)
        return [(0, default_text)] + choices
    
    @classmethod
    def get_choices_for_select(cls, model_class, order_by_field, cache_key: str = None) -> List[Tuple[int, str]]:
        """
        Получает choices для SelectField с фильтрацией по версии БД.
        
        Args:
            model_class: Класс модели SQLAlchemy
            order_by_field: Поле для сортировки
            cache_key: Ключ кэша
            
        Returns:
            List[Tuple[int, str]]: Список кортежей для SelectField
        """
        return cls.get_choices(model_class, order_by_field, cache_key)
    
    @classmethod
    def clear_cache(cls, cache_key: str = None):
        """
        Очищает кэш.
        
        Args:
            cache_key: Ключ кэша для очистки (если не указан, очищается весь кэш)
        """
        if cache_key:
            cls._cache.pop(cache_key, None)
            print(f"[CHOICES_CACHE] Очищен кэш для {cache_key}")
        else:
            cls._cache.clear()
            print(f"[CHOICES_CACHE] Очищен весь кэш")
    
    @classmethod
    def invalidate_cache(cls, cache_key: str):
        """
        Инвалидирует кэш для конкретного ключа.
        
        Args:
            cache_key: Ключ кэша для инвалидации
        """
        cls.clear_cache(cache_key)


# Глобальный экземпляр для удобства использования
choices_cache = ChoicesCacheService()

