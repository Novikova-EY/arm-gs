# -*- coding: utf-8 -*-
"""Helpers for stations_equipment_groups based on v2 equipment group models."""

from __future__ import annotations

from collections import defaultdict
import re

from sqlalchemy import or_, cast
from sqlalchemy.types import String
from sqlalchemy.orm import selectinload

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.get_services.years.years_get_services import (
    get_filter_start_year,
    get_filter_end_year,
)
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_model import EquipmentGroup


def get_standalone_equipment_group_ids(version_id=None, strict_version=False):
    """
    Возвращает множество ID групп оборудования (EquipmentGroup), не привязанных
    ни к одной станции (нет записей в EquipmentGroupSet).

    :param strict_version: если True, при выбранной версии только database_version_id == version_id.
    """
    from app.extensions import db

    if version_id is None:
        version_id = get_current_db_version_id()

    subq = (
        db.session.query(EquipmentGroupSet.equipment_group_id)
        .distinct()
    )
    q = db.session.query(EquipmentGroup.id).filter(
        ~EquipmentGroup.id.in_(subq)
    )
    if version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
    elif strict_version:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(or_(EquipmentGroup.database_version_id == version_id, EquipmentGroup.database_version_id.is_(None)))
    return {r[0] for r in q.all()}


def get_standalone_equipment_group_blocks(version_id=None):
    """
    Возвращает блоки для одиночных групп оборудования в формате, совместимом
    с reorganize_by_equipment_group_first: list of
    {equipment_group, rowspan, station_entries: [{station, station_rowspan, links: [{equipment_group_type, machines, rowspan}]}]}).
    Для одиночных групп: station=None, machines=[None] (одна строка для отображения).
    Для котельных в столбце «Станция» отображается «котельная».
    """
    from types import SimpleNamespace

    ids = get_standalone_equipment_group_ids(version_id)
    if not ids:
        return []

    groups = (
        EquipmentGroup.query.filter(EquipmentGroup.id.in_(ids))
        .options(
            selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroup.cities_external_mapping),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )
    # Сортируем по имени
    groups.sort(key=_equipment_group_sort_key)

    blocks = []
    for eg in groups:
        # Для standalone групп в столбце «Станция» отображается «котельная»
        dummy_station = SimpleNamespace(id=None, name="котельная")
        blocks.append({
            "equipment_group": eg,
            "rowspan": 1,
            "station_entries": [
                {
                    "station": dummy_station,
                    "station_rowspan": 1,
                    "links": [
                        {
                            "equipment_group_type": None,
                            "machines": [None],  # одна строка для отображения
                            "rowspan": 1,
                        }
                    ],
                }
            ],
            "has_multiple_equipment_group_set_station": False,
        })
    return blocks


