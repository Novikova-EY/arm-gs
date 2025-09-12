"""Сервисный get-модуль для RegionalDistrict."""


from sqlalchemy import text, or_
from sqlalchemy.orm import joinedload
from typing import Union, List

# Модели
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea

from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict


def get_regional_district_list_full():
    """Получает полный список субъектов РФ."""
    return RegionalDistrict.query.all()


def get_regional_district_list():
    """Получает список субъектов РФ (кроме "не указано")."""
    query = (
        RegionalDistrict.query
        .filter(RegionalDistrict.id.isnot(None), RegionalDistrict.id > 0)
    )
    return query


def get_regional_district_name(regional_district_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами субъектов РФ по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not regional_district_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(regional_district_ids, str):
        ids = [int(x) for x in regional_district_ids.split(",") if x.strip().isdigit()]
    elif isinstance(regional_district_ids, int):
        ids = [regional_district_ids]
    else:
        ids = [int(x) for x in regional_district_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = RegionalDistrict.query.filter(RegionalDistrict.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)