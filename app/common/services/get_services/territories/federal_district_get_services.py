"""Сервисный get-модуль для FederalDistrict."""

from app.extensions import db
from sqlalchemy.orm import selectinload
from functools import lru_cache
from typing import Union, List, Dict
from collections import defaultdict

# Модели
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem

# Сервисы
from app.common.services.database_version_services import get_current_version


def get_federal_district_list_full():
    """Получает полный список федеральных округов. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = FederalDistrict.query
    if current_version:
        query = query.filter(FederalDistrict.database_version_id == current_version)
    return (
        query
        .order_by(
            FederalDistrict.display_order.asc().nullslast(),
            FederalDistrict.name.asc(),
            FederalDistrict.id.asc(),
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_federal_district_list():
    """Получает список федеральных округов (кроме "не указано")."""
    current_version = get_current_version()
    query = FederalDistrict.query
    
    if current_version:
        query = query.filter(FederalDistrict.database_version_id == current_version)
    
    return (
        query
        .filter(FederalDistrict.id.isnot(None), FederalDistrict.id > 0)
        .order_by(
            FederalDistrict.display_order.asc().nullslast(),
            FederalDistrict.name.asc(),
            FederalDistrict.id.asc(),
        )
    )

def get_federal_districts_list() -> List[FederalDistrict]:
    """Возвращает список FederalDistrict с заранее загруженными субъектами РФ."""
    current_version = get_current_version()
    query = FederalDistrict.query
    
    if current_version:
        query = query.filter(FederalDistrict.database_version_id == current_version)
    
    return (
        query
        .options(
            selectinload(FederalDistrict.regional_districts)
            .load_only(RegionalDistrict.id, RegionalDistrict.name)
        )
        .order_by(
            FederalDistrict.display_order.asc().nullslast(),
            FederalDistrict.name.asc(),
            FederalDistrict.id.asc(),
        )
        .all()
    )

# 2) DTO-список для шаблонов (плоские dict'ы)
def get_federal_districts_dto_list() -> List[dict]:
    """Возвращает список dict: {id, name, regional_district_ids}."""
    rows = get_federal_districts_list()
    return [
        {
            "id": fd.id,
            "name": fd.name,
            "regional_district_ids": [rd.id for rd in fd.regional_districts] if fd.regional_districts else [],
        }
        for fd in rows
    ]

# 3) Карта {fd_id: fd_name} — лёгкий lookup (кэшируется)
@lru_cache(maxsize=1)
def get_federal_districts_map() -> Dict[int, str]:
    """Возвращает отображение {ФО.id: ФО.name} (кэшируется)."""
    current_version = get_current_version()
    query = FederalDistrict.query.with_entities(FederalDistrict.id, FederalDistrict.name)
    
    if current_version:
        query = query.filter(FederalDistrict.database_version_id == current_version)
    
    rows = query.order_by(FederalDistrict.id).all()
    return {id_: name for id_, name in rows}

# 4) Карта связей {fd_id: [regional_district_id, ...]} — без загрузки ORM-объектов
def get_fd_to_rd_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ФО.id: [СубъектРФ.id, ...]}. Без кэша — версия из текущего запроса."""
    current_version = get_current_version()
    query = db.session.query(RegionalDistrict.id_federal_district, RegionalDistrict.id)
    if current_version:
        query = query.filter(RegionalDistrict.database_version_id == current_version)
    rows = query.order_by(RegionalDistrict.id_federal_district, RegionalDistrict.id).all()
    acc: Dict[int, List[int]] = {}
    for fd_id, rd_id in rows:
        if fd_id is None:
            continue
        acc.setdefault(fd_id, []).append(rd_id)
    return acc