def get_filtered_standalone_equipment_group_ids(filters, version_id=None, strict_version=False):
    """
    Возвращает ID standalone-групп (котельные и др.), отфильтрованных по
    территориальным атрибутам самой группы (obl, oes через external mapping).

    :param strict_version: если True, при выбранной версии показывать только группы
        с database_version_id == version_id (без legacy NULL). Для страницы
        stations_equipment_group_fuel_params.
    """
    from app.extensions import db
    from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
        UnionEnergySystemExternalMapping,
    )
    from app.refdata.models.energy_systems.union_energy_system_model import (
        UnionEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.common.services.database_version_filter import filter_by_explicit_db_version

    if version_id is None:
        version_id = get_current_db_version_id()

    _filters = {k: v for k, v in (filters or {}).items()
                if k not in ("page", "start_year", "end_year")}
    territorial_keys = (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    )
    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if not any(_filters.get(k) for k in territorial_keys) and not equipment_group_name_filter:
        return get_standalone_equipment_group_ids(version_id, strict_version=strict_version)

    subq = db.session.query(EquipmentGroupSet.equipment_group_id).distinct()
    q = (
        db.session.query(EquipmentGroup.id)
        .filter(~EquipmentGroup.id.in_(subq))
    )
    # Фильтр по версии: strict_version=True — только текущая (для fuel_params)
    if version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
    elif strict_version:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(or_(EquipmentGroup.database_version_id == version_id, EquipmentGroup.database_version_id.is_(None)))

    need_terr = (
        _filters.get("regional_energy_system_filter")
        or _filters.get("regional_district_filter")
        or _filters.get("federal_district_filter")
    )
    if need_terr:
        # Используем regional_district_id/regional_energy_system_id (заполняются при загрузке)
        if _filters.get("regional_energy_system_filter"):
            q = q.filter(
                EquipmentGroup.regional_energy_system_id.in_(
                    _filters["regional_energy_system_filter"]
                )
            )
        if _filters.get("regional_district_filter"):
            q = q.filter(
                EquipmentGroup.regional_district_id.in_(
                    _filters["regional_district_filter"]
                )
            )
        if _filters.get("federal_district_filter"):
            q = q.join(
                RegionalDistrict,
                EquipmentGroup.regional_district_id == RegionalDistrict.id,
            )
            q = q.filter(
                RegionalDistrict.id_federal_district.in_(
                    _filters["federal_district_filter"]
                )
            )

    if _filters.get("union_energy_system_filter") or _filters.get(
        "energy_system_type_filter"
    ):
        q = q.join(
            UnionEnergySystemExternalMapping,
            cast(EquipmentGroup.oes, String) == UnionEnergySystemExternalMapping.external_id,
        )
        q = q.join(
            UnionEnergySystem,
            UnionEnergySystemExternalMapping.union_energy_system_ref_uuid
            == UnionEnergySystem.ref_uuid,
        )
        q = filter_by_explicit_db_version(q, UnionEnergySystem, version_id)
        if _filters.get("union_energy_system_filter"):
            q = q.filter(
                UnionEnergySystem.id.in_(
                    _filters["union_energy_system_filter"]
                )
            )
        if _filters.get("energy_system_type_filter"):
            q = q.filter(
                UnionEnergySystem.id_energy_system_type.in_(
                    _filters["energy_system_type_filter"]
                )
            )

    # Фильтр по названию группы оборудования (для котельных и др. standalone)
    if equipment_group_name_filter:
        pattern = f"%{equipment_group_name_filter}%"
        q = q.filter(
            or_(
                EquipmentGroup.name.ilike(pattern),
                EquipmentGroup.name_ext.ilike(pattern),
            )
        )

    return {r[0] for r in q.distinct().all()}


def get_filtered_equipment_group_ids_all(filters, version_id=None, strict_version=False):
    """
    EquipmentGroup-first: возвращает ID всех групп оборудования (и привязанных к станциям,
    и standalone), отфильтрованных по атрибутам самой EquipmentGroup.

    Фильтры: территориальные (EST, ОЭС, РЭС, ФО, субъект), название группы,
    тип станции ТЭС (для привязанных групп — только если станция ТЭС; standalone всегда включаются).
    """
    from app.extensions import db
    from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
        UnionEnergySystemExternalMapping,
    )
    from app.refdata.models.energy_systems.union_energy_system_model import (
        UnionEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.generation.models.station.station_model import Station

    if version_id is None:
        version_id = get_current_db_version_id()

    _filters = {k: v for k, v in (filters or {}).items()
                if k not in ("page", "start_year", "end_year")}

    # Базовый запрос: все EquipmentGroup (без ограничения standalone)
    q = db.session.query(EquipmentGroup.id)
    if version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
    elif strict_version:
        q = q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        q = q.filter(or_(
            EquipmentGroup.database_version_id == version_id,
            EquipmentGroup.database_version_id.is_(None),
        ))

    # Территориальные фильтры
    need_terr = (
        _filters.get("regional_energy_system_filter")
        or _filters.get("regional_district_filter")
        or _filters.get("federal_district_filter")
    )
    if need_terr:
        if _filters.get("regional_energy_system_filter"):
            q = q.filter(
                EquipmentGroup.regional_energy_system_id.in_(
                    _filters["regional_energy_system_filter"]
                )
            )
        if _filters.get("regional_district_filter"):
            q = q.filter(
                EquipmentGroup.regional_district_id.in_(
                    _filters["regional_district_filter"]
                )
            )
        if _filters.get("federal_district_filter"):
            q = q.join(
                RegionalDistrict,
                EquipmentGroup.regional_district_id == RegionalDistrict.id,
            )
            q = q.filter(
                RegionalDistrict.id_federal_district.in_(
                    _filters["federal_district_filter"]
                )
            )

    if _filters.get("union_energy_system_filter") or _filters.get("energy_system_type_filter"):
        q = q.join(
            UnionEnergySystemExternalMapping,
            cast(EquipmentGroup.oes, String) == UnionEnergySystemExternalMapping.external_id,
        )
        q = q.join(
            UnionEnergySystem,
            UnionEnergySystemExternalMapping.union_energy_system_ref_uuid
            == UnionEnergySystem.ref_uuid,
        )
        q = filter_by_explicit_db_version(q, UnionEnergySystem, version_id)
        if _filters.get("union_energy_system_filter"):
            q = q.filter(
                UnionEnergySystem.id.in_(
                    _filters["union_energy_system_filter"]
                )
            )
        if _filters.get("energy_system_type_filter"):
            q = q.filter(
                UnionEnergySystem.id_energy_system_type.in_(
                    _filters["energy_system_type_filter"]
                )
            )

    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if equipment_group_name_filter:
        pattern = f"%{equipment_group_name_filter}%"
        q = q.filter(
            or_(
                EquipmentGroup.name.ilike(pattern),
                EquipmentGroup.name_ext.ilike(pattern),
            )
        )

    territorial_ids = {r[0] for r in q.distinct().all()}

    # Фильтр по типу станции ТЭС: оставляем группы, привязанные к ТЭС, или standalone
    station_type_filter = _filters.get("station_type_filter")
    if not station_type_filter:
        return territorial_ids

    subq_linked = (
        db.session.query(EquipmentGroupSet.equipment_group_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .filter(Station.id_station_type.in_(station_type_filter))
        .distinct()
    )
    ids_linked_to_tes = {r[0] for r in subq_linked.all()}
    standalone_ids = get_standalone_equipment_group_ids(version_id, strict_version=strict_version)
    allowed_ids = ids_linked_to_tes | standalone_ids
    return territorial_ids & allowed_ids


def _version_filter_with_legacy(query, model_class):
    """
    Добавляет фильтр по версии БД с учётом legacy (как _filter_by_version_with_fallback):
    при текущей версии — включаем и текущую версию, и записи без версии (NULL).
    """
    version_id = get_current_db_version_id()
    if not hasattr(model_class, "database_version_id"):
        return query
    col = model_class.database_version_id
    if version_id is None:
        return query.filter(col.is_(None))
    return query.filter(or_(col == version_id, col.is_(None)))


def get_equipment_group_ids_for_stations(station_ids):
    """
    Возвращает множество ID групп оборудования (EquipmentGroup), связанных
    со станциями через EquipmentGroupSet -> EquipmentGroupSetStation.
    """
    if not station_ids:
        return set()
    from app.extensions import db

    q = (
        db.session.query(EquipmentGroup.id)
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(EquipmentGroupSetStation.station_id.in_(station_ids))
    )
    q = _version_filter_with_legacy(q, EquipmentGroupSetStation)
    q = _version_filter_with_legacy(q, EquipmentGroup)
    return {r[0] for r in q.distinct().all()}


def get_filtered_equipment_group_ids(filters, start_year=None, end_year=None):
    """
    Возвращает множество ID групп оборудования (EquipmentGroup), соответствующих
    применяемым фильтрам станций. Список формируется по модели EquipmentGroup
    через связь EquipmentGroupSet -> EquipmentGroupSetStation -> Station.

    Учитывает database_version_id с fallback на legacy (NULL), как в
    build_station_equipment_groups_v2.
    """
    from app.generation.services.station_services.station_services import get_stations_list

    _start = start_year if start_year is not None else get_filter_start_year()
    _end = end_year if end_year is not None else get_filter_end_year()

    _filters = {k: v for k, v in (filters or {}).items()
                if k not in ("page", "start_year", "end_year")}
    result = get_stations_list(
        page=1,
        per_page=1,
        start_year=_start,
        end_year=_end,
        return_ids_only=True,
        **_filters,
    )
    station_ids = result.get("station_ids") or []
    if not station_ids:
        return set()

    from app.extensions import db

    # ID берутся из EquipmentGroup (модель — источник)
    # Фильтр по версии с учётом legacy (как build_station_equipment_groups_v2)
    q = (
        db.session.query(EquipmentGroup.id)
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .filter(EquipmentGroupSetStation.station_id.in_(station_ids))
    )
    q = _version_filter_with_legacy(q, EquipmentGroupSetStation)
    q = _version_filter_with_legacy(q, EquipmentGroup)

    # Фильтр по названию группы оборудования
    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if equipment_group_name_filter:
        pattern = f"%{equipment_group_name_filter}%"
        q = q.filter(
            or_(
                EquipmentGroup.name.ilike(pattern),
                EquipmentGroup.name_ext.ilike(pattern),
            )
        )

    rows = q.distinct().all()
    return {r[0] for r in rows}


def _is_current_version(entity, current_version_id) -> bool:
    if entity is None:
        return False
    if not hasattr(entity, "database_version_id"):
        return True
    if current_version_id is None:
        return entity.database_version_id is None
    return entity.database_version_id == current_version_id


def _filter_by_version_with_fallback(items, current_version_id):
    """
    Возвращает элементы текущей версии, а если их нет — элементы без версии (legacy).
    """
    if not items:
        return []
    if current_version_id is None:
        return [i for i in items if getattr(i, "database_version_id", None) is None]
    current_items = [
        i for i in items if getattr(i, "database_version_id", None) == current_version_id
    ]
    if current_items:
        return current_items
    return [i for i in items if getattr(i, "database_version_id", None) is None]


def get_station_equipment_group_name_map(station_ids):
    """
    Возвращает dict[(station_id, equipment_group_type_id)] -> EquipmentGroup (fuel)
    для отображения EquipmentGroup.name вместо EquipmentGroupType.name.
    """
    if not station_ids:
        return {}
    current_version_id = get_current_db_version_id()
    links = (
        EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id.in_(station_ids)
        )
        .options(
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group),
        )
        .all()
    )
    station_links = _filter_by_version_with_fallback(links, current_version_id)
    result = {}
    for link in station_links:
        group_links = [
            gl
            for gl in (link.equipment_group_links_v2 or [])
            if gl.equipment_group and _is_current_version(gl.equipment_group, current_version_id)
        ]
        if not group_links and current_version_id is not None:
            group_links = [
                gl
                for gl in (link.equipment_group_links_v2 or [])
                if gl.equipment_group and gl.equipment_group.database_version_id is None
            ]
        if group_links:
            key = (link.station_id, link.equipment_group_type_id)
            result[key] = group_links[0].equipment_group
    return result


