"""Сервисный get-модуль для RegionalDistrict."""

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

# Функции для работы с версионированием БД
from app.common.services.database_version_filter import filter_by_db_version
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_regional_district_list_full():
    """Получает полный список субъектов РФ."""
    query = RegionalDistrict.query
    # Фильтрация по версии БД
    query = filter_by_db_version(query, RegionalDistrict)
    # Извлекаем только нужные поля, чтобы избежать DetachedInstanceError
    # Преобразуем Row объекты в обычные кортежи для совместимости с WTForms
    rows = (
        query
        .with_entities(RegionalDistrict.id, RegionalDistrict.name)
        .order_by(RegionalDistrict.name.asc())
        .all()
    )
    return [(row.id, row.name) for row in rows]


@lru_cache(maxsize=1)
def get_regional_district_list():
    """Получает список субъектов РФ (кроме "не указано")."""
    current_version = get_current_version()
    query = RegionalDistrict.query
    
    if current_version:
        query = query.filter(RegionalDistrict.database_version_id == current_version)
    
    return (
        query
        .filter(RegionalDistrict.id.isnot(None), RegionalDistrict.id > 0)
        .order_by(RegionalDistrict.name.asc())
    )


def get_regional_districts_list() -> List[RegionalDistrict]:
    """Возвращает список ORM-объектов субъектов РФ с заранее загруженными ФО."""
    current_version = get_current_version()
    query = RegionalDistrict.query
    
    if current_version:
        query = query.filter(RegionalDistrict.database_version_id == current_version)
    
    return (
        query
        .options(
            selectinload(RegionalDistrict.federal_district)
            .load_only(FederalDistrict.id, FederalDistrict.name)
        )
        .order_by(RegionalDistrict.id)
        .all()
    )

# 2) DTO-список для шаблонов (плоские dict'ы)
def get_regional_districts_dto_list() -> List[dict]:
    """Возвращает список dict: {id, name, federal_district_id, federal_district_name}."""
    rows = get_regional_districts_list()
    return [
        {
            "id": rd.id,
            "name": rd.name,
            "federal_district_id": rd.id_federal_district,
            "federal_district_name": rd.federal_district.name if rd.federal_district else None,
        }
        for rd in rows
    ]

# 3) Lookup {rd_id: name} — лёгкий и кэшируемый
@lru_cache(maxsize=1)
def get_regional_districts_map() -> Dict[int, str]:
    """Возвращает отображение {Субъект.id: Субъект.name} (кэшируется)."""
    current_version = get_current_version()
    query = RegionalDistrict.query.with_entities(RegionalDistrict.id, RegionalDistrict.name)
    
    if current_version:
        query = query.filter(RegionalDistrict.database_version_id == current_version)
    
    rows = query.order_by(RegionalDistrict.id).all()
    return {id_: name for id_, name in rows}


# 4) Маппинг {rd_id: fd_id} — часто нужен для валидации/фильтров
@lru_cache(maxsize=1)
def get_rd_to_fd_id_map() -> Dict[int, int]:
    """Возвращает отображение {Субъект.id: ФО.id} (кэшируется)."""
    current_version = get_current_version()
    query = (
        RegionalDistrict.query
        .with_entities(RegionalDistrict.id, RegionalDistrict.id_federal_district)
        .filter(RegionalDistrict.id_federal_district.isnot(None))
    )
    if current_version:
        query = query.filter(RegionalDistrict.database_version_id == current_version)
    rows = query.all()
    return {rd_id: fd_id for rd_id, fd_id in rows}

# 5) Инвалидатор кэшей — вызывать после CRUD по субъектам/их привязке к ФО
def invalidate_regional_district_lookups_cache() -> None:
    get_regional_districts_map.cache_clear()
    get_rd_to_fd_id_map.cache_clear()
    get_rd_to_res_ids_map.cache_clear()
    get_rd_to_ues_ids_map.cache_clear()
    get_rd_to_est_ids_map.cache_clear()


@lru_cache(maxsize=1)
def get_rd_to_res_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {СубъектРФ.id: [РЭС.id, ...]} через M2M (кэшируется)."""
    current_version = get_current_version()
    query = (
        db.session.query(
            regional_district_regional_energy_system.c.regional_district_id,
            regional_district_regional_energy_system.c.regional_energy_system_id,
        )
        .join(
            RegionalDistrict,
            RegionalDistrict.id == regional_district_regional_energy_system.c.regional_district_id,
        )
        .join(
            RegionalEnergySystem,
            RegionalEnergySystem.id == regional_district_regional_energy_system.c.regional_energy_system_id,
        )
    )

    # Важно: M2M-таблица не версионируется, поэтому фильтруем по версии через join'ы.
    if current_version:
        query = query.filter(
            RegionalDistrict.database_version_id == current_version,
            RegionalEnergySystem.database_version_id == current_version,
        )

    rows = query.all()
    acc: Dict[int, List[int]] = defaultdict(list)
    for rd_id, res_id in rows:
        acc[rd_id].append(res_id)
    return dict(acc)


@lru_cache(maxsize=1)
def get_rd_to_ues_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {СубъектРФ.id: [ОЭС.id, ...]} через РЭС (кэшируется)."""
    current_version = get_current_version()
    rd_to_res = get_rd_to_res_ids_map()
    
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
    
    # Строим rd -> ues
    acc: Dict[int, List[int]] = defaultdict(list)
    for rd_id, res_ids in rd_to_res.items():
        for res_id in res_ids:
            if res_id in res_to_ues:
                acc[rd_id].append(res_to_ues[res_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


@lru_cache(maxsize=1)
def get_rd_to_est_ids_map() -> Dict[int, List[int]]:
    """Возвращает отображение {СубъектРФ.id: [ТипЭС.id, ...]} через ОЭС (кэшируется)."""
    current_version = get_current_version()
    rd_to_ues = get_rd_to_ues_ids_map()
    
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
    
    # Строим rd -> est
    acc: Dict[int, List[int]] = defaultdict(list)
    for rd_id, ues_ids in rd_to_ues.items():
        for ues_id in ues_ids:
            if ues_id in ues_to_est:
                acc[rd_id].append(ues_to_est[ues_id])
    
    # Убираем дубликаты
    return {k: list(set(v)) for k, v in acc.items()}


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

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = RegionalDistrict.query.filter(RegionalDistrict.id.in_(ids))
    
    if current_version:
        query = query.filter(RegionalDistrict.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)