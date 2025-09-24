"""Сервисный get-модуль для RegionalEnergySystem."""

from functools import lru_cache
from sqlalchemy.orm import selectinload
from typing import Union, List, Dict

# Модели
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem


@lru_cache(maxsize=1)
def get_regional_energy_system_list_full():
    """Получает полный список региональных энергосистем."""
    return (
        RegionalEnergySystem.query
        .order_by(RegionalEnergySystem.name.asc())
        .all()
    )


@lru_cache(maxsize=1)
def get_regional_energy_system_list():
    """Получает список региональных энергосистем (кроме "не указано")."""
    query = (
        RegionalEnergySystem.query
        .filter(RegionalEnergySystem.id.isnot(None), RegionalEnergySystem.id > 0)
        .order_by(RegionalEnergySystem.name.asc())
    )
    return query


def get_regional_energy_systems_list() -> List[RegionalEnergySystem]:
    """Возвращает список ORM-объектов РЭС с заранее загруженной ОЭС."""
    return (
        RegionalEnergySystem.query
        .options(
            selectinload(RegionalEnergySystem.union_energy_system)
            .load_only(UnionEnergySystem.id, UnionEnergySystem.name)
        )
        .order_by(RegionalEnergySystem.id)
        .all()
    )

# 2) DTO-список для шаблонов (плоские dict'ы)
def get_regional_energy_systems_dto_list() -> List[dict]:
    """Возвращает список dict: {id, name, union_energy_system_id, union_energy_system_name}."""
    rows = get_regional_energy_systems_list()
    return [
        {
            "id": r.id,
            "name": r.name,
            "union_energy_system_id": r.id_union_energy_system,
            "union_energy_system_name": r.union_energy_system.name if r.union_energy_system else None,
        }
        for r in rows
    ]

# 3) Карта {res_id: name_full} — лёгкий lookup (кэшируется)
@lru_cache(maxsize=1)
def get_regional_energy_systems_map() -> Dict[int, str]:
    """Возвращает отображение {РЭС.id: РЭС.name_full} (кэшируется)."""
    rows = (
        RegionalEnergySystem.query
        .with_entities(RegionalEnergySystem.id, RegionalEnergySystem.name_full)
        .order_by(RegionalEnergySystem.id)
        .all()
    )
    return {id_: name_full for id_, name_full in rows}


# 4) Обратная/прямая связи с ОЭС — часто нужны вместе с РЭС
@lru_cache(maxsize=1)
def get_res_to_ues_id_map() -> Dict[int, int]:
    """Возвращает отображение {РЭС.id: ОЭС.id} (кэшируется)."""
    rows = (
        RegionalEnergySystem.query
        .with_entities(RegionalEnergySystem.id, RegionalEnergySystem.id_union_energy_system)
        .filter(RegionalEnergySystem.id_union_energy_system.isnot(None))
        .all()
    )
    return {res_id: ues_id for res_id, ues_id in rows}


@lru_cache(maxsize=1)
def get_ues_to_res_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ОЭС.id: [РЭС.id, ...]} (кэшируется)."""
    rows = (
        RegionalEnergySystem.query
        .with_entities(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id)
        .order_by(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id)
        .all()
    )
    acc: Dict[int, List[int]] = {}
    for ues_id, res_id in rows:
        if ues_id is None:
            continue
        acc.setdefault(ues_id, []).append(res_id)
    return acc


def invalidate_res_lookups_cache() -> None:
    get_regional_energy_systems_map.cache_clear()
    get_res_to_ues_id_map.cache_clear()
    get_ues_to_res_ids_map.cache_clear()


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