def _machine_number_sort_key(machine) -> tuple:
    value = (machine.machine_number or "").strip()
    if not value:
        return (1, "", "")
    match = re.search(r"\d+", value)
    if match:
        return (0, int(match.group(0)), value)
    return (1, value, value)


def _equipment_group_sort_key(group: EquipmentGroup | None) -> tuple:
    if group is None:
        return (1, "", 0)
    name = (group.name or group.name_ext or "").strip().lower()
    return (0, name, group.id or 0)


def _is_koitelny_station(station) -> bool:
    """Станция котельная или standalone (id=None)."""
    if station is None:
        return True
    sid = getattr(station, "id", None)
    if sid is None:
        return True
    name = (getattr(station, "name", None) or "").strip().lower()
    return "котельн" in (name or "")


def _group_block_koitelny_sort_key(block) -> tuple:
    """Ключ сортировки: котельные группы в конце."""
    entries = block.get("station_entries") or []
    all_koitelny = all(
        _is_koitelny_station(se.get("station")) for se in entries
    ) if entries else False
    return (1 if all_koitelny else 0, _equipment_group_sort_key(block.get("equipment_group")))


def _equipment_group_type_sort_key(group_type) -> tuple:
    if group_type is None:
        return (1, 10**9, "")
    display_order = (
        group_type.display_order
        if getattr(group_type, "display_order", None) is not None
        else 10**9
    )
    name = (group_type.name or "").strip().lower()
    return (0, display_order, name)


