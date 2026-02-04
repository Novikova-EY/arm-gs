# -*- coding: utf-8 -*-
"""
Сервисы для работы с признаками годов (YearFeature).
"""

from app.extensions import db
from functools import lru_cache

# Модели
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year

# Сервисы
from app.common.services.database_version_services import get_current_version


def get_year_feature_list():
    """Получает список признаков годов для текущей версии. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = YearFeature.query
    if current_version:
        query = query.filter(YearFeature.database_version_id == current_version)
    return query.order_by(YearFeature.name.asc()).all()


def get_year_feature_id_dict():
    """Возвращает словарь {id: name} признаков годов для текущей версии. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = YearFeature.query
    if current_version:
        query = query.filter(YearFeature.database_version_id == current_version)
    features = query.all()
    return {feature.id: feature.name for feature in features}


def get_year_feature_dict():
    """Возвращает словарь {year_number: year_feature_name} для текущей версии."""
    current_version = get_current_version()
    return get_year_feature_dict_for_version(current_version)


@lru_cache(maxsize=64)
def get_year_feature_dict_for_version(version_id: int | None):
    """Возвращает словарь {year_number: year_feature_name} для указанной версии."""
    query = (
        db.session.query(Year.number, YearFeature.name)
        .join(YearFeature, Year.id_year_feature == YearFeature.id)
    )
    if version_id:
        query = query.filter(
            (Year.database_version_id == version_id)
            | (YearFeature.database_version_id == version_id)
            | (YearFeature.database_version_id.is_(None))
        )
    rows = query.all()
    return {number: name for number, name in rows}


def get_year_feature_by_name(name, version_id=None):
    """
    Получает признак года по имени для указанной версии.
    
    Args:
        name: Название признака года
        version_id: ID версии (если None, используется текущая версия)
        
    Returns:
        YearFeature: Признак года или None
    """
    if version_id is None:
        version_id = get_current_version()
    
    query = YearFeature.query.filter(YearFeature.name == name)
    
    if version_id:
        query = query.filter(YearFeature.database_version_id == version_id)
    
    return query.first()


def get_year_features_for_version(version_id):
    """
    Получает все признаки годов для указанной версии.
    
    Args:
        version_id: ID версии
        
    Returns:
        List[YearFeature]: Список признаков годов
    """
    return (
        YearFeature.query
        .filter(YearFeature.database_version_id == version_id)
        .order_by(YearFeature.name.asc())
        .all()
    )
