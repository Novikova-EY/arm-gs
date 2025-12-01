# -*- coding: utf-8 -*-
"""
Универсальный сервис кэширования для выпадающих списков с фильтрацией по версии БД.
"""

from functools import lru_cache
from typing import List, Tuple, Any
from app.extensions import db
from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)


class ChoicesCacheService:
    """Универсальный сервис для кэширования choices с фильтрацией по версии БД."""
    
    _cache = {}
    
    # Специальные константы для "пустых" значений
    EMPTY_VALUE_ID = 0
    EMPTY_VALUE_TEXT = "— не указано —"
    
    @classmethod
    def _build_versioned_cache_key(cls, base_key: str) -> str:
        version_id = get_current_db_version_id()
        suffix = version_id if version_id is not None else "none"
        return f"{base_key}_ver_{suffix}"

    @classmethod
    def get_choices(cls, model_class, order_by_field, name_field=None, cache_key: str = None) -> List[Tuple[int, str]]:
        """
        Получает choices для модели с фильтрацией по версии БД.
        
        Args:
            model_class: Класс модели SQLAlchemy
            order_by_field: Поле для сортировки
            name_field: Поле для имени (если не указано, используется 'name' или 'machine_name')
            cache_key: Ключ кэша (если не указан, используется имя модели)
            
        Returns:
            List[Tuple[int, str]]: Список кортежей (id, name)
        """
        if cache_key is None:
            cache_key = model_class.__name__.lower()
        
        # Определяем поле для имени
        if name_field is None:
            # Проверяем, какое поле существует в модели
            if hasattr(model_class, 'machine_name'):
                name_field = 'machine_name'
            elif hasattr(model_class, 'name'):
                name_field = 'name'
            else:
                name_field = 'name'  # По умолчанию
            
        versioned_key = cls._build_versioned_cache_key(cache_key)

        if versioned_key not in cls._cache:
            print(f"[CHOICES_CACHE] Загружаем {versioned_key} из БД (с фильтрацией по версии)")
            query = model_class.query.order_by(order_by_field)
            query = filter_by_db_version(query, model_class)
            cls._cache[versioned_key] = [(item.id, getattr(item, name_field)) for item in query.all()]
        else:
            print(f"[CHOICES_CACHE] Используем кэшированные {versioned_key}: {len(cls._cache[versioned_key])} записей")
            
        return cls._cache[versioned_key]
    
    @classmethod
    def get_choices_with_default(cls, model_class, order_by_field, default_text: str = None, cache_key: str = None) -> List[Tuple[int, str]]:
        """
        Получает choices с добавлением значения по умолчанию.
        Использует специальный ID=0 для "пустого" значения, чтобы избежать конфликтов с версионированием.
        
        Args:
            model_class: Класс модели SQLAlchemy
            order_by_field: Поле для сортировки
            default_text: Текст для значения по умолчанию (если None, используется константа)
            cache_key: Ключ кэша
            
        Returns:
            List[Tuple[int, str]]: Список кортежей с добавленным значением по умолчанию
        """
        if default_text is None:
            default_text = cls.EMPTY_VALUE_TEXT
            
        choices = cls.get_choices(model_class, order_by_field, cache_key)
        return [(cls.EMPTY_VALUE_ID, default_text)] + choices
    
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
            keys_to_delete = [key for key in cls._cache.keys() if key.startswith(f"{cache_key}_ver_")]
            for key in keys_to_delete:
                cls._cache.pop(key, None)
                print(f"[CHOICES_CACHE] Очищен кэш для {key}")
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
    
    @classmethod
    def is_empty_value(cls, value) -> bool:
        """
        Проверяет, является ли значение "пустым" (None, 0, или пустая строка).
        
        Args:
            value: Значение для проверки
            
        Returns:
            bool: True если значение считается "пустым"
        """
        return value is None or value == 0 or value == '' or value == cls.EMPTY_VALUE_ID
    
    @classmethod
    def normalize_empty_value(cls, value):
        """
        Нормализует "пустое" значение к стандартному виду.
        
        Args:
            value: Значение для нормализации
            
        Returns:
            int: 0 для пустых значений, иначе исходное значение
        """
        if cls.is_empty_value(value):
            return cls.EMPTY_VALUE_ID
        return value


# Глобальный экземпляр для удобства использования
choices_cache = ChoicesCacheService()