def build_station_equipment_groups_v2(stations, filters=None, start_year=None, end_year=None):
    """
    Builds v2 equipment-group tree per station.

    Список групп оборудования формируется по модели EquipmentGroup с учётом
    применяемых фильтров (если filters передан).

    Result: dict[station_id] = {"groups": [..], "total_rows": int}
    Each group: {"equipment_group": EquipmentGroup|None, "links": [...], "rowspan": int}
    Each link: {"link": EquipmentGroupSetStation|None, "equipment_group_type": obj|None,
                "machines": list, "rowspan": int}
    """
    station_ids = [s.id for s in (stations or []) if getattr(s, "id", None)]
    if not station_ids:
        return {}

    filtered_equipment_group_ids = None
    if filters:
        filtered_equipment_group_ids = get_filtered_equipment_group_ids(
            filters, start_year=start_year, end_year=end_year
        )

    current_version_id = get_current_db_version_id()

    links = (
        EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id.in_(station_ids)
        )
        .options(
            selectinload(EquipmentGroupSetStation.equipment_group_type),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroupSetStation.equipment_group_links_v2)
            .selectinload(EquipmentGroupSet.equipment_group)
            .selectinload(EquipmentGroup.cities_external_mapping),
        )
        .all()
    )

    links_by_station = defaultdict(list)
    links_by_station_raw = defaultdict(list)
    for link in links:
        links_by_station_raw[link.station_id].append(link)

    for station_id, station_links in links_by_station_raw.items():
        station_links = _filter_by_version_with_fallback(station_links, current_version_id)
        for link in station_links:
            group_links = [
                gl
                for gl in (link.equipment_group_links_v2 or [])
                if gl.equipment_group and _is_current_version(gl.equipment_group, current_version_id)
            ]
            if not group_links and current_version_id is not None:
                group_links = [
                    gl
                    for gl in (link.equipment_group_links_v2 or [])
                    if gl.equipment_group and gl.equipment_group.database_version_id is None
                ]
            if not group_links:
                links_by_station[station_id].append(
                    {"equipment_group": None, "link": link}
                )
                continue
            for gl in group_links:
                links_by_station[station_id].append(
                    {"equipment_group": gl.equipment_group, "link": link}
                )

    from app.generation.services.station_services.station_services import _apply_machine_display_names

    result = {}
    for station in stations:
        machines = [
            m
            for m in (station.machines or [])
            if current_version_id is None
            or getattr(m, "database_version_id", None) == current_version_id
        ]
        _apply_machine_display_names(machines)
        machines_by_type = defaultdict(list)
        machines_without_type = []
        for machine in machines:
            if machine.id_equipment_group is None:
                machines_without_type.append(machine)
            else:
                machines_by_type[machine.id_equipment_group].append(machine)

        for group_list in machines_by_type.values():
            group_list.sort(key=_machine_number_sort_key)
        machines_without_type.sort(key=_machine_number_sort_key)

        group_nodes = {}
        type_ids_with_links = set()
        for entry in links_by_station.get(station.id, []):
            link = entry["link"]
            type_id = link.equipment_group_type_id
            machine_list = machines_by_type.get(type_id, [])
            if not machine_list:
                continue
            group = entry["equipment_group"]
            if filtered_equipment_group_ids is not None and group is not None:
                if group.id not in filtered_equipment_group_ids:
                    continue
            type_ids_with_links.add(type_id)
            group_key = group.id if group else None
            node = group_nodes.setdefault(
                group_key, {"equipment_group": group, "links": []}
            )
            node["links"].append(
                {
                    "link": link,
                    "equipment_group_type": link.equipment_group_type,
                    "machines": machine_list,
                }
            )

        missing_type_ids = [
            type_id for type_id in machines_by_type.keys() if type_id not in type_ids_with_links
        ]
        if missing_type_ids or machines_without_type:
            node = group_nodes.setdefault(None, {"equipment_group": None, "links": []})
            for type_id in missing_type_ids:
                machine_list = machines_by_type.get(type_id, [])
                if not machine_list:
                    continue
                node["links"].append(
                    {
                        "link": None,
                        "equipment_group_type": machine_list[0].equipment_group
                        if machine_list
                        else None,
                        "machines": machine_list,
                    }
                )
            if machines_without_type:
                node["links"].append(
                    {
                        "link": None,
                        "equipment_group_type": None,
                        "machines": machines_without_type,
                    }
                )

        groups_sorted = sorted(
            group_nodes.values(), key=lambda item: _equipment_group_sort_key(item["equipment_group"])
        )
        total_rows = 0
        for group in groups_sorted:
            group["links"].sort(
                key=lambda item: _equipment_group_type_sort_key(item["equipment_group_type"])
            )
            group_rowspan = 0
            for link in group["links"]:
                link_rows = max(1, len(link["machines"]))
                link["rowspan"] = link_rows
                group_rowspan += link_rows
            group["rowspan"] = group_rowspan
            total_rows += group_rowspan

        result[station.id] = {"groups": groups_sorted, "total_rows": total_rows}

    return result


def _station_sort_key(station) -> tuple:
    """
    Sort key for stations: по столбцу «Станция» (название), котельные и standalone — в конце.
    """
    if station is None:
        return (2, "", 0)
    name = (getattr(station, "name") or "").strip().lower()
    sid = getattr(station, "id", 0) or 0
    # Standalone (id=None) — в самом конце; котельные — перед standalone
    if sid is None:
        return (2, name, 0)
    if "котельн" in (name or ""):
        return (1, name, sid)
    return (0, name, sid)


def reorganize_by_equipment_group_first(stations, v2_groups_map):
    """
    Reorganizes per-station equipment groups into equipment-group-first structure.

    Иерархия: EquipmentGroup -> Station (через EquipmentGroupSet) -> EquipmentGroupType -> Machines

    Returns: list of blocks, each:
        {
            "equipment_group": EquipmentGroup|None,
            "rowspan": int,
            "station_entries": [
                {
                    "station": Station,
                    "station_rowspan": int,
                    "links": [{"equipment_group_type": obj, "machines": list, "rowspan": int}, ...]
                },
                ...
            ]
        }
    """
    if not stations:
        return []

    # Collect (equipment_group, station, link_item) from all stations
    all_entries = []
    for station in stations:
        groups = (v2_groups_map.get(station.id) or {}).get("groups", [])
        for group in groups:
            group_entity = group.get("equipment_group")
            for link_item in group.get("links", []):
                all_entries.append((group_entity, station, link_item))

    # Sort by equipment_group, then station, then equipment_group_type
    all_entries.sort(key=lambda x: (
        _equipment_group_sort_key(x[0]),
        _station_sort_key(x[1]),
        _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
    ))

    # Group by equipment_group (use id for grouping - None for null group)
    from itertools import groupby

    def _group_key(entry):
        eg = entry[0]
        return eg.id if eg else -1

    blocks = []
    for _eg_id, grp in groupby(all_entries, key=_group_key):
        entries = list(grp)
        eq_group = entries[0][0] if entries else None
        # Group by station within this equipment_group
        station_entries = []
        for station_id, st_iter in groupby(entries, key=lambda x: x[1].id):
            st_list = list(st_iter)
            station = st_list[0][1]
            links_data = []
            station_rowspan = 0
            for _, _, link_item in st_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                station_rowspan += rowspan
            station_entries.append({
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links_data,
            })

        total_rowspan = sum(se["station_rowspan"] for se in station_entries)
        distinct_station_keys = {
            _station_identity_key(se.get("station"))
            for se in station_entries
        }
        has_multiple_eg_set_station = len(distinct_station_keys) > 1
        blocks.append({
            "equipment_group": eq_group,
            "rowspan": total_rowspan,
            "station_entries": station_entries,
            "has_multiple_equipment_group_set_station": has_multiple_eg_set_station,
        })

    return blocks


