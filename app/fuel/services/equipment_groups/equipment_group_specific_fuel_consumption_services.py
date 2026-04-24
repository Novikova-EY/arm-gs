#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Read/query/display для страницы «Удельные показатели групп оборудования».

Запись в EquipmentGroupSpecificFuelConsumption — в
equipment_group_specific_fuel_consumption_write_services.py
(пересчёт *_calc — в equipment_group_specific_fuel_consumption_recalc_services.py).
"""

from collections import defaultdict
from sqlalchemy import or_, and_

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)


SPECIFIC_FUEL_CONSUMPTION_COLUMNS = [
    ("name", "Наименование", False),
    ("year_number", "Year", False),
    ("k", "K", True),
    ("y", "Y", True),
    ("btp", "BTP", True),
    ("sntp", "SNTP", True),
    ("bk", "BK", True),
    ("numb1120", "NUMB1120", False),
    ("snk", "SNK", True),
    ("y_calc", "Y (расчет)", True),
    ("btp_calc", "BTP (расчет)", True),
    ("sntp_calc", "SNTP (расчет)", True),
    ("bk_calc", "BK (расчет)", True),
    ("snk_calc", "SNK (расчет)", True),
]

# Суммы в иерархии: все числовые колонки, кроме k (не суммируем)
SPECIFIC_FUEL_CONSUMPTION_SUMMARY_NUMERIC_ATTRS = [
    attr for attr, _, is_num in SPECIFIC_FUEL_CONSUMPTION_COLUMNS
    if is_num and attr != "k"
]


def get_equipment_groups_with_specific_fuel_consumption_data(
    filters=None,
    per_page=10,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Выбирает позиции из EquipmentGroup с присоединением удельных показателей
    EquipmentGroupSpecificFuelConsumption.
    Возвращает rows: list[(EquipmentGroup, EquipmentGroupSpecificFuelConsumption)].
    """
    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
    )
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from sqlalchemy.orm import selectinload

    _start = start_year if start_year is not None else get_filter_start_year()
    _end = end_year if end_year is not None else get_filter_end_year()
    current_version_id = get_current_db_version_id()

    version_match = or_(
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupSpecificFuelConsumption.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupSpecificFuelConsumption.year_number >= _start,
        EquipmentGroupSpecificFuelConsumption.year_number <= _end,
        version_match,
    )

    base_query = (
        db.session.query(EquipmentGroup, EquipmentGroupSpecificFuelConsumption)
        .outerjoin(EquipmentGroupSpecificFuelConsumption, join_cond)
    )

    if hasattr(EquipmentGroup, "database_version_id"):
        if current_version_id is not None:
            base_query = base_query.filter(
                EquipmentGroup.database_version_id == current_version_id
            )
        else:
            base_query = base_query.filter(
                EquipmentGroup.database_version_id.is_(None)
            )

    territorial_keys = (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    )
    _filters = {
        k: v
        for k, v in (filters or {}).items()
        if k not in ("page", "start_year", "end_year")
    }
    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if any(_filters.get(k) for k in territorial_keys) or equipment_group_name_filter:
        from app.fuel.services.stations.stations_equipment_groups_services import (
            get_filtered_equipment_group_ids,
            get_filtered_standalone_equipment_group_ids,
        )

        filtered_ids = (
            get_filtered_equipment_group_ids(
                _filters, start_year=_start, end_year=_end
            )
            | get_filtered_standalone_equipment_group_ids(
                _filters,
                version_id=current_version_id,
                strict_version=True,
            )
        )
        if filtered_ids:
            base_query = base_query.filter(EquipmentGroup.id.in_(filtered_ids))
        else:
            base_query = base_query.filter(
                EquipmentGroup.id != EquipmentGroup.id
            )

    total_count = base_query.count()

    rows = (
        base_query
        .options(
            selectinload(EquipmentGroup.regional_energy_system).selectinload(
                RegionalEnergySystem.union_energy_system
            ),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": total_count or 1,
    }


def build_equipment_group_specific_fuel_consumption_hierarchy(rows):
    """
    Строит иерархию: energy_system_type → UES → РЭС → станция → группа оборудования.
    """
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_map,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_systems_name_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_display_order_map,
        get_union_energy_systems_map,
        union_energy_system_hierarchy_sort_key,
    )
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        _equipment_group_station_sort_key,
        _get_equipment_group_station_mapping_with_display_order,
        should_suppress_fuel_params_station_summary_row,
    )

    est_names = dict(get_energy_system_type_map())
    ues_names = dict(get_union_energy_systems_map())
    ues_display_orders = get_union_energy_system_display_order_map()
    res_names = dict(get_regional_energy_systems_name_map())
    est_names[-1] = "Не указано"
    ues_names[-1] = "Не указано"
    res_names[-1] = "Не указано"

    equipment_group_ids = [eg.id for eg, _ in (rows or []) if eg]
    eg_station_metadata = _get_equipment_group_station_mapping_with_display_order(
        equipment_group_ids, all_versions=True
    )
    eg_to_stations = {
        eg_id: [(st_id, st_name) for st_id, st_name, _ in stations]
        for eg_id, stations in (eg_station_metadata or {}).items()
    }
    eg_primary_display_orders = {
        eg_id: (stations[0][2] if stations else None)
        for eg_id, stations in (eg_station_metadata or {}).items()
    }

    hierarchy = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )

    for eg, param in rows or []:
        if not eg:
            continue
        res = getattr(eg, "regional_energy_system", None)
        ues = getattr(res, "union_energy_system", None) if res else None
        est_id = getattr(ues, "id_energy_system_type", None) if ues else None
        ues_id = ues.id if ues else None
        res_id = res.id if res else None

        _est = est_id if est_id is not None else -1
        _ues = ues_id if ues_id is not None else -1
        _res = res_id if res_id is not None else -1

        hierarchy[_est][_ues][_res][eg.id].append((eg, param))

    def _sort_key_est(eid):
        return (1 if eid == -1 else 0, est_names.get(eid, ""))

    def _sort_key_ues(uid):
        return union_energy_system_hierarchy_sort_key(uid, ues_names, ues_display_orders)

    def _sort_key_res(rid):
        return (1 if rid == -1 else 0, res_names.get(rid, ""))

    def _compute_summary(rows_to_sum):
        from decimal import Decimal

        summary = {}
        for attr in SPECIFIC_FUEL_CONSUMPTION_SUMMARY_NUMERIC_ATTRS:
            total = Decimal(0)
            for _eg, param in rows_to_sum:
                val = getattr(param, attr, None)
                if val is not None:
                    try:
                        total += Decimal(str(val))
                    except (TypeError, ValueError):
                        pass
            summary[attr] = total
        return summary

    def _get_primary_station(eg_id):
        stations = eg_to_stations.get(eg_id, [])
        if not stations:
            return None
        st_id, st_name = stations[0]
        return (st_id, st_name or "—")

    def _station_sort_key(station_tuple):
        st_id, st_name = station_tuple or (None, "—")
        return (1 if st_id is None else 0, (st_name or "").lower(), st_id or 0)

    hierarchy_flat = []
    for est_id in sorted(hierarchy.keys(), key=_sort_key_est):
        ues_list = []
        for ues_id in sorted(hierarchy[est_id].keys(), key=_sort_key_ues):
            res_list = []
            for res_id in sorted(hierarchy[est_id][ues_id].keys(), key=_sort_key_res):
                all_res_rows = []
                eg_items = sorted(
                    hierarchy[est_id][ues_id][res_id].items(),
                    key=lambda item: _equipment_group_station_sort_key(
                        item,
                        eg_primary_display_orders,
                    ),
                )

                by_station = defaultdict(list)
                for eg_id, eg_rows in eg_items:
                    all_res_rows.extend(eg_rows)
                    eg = eg_rows[0][0] if eg_rows else None
                    station_key = _get_primary_station(eg_id)
                    by_station[station_key].append(
                        {"equipment_group": eg, "rows": eg_rows}
                    )

                res_summary = _compute_summary(all_res_rows) if all_res_rows else {}

                station_blocks = []
                for station_key in sorted(by_station.keys(), key=_station_sort_key):
                    group_blocks = by_station[station_key]
                    station_rows = []
                    for gb in group_blocks:
                        station_rows.extend(gb["rows"])
                    station_summary = (
                        _compute_summary(station_rows) if station_rows else {}
                    )
                    st_id, st_name = station_key if station_key else (None, "—")
                    station_blocks.append(
                        {
                            "station_id": st_id,
                            "station_name": st_name,
                            "group_blocks": group_blocks,
                            "station_summary": station_summary,
                            "is_virtual": False,
                            "suppress_station_summary": should_suppress_fuel_params_station_summary_row(
                                st_id,
                                st_name,
                                group_blocks,
                                set(),
                            ),
                        }
                    )

                res_list.append(
                    {
                        "res_id": res_id,
                        "res_name": res_names.get(res_id, "—"),
                        "group_blocks": [
                            gb for sb in station_blocks for gb in sb["group_blocks"]
                        ],
                        "station_blocks": station_blocks,
                        "res_summary": res_summary,
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


def map_latest_specific_y_by_equipment_group_id(
    group_ids: list[int],
    target_year: int,
    *,
    effective_db_version_id: int | None = None,
) -> dict[int, object | None]:
    """
    Для каждой группы — поле ``y`` из строки удельных расходов с максимальным
    ``year_number`` ≤ ``target_year``.

    Условие присоединения к группе — как на странице
    ``stations_equipment_group_specific_fuel_consumption`` (``version_match`` между
    строкой удельных расходов и ``EquipmentGroup``), а не фильтр только по
    ``database_version_id`` самой строки: иначе строки с версией, совпадающей с группой,
    но отличной от «текущей» глобальной версии, не находились.
    """
    if not group_ids:
        return {}

    uniq_ids = list(dict.fromkeys(group_ids))
    current_version_id = (
        effective_db_version_id
        if effective_db_version_id is not None
        else get_current_db_version_id()
    )

    # Как join в get_equipment_groups_with_specific_fuel_consumption_data
    version_match = or_(
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id
            == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupSpecificFuelConsumption.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupSpecificFuelConsumption.year_number <= target_year,
        version_match,
    )

    q = (
        db.session.query(EquipmentGroup, EquipmentGroupSpecificFuelConsumption)
        .join(EquipmentGroupSpecificFuelConsumption, join_cond)
        .filter(EquipmentGroup.id.in_(uniq_ids))
    )
    if current_version_id is not None:
        q = q.filter(EquipmentGroup.database_version_id == current_version_id)
    else:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))

    best: dict[int, tuple[int, EquipmentGroupSpecificFuelConsumption]] = {}
    for _eg, spec in q.all():
        gid = spec.equipment_group_id
        if gid is None:
            continue
        yr = spec.year_number if spec.year_number is not None else -10**9
        prev = best.get(gid)
        if prev is None or yr > prev[0]:
            best[gid] = (yr, spec)

    return {g: (best[g][1].y if g in best else None) for g in uniq_ids}
