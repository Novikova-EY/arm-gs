"""Сервисный get-модуль для Fuel."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.fuels.fuel_model import Fuel

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_fuel_list_full():
    """Получает полный список типов топлива."""
    current_version = get_current_version()
    query = Fuel.query
    
    if current_version:
        query = query.filter(Fuel.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (Fuel.id != 0),
            Fuel.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_fuel_list():
    """Получает список типов топлива (кроме "не указано")."""
    current_version = get_current_version()
    query = Fuel.query
    
    if current_version:
        query = query.filter(Fuel.database_version_id == current_version)
    
    return (
        query
        .filter(Fuel.id.isnot(None), Fuel.id > 0)
        .order_by(Fuel.name.asc())
    )


def get_fuel_name(fuel_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами типов топлива по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not fuel_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(fuel_ids, str):
        ids = [int(x) for x in fuel_ids.split(",") if x.strip().isdigit()]
    elif isinstance(fuel_ids, int):
        ids = [fuel_ids]
    else:
        ids = [int(x) for x in fuel_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = Fuel.query.filter(Fuel.id.in_(ids))
    
    if current_version:
        query = query.filter(Fuel.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)