def build_equipment_group_blocks_aggregation(blocks, regional_energy_system_names=None):
    """
    Строит данные для агрегационных строк «РЭС X, всего» по EquipmentGroup.regional_energy_system_id.
    Блоки группируются по РЭС группы оборудования, а не по ключу иерархии станций.

    :param blocks: список блоков из build_equipment_group_blocks_from_model
    :param regional_energy_system_names: dict[res_id, name] для подписей
    :return: dict с ключами:
        - last_row_index_by_res: dict[res_id, int] — индекс последней строки для каждой РЭС
        - res_aggregations: dict[res_id, {res_name, machine_count}]
        - rows_flat: list для согласования индексов (опционально)
    """
    res_names = regional_energy_system_names or {}
    rows_flat = []
    res_machine_counts = {}

    for block in blocks or []:
        eg = block.get("equipment_group")
        res_id = None
        if eg:
            res = getattr(eg, "regional_energy_system", None)
            res_id = res.id if res else getattr(eg, "regional_energy_system_id", None)
        res_id = res_id if res_id is not None else -1

        for station_entry in block.get("station_entries") or []:
            for link in station_entry.get("links") or []:
                machines = link.get("machines") or []
                for machine in (machines if machines else [None]):
                    rows_flat.append((block, station_entry, link, machine))
                    prev = res_machine_counts.get(res_id, {"res_name": res_names.get(res_id, "—"), "machine_count": 0})
                    res_machine_counts[res_id] = {
                        "res_name": prev["res_name"],
                        "machine_count": prev["machine_count"] + 1,
                    }

    last_row_index_by_res = {}
    for i, (block, _se, _link, _machine) in enumerate(rows_flat):
        eg = block.get("equipment_group")
        res_id = -1
        if eg:
            res = getattr(eg, "regional_energy_system", None)
            res_id = res.id if res else getattr(eg, "regional_energy_system_id", None)
            res_id = res_id if res_id is not None else -1
        last_row_index_by_res[res_id] = i

    for res_id, data in res_machine_counts.items():
        data["res_name"] = res_names.get(res_id, "—") if res_id != -1 else "—"

    return {
        "last_row_index_by_res": last_row_index_by_res,
        "res_aggregations": res_machine_counts,
        "rows_flat": rows_flat,
    }


def build_equipment_group_items_with_aggregation(blocks, regional_energy_system_names=None):
    """
    Строит плоский список элементов (строки данных + агрегационные строки по РЭС)
    для отображения в шаблоне. Группировка по EquipmentGroup.regional_energy_system_id.

    :param blocks: список блоков из build_equipment_group_blocks_from_model
    :param regional_energy_system_names: dict[res_id, name] для подписей
    :return: list of dict с type: "row" | "res_summary"
    """
    agg = build_equipment_group_blocks_aggregation(blocks, regional_energy_system_names)
    last_idx = agg.get("last_row_index_by_res", {})
    res_aggs = agg.get("res_aggregations", {})
    rows_flat = agg.get("rows_flat", [])

    items = []
    for i, (block, station_entry, link, machine) in enumerate(rows_flat):
        items.append({
            "type": "row",
            "block": block,
            "station_entry": station_entry,
            "link": link,
            "machine": machine,
        })
        eg = block.get("equipment_group")
        res_id = -1
        if eg:
            res = getattr(eg, "regional_energy_system", None)
            res_id = res.id if res else getattr(eg, "regional_energy_system_id", None)
            res_id = res_id if res_id is not None else -1
        if last_idx.get(res_id) == i:
            data = res_aggs.get(res_id, {"res_name": "—", "machine_count": 0})
            items.append({
                "type": "res_summary",
                "res_name": data.get("res_name", "—"),
                "machine_count": data.get("machine_count", 0),
            })
    return items


def build_equipment_group_station_blocks(blocks):
    """
    Преобразует блоки EquipmentGroup -> Station -> Type -> Machines
    в структуру Station -> EquipmentGroup -> Type -> Machines.

    Используется для рендера страницы stations_equipment_groups с группировкой
    по EST -> UES -> РЭС, как на странице удельных показателей.
    """
    station_groups = {}

    for block in blocks or []:
        equipment_group = block.get("equipment_group")
        for station_entry in block.get("station_entries") or []:
            station = station_entry.get("station")
            station_key = (
                getattr(station, "id", None),
                (getattr(station, "name", None) or "—").strip().lower(),
            )
            station_bucket = station_groups.setdefault(
                station_key,
                {
                    "station": station,
                    "group_blocks": [],
                },
            )

            links = sorted(
                (station_entry.get("links") or []),
                key=lambda item: _equipment_group_type_sort_key(
                    item.get("equipment_group_type")
                ),
            )
            group_rowspan = station_entry.get("station_rowspan")
            if not group_rowspan:
                group_rowspan = sum(
                    max(1, len((link or {}).get("machines") or []))
                    for link in links
                ) or 1

            station_bucket["group_blocks"].append(
                {
                    "equipment_group": equipment_group,
                    "rowspan": group_rowspan,
                    "links": links,
                    "has_multiple_equipment_group_set_station": block.get(
                        "has_multiple_equipment_group_set_station", False
                    ),
                }
            )

    station_blocks = []
    for bucket in station_groups.values():
        group_blocks = sorted(
            bucket.get("group_blocks") or [],
            key=lambda item: _equipment_group_sort_key(item.get("equipment_group")),
        )
        station_rowspan = sum(
            max(1, item.get("rowspan") or 1) for item in group_blocks
        ) or 1
        station_blocks.append(
            {
                "station": bucket.get("station"),
                "rowspan": station_rowspan,
                "group_blocks": group_blocks,
            }
        )

    station_blocks.sort(key=lambda item: _station_sort_key(item.get("station")))
    return station_blocks


def _station_identity_key(station) -> tuple:
    return (
        getattr(station, "id", None),
        (getattr(station, "name", None) or "—").strip().lower(),
    )


def _normalize_group_block(block):
    station_entries = []
    total_rowspan = 0
    distinct_station_keys = set()

    for station_entry in block.get("station_entries") or []:
        station = station_entry.get("station")
        links = sorted(
            (station_entry.get("links") or []),
            key=lambda item: _equipment_group_type_sort_key(
                item.get("equipment_group_type")
            ),
        )
        station_rowspan = station_entry.get("station_rowspan")
        if not station_rowspan:
            station_rowspan = sum(
                max(1, len((link or {}).get("machines") or []))
                for link in links
            ) or 1

        station_entries.append(
            {
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links,
            }
        )
        total_rowspan += station_rowspan
        distinct_station_keys.add(_station_identity_key(station))

    station_entries.sort(key=lambda item: _station_sort_key(item.get("station")))
    return {
        "equipment_group": block.get("equipment_group"),
        "rowspan": total_rowspan or 1,
        "station_entries": station_entries,
        "has_multiple_equipment_group_set_station": len(distinct_station_keys) > 1,
    }


