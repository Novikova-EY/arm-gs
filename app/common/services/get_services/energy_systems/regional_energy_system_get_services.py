"""Сервисный get-модуль для RegionalEnergySystem."""

from sqlalchemy import text, or_
from sqlalchemy.orm import joinedload
from typing import Union, List

# Модели
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType


def get_regional_energy_system_list_full():
    """Получает полный список региональных энергосистем."""
    return RegionalEnergySystem.query.all()


def get_regional_energy_system_list():
    """Получает список региональных энергосистем (кроме "не указано")."""
    query = (
        RegionalEnergySystem.query
        .filter(RegionalEnergySystem.id.isnot(None), RegionalEnergySystem.id > 0)
    )
    return query


def get_regional_energy_system_name(regional_energy_system_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами региональных энергосистем по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not regional_energy_system_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(regional_energy_system_ids, str):
        ids = [int(x) for x in regional_energy_system_ids.split(",") if x.strip().isdigit()]
    elif isinstance(regional_energy_system_ids, int):
        ids = [regional_energy_system_ids]
    else:
        ids = [int(x) for x in regional_energy_system_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = RegionalEnergySystem.query.filter(RegionalEnergySystem.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)