# 5) Обратная карта {regional_district_id: fd_id} (кэшируется)
@lru_cache(maxsize=1)
def get_regional_district_to_fd_id_map() -> Dict[int, int]:
    """Возвращает отображение {СубъектРФ.id: ФО.id} (кэшируется)."""
    rows = (
        db.session.query(RegionalDistrict.id, RegionalDistrict.id_federal_district)
        .filter(RegionalDistrict.id_federal_district.isnot(None))
        .all()
    )
    return {rd_id: fd_id for rd_id, fd_id in rows}

# 6) Инвалидатор кэшей — вызывай после CRUD по ФО/Субъектам РФ
def invalidate_fd_lookups_cache() -> None:
    get_federal_district_list.cache_clear()
    get_federal_districts_map.cache_clear()
    get_regional_district_to_fd_id_map.cache_clear()
    get_fd_to_res_ids_map.cache_clear()
    get_fd_to_ues_ids_map.cache_clear()
    get_fd_to_est_ids_map.cache_clear()


@lru_cache(maxsize=1)
def get_fd_to_res_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ФО.id: [РЭС.id, ...]} через Субъект РФ (кэшируется)."""
    current_version = get_current_version()
    fd_to_rd = get_fd_to_rd_ids_map()
    
    # Получаем связь Субъект РФ -> РЭС через M2M
    rd_to_res_query = db.session.query(
        regional_district_regional_energy_system.c.regional_district_id,
        regional_district_regional_energy_system.c.regional_energy_system_id
    )
    
    rd_to_res_rows = rd_to_res_query.all()
    rd_to_res = defaultdict(list)
    for rd_id, res_id in rd_to_res_rows:
        rd_to_res[rd_id].append(res_id)
    
    # Строим fd -> res
    acc: Dict[int, List[int]] = defaultdict(list)
    for fd_id, rd_ids in fd_to_rd.items():
        for rd_id in rd_ids:
            if rd_id in rd_to_res:
                acc[fd_id].extend(rd_to_res[rd_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


@lru_cache(maxsize=1)
def get_fd_to_ues_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ФО.id: [ОЭС.id, ...]} через РЭС (кэшируется)."""
    current_version = get_current_version()
    fd_to_res = get_fd_to_res_ids_map()
    
    # Получаем связь РЭС -> ОЭС
    res_to_ues_query = db.session.query(
        RegionalEnergySystem.id,
        RegionalEnergySystem.id_union_energy_system
    )
    
    if current_version:
        res_to_ues_query = res_to_ues_query.filter(RegionalEnergySystem.database_version_id == current_version)
    
    res_to_ues_rows = res_to_ues_query.filter(
        RegionalEnergySystem.id_union_energy_system.isnot(None)
    ).all()
    res_to_ues = {res_id: ues_id for res_id, ues_id in res_to_ues_rows}
    
    # Строим fd -> ues
    acc: Dict[int, List[int]] = defaultdict(list)
    for fd_id, res_ids in fd_to_res.items():
        for res_id in res_ids:
            if res_id in res_to_ues:
                acc[fd_id].append(res_to_ues[res_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


@lru_cache(maxsize=1)
def get_fd_to_est_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ФО.id: [ТипЭС.id, ...]} через ОЭС (кэшируется)."""
    current_version = get_current_version()
    fd_to_ues = get_fd_to_ues_ids_map()
    
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
    
    # Строим fd -> est
    acc: Dict[int, List[int]] = defaultdict(list)
    for fd_id, ues_ids in fd_to_ues.items():
        for ues_id in ues_ids:
            if ues_id in ues_to_est:
                acc[fd_id].append(ues_to_est[ues_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


def get_federal_district_name(federal_district_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами федеральных округов по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not federal_district_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(federal_district_ids, str):
        ids = [int(x) for x in federal_district_ids.split(",") if x.strip().isdigit()]
    elif isinstance(federal_district_ids, int):
        ids = [federal_district_ids]
    else:
        ids = [int(x) for x in federal_district_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = FederalDistrict.query.filter(FederalDistrict.id.in_(ids))
    
    if current_version:
        query = query.filter(FederalDistrict.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)