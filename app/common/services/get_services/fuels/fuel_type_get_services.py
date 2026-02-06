"""Сервисный get-модуль для FuelType."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.fuels.fuel_type_model import FuelType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_fuel_type_list_full():
    """Получает полный список видов топлива."""
    current_version = get_current_version()
    query = FuelType.query
    
    if current_version:
        query = query.filter(FuelType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            FuelType.display_order.asc().nullslast(),
            FuelType.name.asc(),
            FuelType.id.asc(),
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_fuel_type_list():
    """Получает список видов топлива (кроме "не указано")."""
    current_version = get_current_version()
    query = FuelType.query
    
    if current_version:
        query = query.filter(FuelType.database_version_id == current_version)
    
    return (
        query
        .filter(FuelType.id.isnot(None), FuelType.id > 0)
        .order_by(
            FuelType.display_order.asc().nullslast(),
            FuelType.name.asc(),
            FuelType.id.asc(),
        )
    )


def get_fuel_type_name(fuel_type_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами видов топлива по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not fuel_type_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(fuel_type_ids, str):
        ids = [int(x) for x in fuel_type_ids.split(",") if x.strip().isdigit()]
    elif isinstance(fuel_type_ids, int):
        ids = [fuel_type_ids]
    else:
        ids = [int(x) for x in fuel_type_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = FuelType.query.filter(FuelType.id.in_(ids))
    
    if current_version:
        query = query.filter(FuelType.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)