def split_equipment_group_blocks_for_display(blocks):
    """
    Делит блоки на:
    - station_blocks: группы, связанные только с одной станцией;
    - multi_station_group_blocks: группы, связанные с несколькими станциями;
    - boiler_station_blocks: котельные/standalone, которые всегда показываются в конце.
    """
    single_station_blocks = []
    multi_station_group_blocks = []
    boiler_blocks = []

    for raw_block in blocks or []:
        block = _normalize_group_block(raw_block)
        station_entries = block.get("station_entries") or []
        if not station_entries:
            continue

        if all(_is_koitelny_station(entry.get("station")) for entry in station_entries):
            boiler_blocks.append(block)
        elif block.get("has_multiple_equipment_group_set_station"):
            multi_station_group_blocks.append(block)
        else:
            single_station_blocks.append(block)

    multi_station_group_blocks.sort(
        key=lambda item: _equipment_group_sort_key(item.get("equipment_group"))
    )

    return {
        "station_blocks": build_equipment_group_station_blocks(single_station_blocks),
        "multi_station_group_blocks": multi_station_group_blocks,
        "boiler_station_blocks": build_equipment_group_station_blocks(boiler_blocks),
    }


def build_equipment_group_blocks_hierarchy(
    blocks_by_key,
    energy_system_type_names=None,
    union_energy_system_names=None,
    regional_energy_system_names=None,
):
    """
    Строит иерархию EST -> UES -> РЭС -> Station -> EquipmentGroup -> Type -> Machines
    по уже подготовленным блокам групп оборудования.
    """
    est_names = dict(energy_system_type_names or {})
    ues_names = dict(union_energy_system_names or {})
    res_names = dict(regional_energy_system_names or {})
    est_names[-1] = est_names.get(-1) or "Не указано"
    ues_names[-1] = ues_names.get(-1) or "Не указано"
    res_names[-1] = res_names.get(-1) or "Не указано"

    hierarchy = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for key, blocks in (blocks_by_key or {}).items():
        est_id, ues_id, res_id, _rd_id, _eu_id = key
        hierarchy[est_id][ues_id][res_id].extend(blocks or [])

    def _name_sort_key(entity_id, names_map):
        return (
            1 if entity_id == -1 else 0,
            (names_map.get(entity_id) or "").strip().lower(),
            entity_id,
        )

    hierarchy_flat = []
    for est_id in sorted(hierarchy.keys(), key=lambda item: _name_sort_key(item, est_names)):
        ues_list = []
        for ues_id in sorted(
            hierarchy[est_id].keys(),
            key=lambda item: _name_sort_key(item, ues_names),
        ):
            res_list = []
            for res_id in sorted(
                hierarchy[est_id][ues_id].keys(),
                key=lambda item: _name_sort_key(item, res_names),
            ):
                res_blocks = hierarchy[est_id][ues_id][res_id]
                display_blocks = split_equipment_group_blocks_for_display(
                    res_blocks or []
                )
                res_list.append(
                    {
                        "res_id": res_id,
                        "res_name": res_names.get(res_id, "—"),
                        "station_blocks": display_blocks.get("station_blocks", []),
                        "multi_station_group_blocks": display_blocks.get(
                            "multi_station_group_blocks", []
                        ),
                        "boiler_station_blocks": display_blocks.get(
                            "boiler_station_blocks", []
                        ),
                    }
                )
            ues_list.append(
                {
                    "ues_id": ues_id,
                    "ues_name": ues_names.get(ues_id, "—"),
                    "res_list": res_list,
                }
            )
        hierarchy_flat.append(
            {
                "est_id": est_id,
                "est_name": est_names.get(est_id, "—"),
                "ues_list": ues_list,
            }
        )

    return hierarchy_flat


def build_equipment_group_hierarchy_eg_first(
    filters=None,
    start_year=None,
    end_year=None,
    energy_system_type_names=None,
    union_energy_system_names=None,
    regional_energy_system_names=None,
):
    """
    EquipmentGroup-first: строит иерархию EST -> UES -> РЭС из групп оборудования.
    Фильтры применяются к EquipmentGroup, затем подтягиваются станции и агрегаты.
    """
    version_id = get_current_db_version_id()
    filtered_eg_ids = get_filtered_equipment_group_ids_all(
        filters, version_id=version_id, strict_version=False
    )
    if not filtered_eg_ids:
        return []

    standalone_ids = get_standalone_equipment_group_ids(version_id)
    linked_ids = filtered_eg_ids - standalone_ids
    filtered_standalone_ids = filtered_eg_ids & standalone_ids

    blocks = []
    if linked_ids:
        blocks.extend(
            build_equipment_group_blocks_from_eg_ids(
                linked_ids,
                filters=filters,
                start_year=start_year,
                end_year=end_year,
            )
        )
    if filtered_standalone_ids:
        standalone_blocks = get_standalone_equipment_group_blocks(version_id)
        blocks.extend(
            b for b in standalone_blocks
            if b.get("equipment_group") and b["equipment_group"].id in filtered_standalone_ids
        )

    # Как на stations_equipment_group_fuel_params: группы без rd/res идут в (-1,-1,-1,-1,-1)
    blocks_by_key = defaultdict(list)
    for block in blocks:
        eg = block.get("equipment_group")
        if not eg:
            continue
        rd = getattr(eg, "regional_district", None)
        res = getattr(eg, "regional_energy_system", None)
        ues = getattr(res, "union_energy_system", None) if res else None
        est = getattr(ues, "energy_system_type", None) if ues else None
        est_id = est.id if est else -1
        ues_id = ues.id if ues else -1
        res_id = res.id if res else -1
        rd_id = rd.id if rd else -1
        eu_id = rd_id
        key = (est_id, ues_id, res_id, rd_id, eu_id)
        blocks_by_key[key].append(block)

    return build_equipment_group_blocks_hierarchy(
        dict(blocks_by_key),
        energy_system_type_names=energy_system_type_names,
        union_energy_system_names=union_energy_system_names,
        regional_energy_system_names=regional_energy_system_names,
    )


