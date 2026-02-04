"""Сервисный get-модуль для RegionalEnergySystem."""

from functools import lru_cache
from sqlalchemy.orm import selectinload
from typing import Union, List, Dict
from collections import defaultdict
from app.extensions import db

# Модели
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system
from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Сервисы
from app.common.services.database_version_services import get_current_version


def get_regional_energy_system_choices():
    """Список (id, name) для выпадающих списков. Без кэша — версия БД берётся из текущего запроса (g.current_db_version)."""
    current_version = get_current_version()
    query = db.session.query(RegionalEnergySystem.id, RegionalEnergySystem.name)
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    return query.order_by(
        (RegionalEnergySystem.id != 0),
        RegionalEnergySystem.name.asc()
    ).all()


@lru_cache(maxsize=1)
def get_regional_energy_system_list_full():
    """Получает полный список региональных энергосистем с загруженными связями."""
    current_version = get_current_version()
    query = RegionalEnergySystem.query
    
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    
    return (
        query
        .options(
            selectinload(RegionalEnergySystem.union_energy_system)
            .selectinload(UnionEnergySystem.energy_system_type)
        )
        .order_by(
            (RegionalEnergySystem.id != 0),
            RegionalEnergySystem.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_regional_energy_system_list():
    """Получает список региональных энергосистем (кроме "не указано")."""
    current_version = get_current_version()
    query = RegionalEnergySystem.query
    
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    
    return (
        query
        .filter(RegionalEnergySystem.id.isnot(None), RegionalEnergySystem.id > 0)
        .order_by(RegionalEnergySystem.name.asc())
    )


def get_regional_energy_systems_list() -> List[RegionalEnergySystem]:
    """Возвращает список ORM-объектов РЭС с заранее загруженной ОЭС."""
    current_version = get_current_version()
    query = RegionalEnergySystem.query
    
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    
    return (
        query
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

# 3) Карта {res_id: name_full} — лёгкий lookup
def get_regional_energy_systems_map() -> Dict[int, str]:
    """Возвращает отображение {РЭС.id: РЭС.name_full}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = RegionalEnergySystem.query.with_entities(RegionalEnergySystem.id, RegionalEnergySystem.name_full)
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    rows = query.order_by(RegionalEnergySystem.id).all()
    return {id_: name_full for id_, name_full in rows}


# 4) Обратная/прямая связи с ОЭС — часто нужны вместе с РЭС
def get_res_to_ues_id_map() -> Dict[int, int]:
    """Возвращает отображение {РЭС.id: ОЭС.id}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = RegionalEnergySystem.query.with_entities(RegionalEnergySystem.id, RegionalEnergySystem.id_union_energy_system)
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    rows = query.filter(RegionalEnergySystem.id_union_energy_system.isnot(None)).all()
    return {res_id: ues_id for res_id, ues_id in rows}


def get_ues_to_res_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ОЭС.id: [РЭС.id, ...]}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = RegionalEnergySystem.query.with_entities(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id)
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    rows = query.order_by(RegionalEnergySystem.id_union_energy_system, RegionalEnergySystem.id).all()
    acc: Dict[int, List[int]] = {}
    for ues_id, res_id in rows:
        if ues_id is None:
            continue
        acc.setdefault(ues_id, []).append(res_id)
    return acc


def invalidate_res_lookups_cache() -> None:
    get_res_to_est_id_map.cache_clear()
    get_res_to_rd_ids_map.cache_clear()
    get_res_to_fd_ids_map.cache_clear()


def get_res_to_est_id_map() -> Dict[int, int]:
    """Возвращает отображение {РЭС.id: ТипЭС.id} через ОЭС. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    res_to_ues = get_res_to_ues_id_map()
    
    # Получаем связь ОЭС -> Тип ЭС
    ues_to_est_query = db.session.query(
        UnionEnergySystem.id,
        UnionEnergySystem.id_energy_system_type
    )
    
    if current_version:
        ues_to_est_query = ues_to_est_query.filter(UnionEnergySystem.database_version_id == current_version)
    
    ues_to_est_rows = ues_to_est_query.filter(
        UnionEnergySystem.id_energy_system_type.isnot(None)
    ).all()
    ues_to_est = {ues_id: est_id for ues_id, est_id in ues_to_est_rows}
    
    # Строим res -> est
    res_to_est = {}
    for res_id, ues_id in res_to_ues.items():
        if ues_id in ues_to_est:
            res_to_est[res_id] = ues_to_est[ues_id]
    
    return res_to_est


@lru_cache(maxsize=1)
def get_res_to_rd_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {РЭС.id: [СубъектРФ.id, ...]} через M2M (кэшируется)."""
    current_version = get_current_version()
    query = (
        db.session.query(
            regional_district_regional_energy_system.c.regional_energy_system_id,
            regional_district_regional_energy_system.c.regional_district_id,
        )
        .join(
            RegionalEnergySystem,
            RegionalEnergySystem.id == regional_district_regional_energy_system.c.regional_energy_system_id,
        )
        .join(
            RegionalDistrict,
            RegionalDistrict.id == regional_district_regional_energy_system.c.regional_district_id,
        )
    )

    # Важно: M2M-таблица не версионируется, поэтому фильтруем по версии через join'ы.
    if current_version:
        query = query.filter(
            RegionalEnergySystem.database_version_id == current_version,
            RegionalDistrict.database_version_id == current_version,
        )

    rows = query.all()
    acc: Dict[int, List[int]] = defaultdict(list)
    for res_id, rd_id in rows:
        acc[res_id].append(rd_id)
    return dict(acc)


@lru_cache(maxsize=1)
def get_res_to_fd_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {РЭС.id: [ФО.id, ...]} через Субъект РФ (кэшируется)."""
    current_version = get_current_version()
    res_to_rd = get_res_to_rd_ids_map()
    
    # Получаем связь Субъект РФ -> ФО
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
    
    # Строим res -> fd
    acc: Dict[int, List[int]] = defaultdict(list)
    for res_id, rd_ids in res_to_rd.items():
        for rd_id in rd_ids:
            if rd_id in rd_to_fd:
                acc[res_id].append(rd_to_fd[rd_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


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

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = RegionalEnergySystem.query.filter(RegionalEnergySystem.id.in_(ids))
    
    if current_version:
        query = query.filter(RegionalEnergySystem.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)