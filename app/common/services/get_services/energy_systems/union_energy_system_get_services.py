"""Сервисный get-модуль для UnionEnergySystem."""

from sqlalchemy import text, or_
from sqlalchemy.orm import joinedload
from typing import Union, List

# Модели
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType


def get_union_energy_system_list_full():
    """Получает полный список ОЭС."""
    return UnionEnergySystem.query.all()


def get_union_energy_system_list():
    """Получает список ОЭС (кроме "не указано")."""
    query = (
        UnionEnergySystem.query
        .filter(UnionEnergySystem.id.isnot(None), UnionEnergySystem.id > 0)
    )
    return query


def get_union_energy_system_name(union_energy_system_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами ОЭС по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not union_energy_system_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(union_energy_system_ids, str):
        ids = [int(x) for x in union_energy_system_ids.split(",") if x.strip().isdigit()]
    elif isinstance(union_energy_system_ids, int):
        ids = [union_energy_system_ids]
    else:
        ids = [int(x) for x in union_energy_system_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = UnionEnergySystem.query.filter(UnionEnergySystem.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)