def build_equipment_group_blocks_from_eg_ids(
    equipment_group_ids,
    filters=None,
    start_year=None,
    end_year=None,
):
    """
    EquipmentGroup-first: строит блоки по списку ID групп оборудования.
    Подтягивает все станции и агрегаты для каждой группы (без фильтра по станциям).

    :param equipment_group_ids: множество ID групп оборудования (EquipmentGroup)
    :return: list of blocks (формат как reorganize_by_equipment_group_first)
    """
    if not equipment_group_ids:
        return []

    from app.generation.models.station.station_model import Station

    current_version_id = get_current_db_version_id()

    equipment_groups = (
        EquipmentGroup.query.filter(EquipmentGroup.id.in_(equipment_group_ids))
        .options(
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.station).selectinload(Station.machines),
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.equipment_group_type),
            selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroup.cities_external_mapping),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    all_entries = []
    for eg in equipment_groups:
        for eg_set in (eg.equipment_group_links_v2 or []):
            eg_set_station = eg_set.equipment_group_set_station
            if not eg_set_station:
                continue
            station = eg_set_station.station
            equipment_group_type = eg_set_station.equipment_group_type
            if not station:
                continue
            if not _is_current_version(eg_set_station, current_version_id):
                continue
            if not _is_current_version(eg, current_version_id):
                if current_version_id is not None and eg.database_version_id is not None:
                    continue
            machines = [
                m
                for m in (station.machines or [])
                if m.id_equipment_group == eg_set_station.equipment_group_type_id
                and (
                    current_version_id is None
                    or getattr(m, "database_version_id", None) == current_version_id
                )
            ]
            machines.sort(key=_machine_number_sort_key)
            all_entries.append(
                (eg, station, {"equipment_group_type": equipment_group_type, "machines": machines})
            )

    all_entries.sort(
        key=lambda x: (
            _equipment_group_sort_key(x[0]),
            _station_sort_key(x[1]),
            _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
        )
    )

    from itertools import groupby

    def _group_key(entry):
        eg = entry[0]
        return eg.id if eg else -1

    blocks = []
    for _eg_id, grp in groupby(all_entries, key=_group_key):
        entries = list(grp)
        eq_group = entries[0][0] if entries else None
        station_entries = []
        for _st_id, st_iter in groupby(entries, key=lambda x: x[1].id):
            st_list = list(st_iter)
            station = st_list[0][1]
            links_data = []
            station_rowspan = 0
            for _, _, link_item in st_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                station_rowspan += rowspan
            station_entries.append({
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links_data,
            })
        total_rowspan = sum(se["station_rowspan"] for se in station_entries)
        distinct_station_keys = {
            _station_identity_key(se.get("station"))
            for se in station_entries
        }
        has_multiple_eg_set_station = len(distinct_station_keys) > 1
        blocks.append({
            "equipment_group": eq_group,
            "rowspan": total_rowspan,
            "station_entries": station_entries,
            "has_multiple_equipment_group_set_station": has_multiple_eg_set_station,
        })

    return blocks


def build_equipment_group_blocks_from_model(
    equipment_group_ids,
    stations,
    filters=None,
    start_year=None,
    end_year=None,
):
    """
    Строит блоки групп оборудования по модели EquipmentGroup.
    Данные по станциям и агрегатам подтягиваются из EquipmentGroupSet и Station.

    :param equipment_group_ids: множество ID групп оборудования (EquipmentGroup)
    :param stations: список станций (Station) для фильтрации
    :return: list of blocks (формат как reorganize_by_equipment_group_first)
    """
    if not equipment_group_ids or not stations:
        return []

    from app.generation.models.station.station_model import Station

    station_ids = {s.id for s in stations}
    current_version_id = get_current_db_version_id()

    equipment_groups = (
        EquipmentGroup.query.filter(EquipmentGroup.id.in_(equipment_group_ids))
        .options(
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.station).selectinload(Station.machines),
            selectinload(EquipmentGroup.equipment_group_links_v2).selectinload(
                EquipmentGroupSet.equipment_group_set_station
            ).selectinload(EquipmentGroupSetStation.equipment_group_type),
            selectinload(EquipmentGroup.regional_district),
            selectinload(EquipmentGroup.regional_energy_system),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.department_external_mapping),
            selectinload(EquipmentGroup.union_energy_system_external_mapping),
            selectinload(EquipmentGroup.economic_region_external_mapping),
            selectinload(EquipmentGroup.federal_district_external_mapping),
            selectinload(EquipmentGroup.business_unit_external_mapping),
            selectinload(EquipmentGroup.gen_company_external_mapping),
            selectinload(EquipmentGroup.gen_company_branch_external_mapping),
            selectinload(EquipmentGroup.cities_external_mapping),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    all_entries = []
    for eg in equipment_groups:
        for eg_set in (eg.equipment_group_links_v2 or []):
            eg_set_station = eg_set.equipment_group_set_station
            if not eg_set_station or eg_set_station.station_id not in station_ids:
                continue
            station = eg_set_station.station
            equipment_group_type = eg_set_station.equipment_group_type
            if not station:
                continue
            if not _is_current_version(eg_set_station, current_version_id):
                continue
            if not _is_current_version(eg, current_version_id):
                if current_version_id is not None and eg.database_version_id is not None:
                    continue
            machines = [
                m
                for m in (station.machines or [])
                if m.id_equipment_group == eg_set_station.equipment_group_type_id
                and (
                    current_version_id is None
                    or getattr(m, "database_version_id", None) == current_version_id
                )
            ]
            machines.sort(key=_machine_number_sort_key)
            all_entries.append(
                (eg, station, {"equipment_group_type": equipment_group_type, "machines": machines})
            )

    all_entries.sort(
        key=lambda x: (
            _equipment_group_sort_key(x[0]),
            _station_sort_key(x[1]),
            _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
        )
    )

    from itertools import groupby

    def _group_key(entry):
        eg = entry[0]
        return eg.id if eg else -1

    blocks = []
    for _eg_id, grp in groupby(all_entries, key=_group_key):
        entries = list(grp)
        eq_group = entries[0][0] if entries else None
        station_entries = []
        for _st_id, st_iter in groupby(entries, key=lambda x: x[1].id):
            st_list = list(st_iter)
            station = st_list[0][1]
            links_data = []
            station_rowspan = 0
            for _, _, link_item in st_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                station_rowspan += rowspan
            station_entries.append({
                "station": station,
                "station_rowspan": station_rowspan,
                "links": links_data,
            })
        total_rowspan = sum(se["station_rowspan"] for se in station_entries)
        distinct_station_keys = {
            _station_identity_key(se.get("station"))
            for se in station_entries
        }
        has_multiple_eg_set_station = len(distinct_station_keys) > 1
        blocks.append({
            "equipment_group": eq_group,
            "rowspan": total_rowspan,
            "station_entries": station_entries,
            "has_multiple_equipment_group_set_station": has_multiple_eg_set_station,
        })

    return blocks


