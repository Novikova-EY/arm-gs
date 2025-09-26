"""Сервисный get-модуль для EnergyZone."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone


@lru_cache(maxsize=1)
def get_energy_zone_list_full():
    """Получает полный список энергозон'."""
    return (
        EnergyZone.query
        .order_by(
            (EnergyZone.id != 0),
            EnergyZone.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_energy_zone_list():
    """Получает список энергозон (кроме "не указано")."""
    query = (
        EnergyZone.query
        .filter(EnergyZone.id.isnot(None), EnergyZone.id > 0)
        .order_by(EnergyZone.name.asc())
    )
    return query


def get_energy_zone_name(_energy_zone_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами энергозон по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not _energy_zone_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(_energy_zone_ids, str):
        ids = [int(x) for x in _energy_zone_ids.split(",") if x.strip().isdigit()]
    elif isinstance(_energy_zone_ids, int):
        ids = [_energy_zone_ids]
    else:
        ids = [int(x) for x in _energy_zone_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = EnergyZone.query.filter(EnergyZone.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)
