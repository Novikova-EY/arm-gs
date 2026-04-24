"""Сервисный get-модуль для UnionEnergySystem."""

from app.extensions import db
from functools import lru_cache
from collections import defaultdict
from typing import Union, List, Dict
from sqlalchemy.orm import selectinload, load_only

# Модели
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

# Сервисы
from app.common.services.database_version_services import get_current_version


def get_union_energy_system_list_full():
    """Получает полный список ОЭС. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = UnionEnergySystem.query
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    return (
        query
        .order_by(
            (UnionEnergySystem.display_order.is_(None)),
            UnionEnergySystem.display_order.asc(),
            (UnionEnergySystem.id != 0),
            UnionEnergySystem.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_union_energy_system_list():
    """Получает список ОЭС (кроме "не указано")."""
    current_version = get_current_version()
    query = UnionEnergySystem.query
    
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    
    return (
        query
        .filter(UnionEnergySystem.id.isnot(None), UnionEnergySystem.id > 0)
        .order_by(
            UnionEnergySystem.display_order.asc().nullslast(),
            UnionEnergySystem.name.asc(),
            UnionEnergySystem.id.asc(),
        )
    )


def get_union_energy_systems_list() -> List[UnionEnergySystem]:
    """Возвращает список ОЭС с заранее загруженными региональными энергосистемами."""
    current_version = get_current_version()
    query = UnionEnergySystem.query
    
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    
    return (
        query
        .options(
            selectinload(UnionEnergySystem.regional_energy_systems)
            .load_only(RegionalEnergySystem.id, RegionalEnergySystem.name)
        )
        .order_by(
            UnionEnergySystem.display_order.asc().nullslast(),
            UnionEnergySystem.name.asc(),
            UnionEnergySystem.id.asc(),
        )
        .all()
    )


def get_union_energy_systems_map() -> Dict[int, str]:
    """Возвращает отображение {ОЭС.id: ОЭС.name}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = UnionEnergySystem.query.with_entities(UnionEnergySystem.id, UnionEnergySystem.name)
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    rows = query.order_by(UnionEnergySystem.id).all()
    return {id_: name for id_, name in rows}


def get_union_energy_system_display_order_map() -> Dict[int, int | None]:
    """Возвращает отображение {ОЭС.id: ОЭС.display_order}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = UnionEnergySystem.query.with_entities(
        UnionEnergySystem.id,
        UnionEnergySystem.display_order,
    )
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    rows = query.order_by(UnionEnergySystem.id).all()
    return {id_: display_order for id_, display_order in rows}


def union_energy_system_hierarchy_sort_key(
    ues_id: int,
    ues_names: Dict[int, str],
    ues_display_orders: Dict[int, int | None],
) -> tuple:
    """
    Ключ сортировки ОЭС для иерархии ЕЭС → ОЭС → РЭС (порядок как в справочнике ОЭС):
    display_order, затем имя; «Не указано» и записи без номера порядка — в конце.
    """
    display_order = ues_display_orders.get(ues_id)
    return (
        1 if ues_id == -1 else 0,
        1 if display_order is None else 0,
        display_order if display_order is not None else 10**9,
        (ues_names.get(ues_id) or "").strip().lower(),
        ues_id,
    )


def get_ues_to_res_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ОЭС.id: [РЭС.id, ...]}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = db.session.query(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id)
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    pairs = query.order_by(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id).all()
    acc: dict[int, list[int]] = defaultdict(list)
    for ues_id, res_id in pairs:
        if ues_id is not None:
            acc[ues_id].append(res_id)
    return dict(acc)


def get_res_to_ues_id_map() -> Dict[int, int]:
    """Возвращает отображение {РЭС.id: ОЭС.id}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = db.session.query(RegionalEnergySystem.id, RegionalEnergySystem.id_union_energy_system)
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    pairs = query.filter(RegionalEnergySystem.id_union_energy_system.isnot(None)).all()
    return {res_id: ues_id for res_id, ues_id in pairs}


def invalidate_ues_lookups_cache() -> None:
    get_ues_to_est_id_map.cache_clear()
    get_ues_to_rd_ids_map.cache_clear()
    get_ues_to_fd_ids_map.cache_clear()


@lru_cache(maxsize=1)
def get_ues_to_est_id_map() -> Dict[int, int]:
    """Возвращает отображение {ОЭС.id: ТипЭС.id} (кэшируется)."""
    current_version = get_current_version()
    query = db.session.query(UnionEnergySystem.id, UnionEnergySystem.id_energy_system_type)
    
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    
    rows = query.filter(UnionEnergySystem.id_energy_system_type.isnot(None)).all()
    return {ues_id: est_id for ues_id, est_id in rows}


@lru_cache(maxsize=1)
def get_ues_to_rd_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ОЭС.id: [СубъектРФ.id, ...]} через РЭС (кэшируется).

    ВАЖНО: M2M-таблица RegionalDistrict<->RegionalEnergySystem не версионируется,
    поэтому при построении маппинга нужно фильтровать по версии через join'ы.
    """
    ues_to_res = get_ues_to_res_ids_map()

    # Используем версионированный маппинг {РЭС.id: [СубъектРФ.id,...]}
    # (внутри он фильтрует по версии через join с таблицами-родителями).
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_res_to_rd_ids_map,
    )
    res_to_rd = get_res_to_rd_ids_map()

    acc: Dict[int, List[int]] = defaultdict(list)
    for ues_id, res_ids in ues_to_res.items():
        for res_id in res_ids:
            if res_id in res_to_rd:
                acc[ues_id].extend(res_to_rd[res_id])

    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


@lru_cache(maxsize=1)
def get_ues_to_fd_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ОЭС.id: [ФО.id, ...]} через Субъект РФ (кэшируется)."""
    current_version = get_current_version()
    ues_to_rd = get_ues_to_rd_ids_map()
    
    # Получаем связь Субъект РФ -> ФО
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    rd_to_fd_query = db.session.query(
        RegionalDistrict.id,
        RegionalDistrict.id_federal_district
    )
    
    if current_version:
        rd_to_fd_query = rd_to_fd_query.filter(RegionalDistrict.database_version_id == current_version)
    
    rd_to_fd_rows = rd_to_fd_query.filter(
        RegionalDistrict.id_federal_district.isnot(None)
    ).all()
    rd_to_fd = {rd_id: fd_id for rd_id, fd_id in rd_to_fd_rows}
    
    # Строим ues -> fd
    acc: Dict[int, List[int]] = defaultdict(list)
    for ues_id, rd_ids in ues_to_rd.items():
        for rd_id in rd_ids:
            if rd_id in rd_to_fd:
                acc[ues_id].append(rd_to_fd[rd_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}

    
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

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = UnionEnergySystem.query.filter(UnionEnergySystem.id.in_(ids))
    
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)