"""Сервисный get-модуль для EnergySystemType."""

from app.extensions import db
from typing import Union, List, Dict
from functools import lru_cache
from collections import defaultdict

# Модели
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system

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


@lru_cache(maxsize=1)
def get_est_to_ues_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ТипЭС.id: [ОЭС.id, ...]} (кэшируется)."""
    current_version = get_current_version()
    query = db.session.query(UnionEnergySystem.id_energy_system_type, UnionEnergySystem.id)
    
    if current_version:
        query = query.filter(UnionEnergySystem.database_version_id == current_version)
    
    rows = query.filter(UnionEnergySystem.id_energy_system_type.isnot(None)).all()
    acc: Dict[int, List[int]] = defaultdict(list)
    for est_id, ues_id in rows:
        acc[est_id].append(ues_id)
    return dict(acc)


@lru_cache(maxsize=1)
def get_est_to_res_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ТипЭС.id: [РЭС.id, ...]} через ОЭС (кэшируется)."""
    current_version = get_current_version()
    # Сначала получаем ОЭС по типу, затем РЭС по ОЭС
    est_to_ues = get_est_to_ues_ids_map()
    ues_to_res_query = db.session.query(
        UnionEnergySystem.id,
        RegionalEnergySystem.id
    ).join(
        RegionalEnergySystem,
        UnionEnergySystem.id == RegionalEnergySystem.id_union_energy_system
    )
    
    if current_version:
        ues_to_res_query = ues_to_res_query.filter(
            UnionEnergySystem.database_version_id == current_version,
            RegionalEnergySystem.database_version_id == current_version
        )
    
    ues_to_res_rows = ues_to_res_query.filter(
        RegionalEnergySystem.id_union_energy_system.isnot(None)
    ).all()
    
    ues_to_res = defaultdict(list)
    for ues_id, res_id in ues_to_res_rows:
        ues_to_res[ues_id].append(res_id)
    
    # Теперь строим est -> res
    acc: Dict[int, List[int]] = defaultdict(list)
    for est_id, ues_ids in est_to_ues.items():
        for ues_id in ues_ids:
            if ues_id in ues_to_res:
                acc[est_id].extend(ues_to_res[ues_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


@lru_cache(maxsize=1)
def get_est_to_rd_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ТипЭС.id: [СубъектРФ.id, ...]} через РЭС (кэшируется)."""
    current_version = get_current_version()
    est_to_res = get_est_to_res_ids_map()
    
    # Получаем связь РЭС -> Субъект РФ через M2M таблицу
    res_to_rd_query = db.session.query(
        regional_district_regional_energy_system.c.regional_energy_system_id,
        regional_district_regional_energy_system.c.regional_district_id
    )
    
    res_to_rd_rows = res_to_rd_query.all()
    res_to_rd = defaultdict(list)
    for res_id, rd_id in res_to_rd_rows:
        res_to_rd[res_id].append(rd_id)
    
    # Строим est -> rd
    acc: Dict[int, List[int]] = defaultdict(list)
    for est_id, res_ids in est_to_res.items():
        for res_id in res_ids:
            if res_id in res_to_rd:
                acc[est_id].extend(res_to_rd[res_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


@lru_cache(maxsize=1)
def get_est_to_fd_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {ТипЭС.id: [ФО.id, ...]} через Субъект РФ (кэшируется)."""
    current_version = get_current_version()
    est_to_rd = get_est_to_rd_ids_map()
    
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
    
    # Строим est -> fd
    acc: Dict[int, List[int]] = defaultdict(list)
    for est_id, rd_ids in est_to_rd.items():
        for rd_id in rd_ids:
            if rd_id in rd_to_fd:
                acc[est_id].append(rd_to_fd[rd_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}
