"""Сервисный get-модуль для EnergyUnit."""

from typing import Union, List
from functools import lru_cache

# Модели
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit


@lru_cache(maxsize=1)
def get_energy_unit_list_full():
    """Получает полный список энергоузлов."""
    return (
        EnergyUnit.query
        .order_by(
            (EnergyUnit.id != 0),
            EnergyUnit.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_energy_unit_list():
    """Получает список энергоузлов (кроме "не указано")."""
    query = (
        EnergyUnit.query
        .filter(EnergyUnit.id.isnot(None), EnergyUnit.id > 0)
        .order_by(EnergyUnit.name.asc())
    )
    return query


def get_energy_unit_name(energy_unit_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами энергоузлов по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not energy_unit_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(energy_unit_ids, str):
        ids = [int(x) for x in energy_unit_ids.split(",") if x.strip().isdigit()]
    elif isinstance(energy_unit_ids, int):
        ids = [energy_unit_ids]
    else:
        ids = [int(x) for x in energy_unit_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = EnergyUnit.query.filter(EnergyUnit.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)