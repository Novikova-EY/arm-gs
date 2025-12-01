# -*- coding: utf-8 -*-
"""
Вспомогательные функции для фильтрации данных по версии БД.
"""

from functools import wraps
from flask import g
from sqlalchemy import or_


def get_current_db_version_id():
    """
    Получает ID текущей активной версии БД из контекста Flask или из БД.
    
    Returns:
        int or None: ID активной версии или None, если версия не установлена
    """
    from flask import g, has_app_context
    
    # Проверяем, что мы в контексте приложения
    if not has_app_context():
        # Если не в контексте приложения, берем напрямую из БД
        from app.common.models.database_version_model import DatabaseVersion
        active_version = DatabaseVersion.query.filter_by(is_active=True).first()
        return active_version.id if active_version else None
    
    # Сначала проверяем контекст Flask
    if hasattr(g, 'current_db_version'):
        return g.current_db_version
    
    # Если не найдено в контексте, берем из БД
    from app.common.models.database_version_model import DatabaseVersion
    active_version = DatabaseVersion.query.filter_by(is_active=True).first()
    if active_version:
        g.current_db_version = active_version.id
        return active_version.id
    
    return None


def filter_by_db_version(query, model_class):
    """
    Добавляет фильтр по текущей версии БД к запросу.
    
    Args:
        query: SQLAlchemy query объект
        model_class: Класс модели, которую нужно фильтровать
        
    Returns:
        query: Модифицированный query объект
        
    Example:
        query = Station.query
        query = filter_by_db_version(query, Station)
        stations = query.all()
    """
    current_version_id = get_current_db_version_id()
    model_name = model_class.__name__
    
    # Логи НЕ должны фильтроваться по версии БД, так как они хранят историю изменений
    if model_name == 'Log':
        print(f"[DEBUG] Пропускаем фильтрацию для {model_name}: логи должны отображаться все")
        return query
    
    print(f"[DEBUG] filter_by_db_version для {model_name}: current_version_id = {current_version_id}")
    
    if current_version_id is not None and hasattr(model_class, 'database_version_id'):
        # При выбранной версии показываем ТОЛЬКО записи этой версии
        # Записи без версии (NULL) НЕ показываются, так как они относятся к другим версиям
        print(f"[DEBUG] Применяем фильтр: {model_name}.database_version_id == {current_version_id}")
        query = query.filter(
            model_class.database_version_id == current_version_id
        )
    elif current_version_id is None and hasattr(model_class, 'database_version_id'):
        # Если версия не установлена, показываем только записи без версии (NULL)
        # Это предотвращает показ записей из неактивных версий
        print(f"[DEBUG] Применяем фильтр: {model_name}.database_version_id IS NULL")
        query = query.filter(model_class.database_version_id.is_(None))
    else:
        print(f"[DEBUG] Фильтр не применен для {model_name}: current_version_id={current_version_id}, has_database_version_id={hasattr(model_class, 'database_version_id')}")
    
    return query


def filter_by_explicit_db_version(query, model_class, version_id):
    """
    Добавляет фильтр по конкретной версии БД к запросу.

    Args:
        query: SQLAlchemy query объект
        model_class: Класс модели
        version_id: ID версии или None

    Returns:
        query: модифицированный query
    """
    if not hasattr(model_class, "database_version_id"):
        return query
    if version_id is None:
        return query.filter(model_class.database_version_id.is_(None))
    return query.filter(model_class.database_version_id == version_id)


def set_db_version_on_create(instance):
    """
    Автоматически устанавливает database_version_id при создании новой записи.
    
    Args:
        instance: Экземпляр модели
        
    Example:
        station = Station(name="New Station")
        set_db_version_on_create(station)
        db.session.add(station)
        db.session.commit()
    """
    current_version_id = get_current_db_version_id()
    
    if current_version_id is not None and hasattr(instance, 'database_version_id'):
        if instance.database_version_id is None:
            instance.database_version_id = current_version_id


def auto_filter_by_version(func):
    """
    Декоратор для автоматической фильтрации query по версии БД.
    
    Предполагается, что функция возвращает query объект.
    
    Example:
        @auto_filter_by_version
        def get_stations_query():
            return Station.query
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        
        # Проверяем, что результат - это query
        if hasattr(result, 'filter'):
            # Пытаемся определить модель из query
            if hasattr(result, 'column_descriptions') and result.column_descriptions:
                model_class = result.column_descriptions[0]['type']
                result = filter_by_db_version(result, model_class)
        
        return result
    
    return wrapper


def apply_version_filter(query, model_class):
    """
    Упрощенная обертка для фильтрации по версиям БД.
    Добавляет фильтр по текущей версии к query.
    
    Args:
        query: SQLAlchemy query объект
        model_class: Класс модели
        
    Returns:
        query: Модифицированный query с фильтром по версии
        
    Example:
        from app.common.services.database_version_filter import apply_version_filter
        
        def gen_company_query(filters...):
            query = GenCompany.query.filter(...)
            query = apply_version_filter(query, GenCompany)
            return query
    """
    return filter_by_db_version(query, model_class)


# Пример использования в services:
#
# from app.common.services.database_version_filter import filter_by_db_version, set_db_version_on_create
#
# def get_stations():
#     query = Station.query
#     query = filter_by_db_version(query, Station)
#     return query.all()
#
# def create_station(data):
#     station = Station(**data)
#     set_db_version_on_create(station)
#     db.session.add(station)
#     db.session.commit()
#     return station


