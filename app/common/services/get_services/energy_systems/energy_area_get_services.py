"""Сервисный get-модуль для EnergyArea."""

from typing import Union, List
from functools import lru_cache

# Модели
from app.refdata.models.energy_systems.energy_area_model import EnergyArea


@lru_cache(maxsize=1)
def get_energy_area_list_full():
    """Получает полный список энергорайонов."""
    return (
        EnergyArea.query
        .order_by(EnergyArea.name.asc())
        .all()
    )

@lru_cache(maxsize=1)
def get_energy_area_list():
    """Получает список энергорайонов (кроме "не указано")."""
    query = (
        EnergyArea.query
        .filter(EnergyArea.id.isnot(None), EnergyArea.id > 0)
        .order_by(EnergyArea.name.asc())
    )
    return query


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

    # Берем имена из базы
    objs = EnergyArea.query.filter(EnergyArea.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)