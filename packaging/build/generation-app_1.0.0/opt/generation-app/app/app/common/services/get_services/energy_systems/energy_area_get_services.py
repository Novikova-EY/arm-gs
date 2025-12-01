"""Сервисный get-модуль для EnergyArea."""

from typing import Union, List
from functools import lru_cache

# Модели
from app.refdata.models.energy_systems.energy_area_model import EnergyArea

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_energy_area_list_full():
    """Получает полный список энергорайонов."""
    current_version = get_current_version()
    query = EnergyArea.query
    
    if current_version:
        query = query.filter(EnergyArea.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (EnergyArea.id != 0),
            EnergyArea.name.asc()
        )
        .all()
    )

@lru_cache(maxsize=1)
def get_energy_area_list():
    """Получает список энергорайонов (кроме "не указано")."""
    current_version = get_current_version()
    query = EnergyArea.query
    
    if current_version:
        query = query.filter(EnergyArea.database_version_id == current_version)
    
    return (
        query
        .filter(EnergyArea.id.isnot(None), EnergyArea.id > 0)
        .order_by(EnergyArea.name.asc())
    )


def get_energy_area_name(energy_area_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами энергорайонов по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not energy_area_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(energy_area_ids, str):
        ids = [int(x) for x in energy_area_ids.split(",") if x.strip().isdigit()]
    elif isinstance(energy_area_ids, int):
        ids = [energy_area_ids]
    else:
        ids = [int(x) for x in energy_area_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = EnergyArea.query.filter(EnergyArea.id.in_(ids))
    
    if current_version:
        query = query.filter(EnergyArea.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)