"""Сервисный get-модуль для EnergySystemType."""

from app.extensions import db
from typing import Union, List
from functools import lru_cache

# Модели
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_energy_system_type_list_full():
    """Получает полный список типов энергосистем."""
    current_version = get_current_version()
    query = EnergySystemType.query
    
    if current_version:
        query = query.filter(EnergySystemType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (EnergySystemType.id != 0),
            EnergySystemType.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_energy_system_type_list():
    """Получает список типов энергосистем (кроме "не указано")."""
    current_version = get_current_version()
    query = EnergySystemType.query
    
    if current_version:
        query = query.filter(EnergySystemType.database_version_id == current_version)
    
    return (
        query
        .filter(EnergySystemType.id.isnot(None), EnergySystemType.id > 0)
        .order_by(EnergySystemType.name.asc())
    )


@lru_cache(maxsize=1)
def get_energy_system_type_map():
    """Возвращает отображение {id: name} для всех типов энергосистем."""
    current_version = get_current_version()
    query = db.session.query(EnergySystemType.id, EnergySystemType.name)
    
    if current_version:
        query = query.filter(EnergySystemType.database_version_id == current_version)
    
    rows = query.order_by(EnergySystemType.id).all()
    energy_system_type_names = {id_: name for id_, name in rows}
    return energy_system_type_names


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

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = EnergySystemType.query.filter(EnergySystemType.id.in_(ids))
    
    if current_version:
        query = query.filter(EnergySystemType.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)


