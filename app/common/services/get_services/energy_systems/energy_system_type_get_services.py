"""Сервисный get-модуль для EnergySystemType."""

from sqlalchemy import text, or_
from sqlalchemy.orm import joinedload
from typing import Union, List

# Модели
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType


def get_energy_system_type_list_full():
    """Получает полный список типов энергосистем."""
    return EnergySystemType.query.all()


def get_energy_system_type_list():
    """Получает список типов энергосистем (кроме "не указано")."""
    query = (
        EnergySystemType.query
        .filter(EnergySystemType.id.isnot(None), EnergySystemType.id > 0)
    )
    return query


def get_energy_system_type_name(energy_system_type_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами частей энергосистем России по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not energy_system_type_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(energy_system_type_ids, str):
        ids = [int(x) for x in energy_system_type_ids.split(",") if x.strip().isdigit()]
    elif isinstance(energy_system_type_ids, int):
        ids = [energy_system_type_ids]
    else:
        ids = [int(x) for x in energy_system_type_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = EnergySystemType.query.filter(EnergySystemType.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)
