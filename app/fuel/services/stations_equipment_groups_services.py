# -*- coding: utf-8 -*-
"""Helpers for stations_equipment_groups based on v2 equipment group models."""

from __future__ import annotations

from collections import defaultdict
import re

from sqlalchemy import or_
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
        # Одна строка: станция —, тип —, агрегат —
        dummy_station = SimpleNamespace(id=None, name="—")
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
    if not any(_filters.get(k) for k in territorial_keys):
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
            EquipmentGroup.oes == UnionEnergySystemExternalMapping.external_id,
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

    return {r[0] for r in q.distinct().all()}


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

    result = {}
    for station in stations:
        machines = [
            m
            for m in (station.machines or [])
            if current_version_id is None
            or getattr(m, "database_version_id", None) == current_version_id
        ]
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
    """Sort key for stations (by name, then id)."""
    if station is None:
        return (1, "", 0)
    name = (getattr(station, "name") or "").strip().lower()
    return (0, name, getattr(station, "id", 0) or 0)


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
        blocks.append({
            "equipment_group": eq_group,
            "rowspan": total_rowspan,
            "station_entries": station_entries,
        })

    return blocks


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
