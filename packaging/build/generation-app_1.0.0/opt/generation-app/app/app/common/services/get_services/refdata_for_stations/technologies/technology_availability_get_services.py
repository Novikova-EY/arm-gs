"""Сервисный get-модуль для TechnologyAvailability."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import TechnologyAvailability

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_technology_availability_list_full():
    """Получает полный список видов технологий."""
    current_version = get_current_version()
    query = TechnologyAvailability.query
    
    if current_version:
        query = query.filter(TechnologyAvailability.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (TechnologyAvailability.id != 0),
            TechnologyAvailability.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_technology_availability_list():
    """Получает список видов технологий (кроме "не указано")."""
    current_version = get_current_version()
    query = TechnologyAvailability.query
    
    if current_version:
        query = query.filter(TechnologyAvailability.database_version_id == current_version)
    
    return (
        query
        .filter(TechnologyAvailability.id.isnot(None), TechnologyAvailability.id > 0)
        .order_by(TechnologyAvailability.name.asc())
    )


def get_technology_availability_name(technology_availability_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами видов технологий по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not technology_availability_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(technology_availability_ids, str):
        ids = [int(x) for x in technology_availability_ids.split(",") if x.strip().isdigit()]
    elif isinstance(technology_availability_ids, int):
        ids = [technology_availability_ids]
    else:
        ids = [int(x) for x in technology_availability_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = TechnologyAvailability.query.filter(TechnologyAvailability.id.in_(ids))
    
    if current_version:
        query = query.filter(TechnologyAvailability.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)