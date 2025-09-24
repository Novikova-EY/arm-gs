"""Сервисный get-модуль для UnionEnergySystem."""

from app.extensions import db
from functools import lru_cache
from collections import defaultdict
from typing import Union, List, Dict
from sqlalchemy.orm import selectinload, load_only

# Модели
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem


@lru_cache(maxsize=1)
def get_union_energy_system_list_full():
    """Получает полный список ОЭС."""
    return (
        UnionEnergySystem.query
        .order_by(UnionEnergySystem.name.asc())
        .all()
    )


@lru_cache(maxsize=1)
def get_union_energy_system_list():
    """Получает список ОЭС (кроме "не указано")."""
    query = (
        UnionEnergySystem.query
        .filter(UnionEnergySystem.id.isnot(None), UnionEnergySystem.id > 0)
        .order_by(UnionEnergySystem.name.asc())
    )
    return query


def get_union_energy_systems_list() -> List[UnionEnergySystem]:
    """Возвращает список ОЭС с заранее загруженными региональными энергосистемами."""
    return (
        UnionEnergySystem.query
        .options(
            selectinload(UnionEnergySystem.regional_energy_systems)
            .load_only(RegionalEnergySystem.id, RegionalEnergySystem.name)
        )
        .order_by(UnionEnergySystem.id)
        .all()
    )


@lru_cache(maxsize=1)
def get_union_energy_systems_map() -> Dict[int, str]:
    """Возвращает отображение {ОЭС.id: ОЭС.name} для всех ОЭС (кэшируется)."""
    rows = (
        UnionEnergySystem.query
        .with_entities(UnionEnergySystem.id, UnionEnergySystem.name)
        .order_by(UnionEnergySystem.id)
        .all()
    )
    return {id_: name for id_, name in rows}


@lru_cache(maxsize=1)
def get_ues_to_res_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ОЭС.id: [РЭС.id, ...]} (кэшируется)."""
    pairs = (
        db.session.query(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id)
        .order_by(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id)
        .all()
    )
    acc: dict[int, list[int]] = defaultdict(list)
    for ues_id, res_id in pairs:
        if ues_id is not None:
            acc[ues_id].append(res_id)
    return dict(acc)


@lru_cache(maxsize=1)
def get_res_to_ues_id_map() -> Dict[int, int]:
    """Возвращает отображение {РЭС.id: ОЭС.id} (кэшируется)."""
    pairs = (
        db.session.query(RegionalEnergySystem.id, RegionalEnergySystem.id_union_energy_system)
        .filter(RegionalEnergySystem.id_union_energy_system.isnot(None))
        .all()
    )
    return {res_id: ues_id for res_id, ues_id in pairs}


def invalidate_ues_lookups_cache() -> None:
    get_union_energy_systems_map.cache_clear()
    get_ues_to_res_ids_map.cache_clear()
    get_res_to_ues_id_map.cache_clear()

    
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