def build_standalone_equipment_group_hierarchy(filters=None, allowed_prefixes=None):
    """
    Возвращает иерархию для standalone-групп (котельные) в формате:
    grouped_stations, blocks_by_key, hierarchy_keys, unmatched_blocks.
    """
    version_id = get_current_db_version_id()
    standalone_ids = get_filtered_standalone_equipment_group_ids(
        filters, version_id=version_id, strict_version=False
    )
    if not standalone_ids:
        return {
            "grouped_stations": {},
            "blocks_by_key": {},
            "hierarchy_keys": set(),
            "unmatched_blocks": [],
        }

    blocks = get_standalone_equipment_group_blocks(version_id)
    blocks = [b for b in blocks if b.get("equipment_group") and b["equipment_group"].id in standalone_ids]
    if not blocks:
        return {
            "grouped_stations": {},
            "blocks_by_key": {},
            "hierarchy_keys": set(),
            "unmatched_blocks": [],
        }

    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
    from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

    def _is_allowed_key(key):
        if not allowed_prefixes:
            return True
        for prefix in allowed_prefixes:
            if not prefix:
                continue
            if key[: len(prefix)] == tuple(prefix):
                return True
        return False

    blocks_by_key = defaultdict(list)
    hierarchy_keys = set()
    for block in blocks:
        eg = block.get("equipment_group")
        if not eg:
            continue
        rd = getattr(eg, "regional_district", None)
        res = getattr(eg, "regional_energy_system", None)
        if not rd or not res:
            continue
        ues = getattr(res, "union_energy_system", None) if res else None
        est = getattr(ues, "energy_system_type", None) if ues else None
        if not ues or not est:
            continue
        est_id = est.id
        ues_id = ues.id
        res_id = res.id
        rd_id = rd.id
        eu_id = rd_id
        key = (est_id, ues_id, res_id, rd_id, eu_id)
        if not _is_allowed_key(key):
            continue
        blocks_by_key[key].append(block)
        hierarchy_keys.add(key)

    grouped_stations = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        )
    )
    for key in hierarchy_keys:
        est_id, ues_id, res_id, rd_id, eu_id = key
        grouped_stations[est_id][ues_id][res_id][rd_id][eu_id] = []

    unmatched = []
    for block in blocks:
        eg = block.get("equipment_group")
        if not eg:
            unmatched.append(block)
            continue
        rd = getattr(eg, "regional_district", None)
        res = getattr(eg, "regional_energy_system", None)
        if not rd or not res:
            unmatched.append(block)
            continue
        ues = getattr(res, "union_energy_system", None) if res else None
        est = getattr(ues, "energy_system_type", None) if ues else None
        if not ues or not est:
            unmatched.append(block)
            continue
        key = (est.id, ues.id, res.id, rd.id, rd.id)
        if not _is_allowed_key(key):
            unmatched.append(block)

    return {
        "grouped_stations": dict(grouped_stations),
        "blocks_by_key": dict(blocks_by_key),
        "hierarchy_keys": hierarchy_keys,
        "unmatched_blocks": unmatched,
    }


def reorganize_by_station_first(stations, v2_groups_map):
    """
    Reorganizes per-station equipment groups into station-first structure.

    Если несколько групп оборудования входят в состав одной станции,
    ячейка «Станция» объединяется (rowspan) на все группы оборудования.

    Иерархия: Station -> EquipmentGroup -> EquipmentGroupType -> Machines

    Returns: list of blocks, each:
        {
            "station": Station,
            "station_rowspan": int,  # суммарное число строк для всех групп этой станции
            "group_entries": [
                {
                    "equipment_group": EquipmentGroup|None,
                    "rowspan": int,
                    "links": [{"equipment_group_type": obj, "machines": list, "rowspan": int}, ...]
                },
                ...
            ]
        }
    """
    if not stations:
        return []

    # Collect (equipment_group, station, link_item) from all stations
    all_entries = []
    for station in stations:
        groups = (v2_groups_map.get(station.id) or {}).get("groups", [])
        for group in groups:
            group_entity = group.get("equipment_group")
            for link_item in group.get("links", []):
                all_entries.append((group_entity, station, link_item))

    # Sort by station first, then equipment_group, then equipment_group_type
    all_entries.sort(key=lambda x: (
        _station_sort_key(x[1]),
        _equipment_group_sort_key(x[0]),
        _equipment_group_type_sort_key(x[2].get("equipment_group_type")),
    ))

    from itertools import groupby

    def _station_key(entry):
        return entry[1].id if entry[1] else -1

    blocks = []
    for _st_id, st_grp in groupby(all_entries, key=_station_key):
        st_entries = list(st_grp)
        station = st_entries[0][1] if st_entries else None

        # Group by equipment_group within this station
        def _eg_key(entry):
            eg = entry[0]
            return eg.id if eg else -1

        group_entries = []
        for _eg_id, eg_grp in groupby(st_entries, key=_eg_key):
            eg_list = list(eg_grp)
            eq_group = eg_list[0][0] if eg_list else None
            links_data = []
            group_rowspan = 0
            for _, _, link_item in eg_list:
                machines = link_item.get("machines", [])
                rowspan = max(1, len(machines))
                links_data.append({
                    "equipment_group_type": link_item.get("equipment_group_type"),
                    "machines": machines,
                    "rowspan": rowspan,
                })
                group_rowspan += rowspan
            group_entries.append({
                "equipment_group": eq_group,
                "rowspan": group_rowspan,
                "links": links_data,
            })

        station_rowspan = sum(ge["rowspan"] for ge in group_entries)
        blocks.append({
            "station": station,
            "station_rowspan": station_rowspan,
            "group_entries": group_entries,
        })

    return blocks
