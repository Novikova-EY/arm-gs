"""Сервисный get-модуль для EnergyUnit."""

from typing import Union, List
from functools import lru_cache

from sqlalchemy import or_

# Модели
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit

# Сервисы
from app.common.services.database_version_services import get_current_version


def get_energy_unit_list_full():
    """Полный список энергоузлов. Без LRU-кэша: иначе ORM-объекты после закрытия сессии отвязываются (DetachedInstanceError)."""
    current_version = get_current_version()
    query = EnergyUnit.query
    
    if current_version:
        # Для справочников допускаем "общие" записи без версии (NULL).
        query = query.filter(
            or_(
                EnergyUnit.database_version_id == current_version,
                EnergyUnit.database_version_id.is_(None),
            )
        )
    
    return (
        query
        .order_by(
            (EnergyUnit.id != 0),
            EnergyUnit.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_energy_unit_list():
    """Получает список энергоузлов (кроме "не указано")."""
    current_version = get_current_version()
    query = EnergyUnit.query
    
    if current_version:
        query = query.filter(
            or_(
                EnergyUnit.database_version_id == current_version,
                EnergyUnit.database_version_id.is_(None),
            )
        )
    
    return (
        query
        .filter(EnergyUnit.id.isnot(None), EnergyUnit.id > 0)
        .order_by(EnergyUnit.name.asc())
    )


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

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = EnergyUnit.query.filter(EnergyUnit.id.in_(ids))
    
    if current_version:
        query = query.filter(EnergyUnit.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)