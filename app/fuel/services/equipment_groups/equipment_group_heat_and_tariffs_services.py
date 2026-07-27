#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Read/query/display для страницы «Тепло и тарифы из СТ».
"""

from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy import or_, and_

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import (
    EquipmentGroupHeatAndTariffs,
)


HEAT_AND_TARIFFS_COLUMNS = [
    ("numb1120", "NUMB1120", False),
    ("kod_goroda", "kod_goroda", False),
    ("name_goroda", "name_goroda", False),
    ("var_razv", "var_razv", False),
    ("name_eto", "name_ETO", False),
    ("ndv_st", "NDvST", False),
    ("year_number", "Year", False),
    ("q", "Q", True),
    ("tarif", "TARIF", True),
]

# Колонки-идентификаторы (слева) и метрики (строки) при отображении годов столбцами
HEAT_AND_TARIFFS_IDENTITY_COLUMNS = [
    ("numb1120", "NUMB1120", False),
    ("kod_goroda", "kod_goroda", False),
    ("name_goroda", "name_goroda", False),
    ("var_razv", "var_razv", False),
    ("name_eto", "name_ETO", False),
    ("ndv_st", "NDvST", False),
]

HEAT_AND_TARIFFS_METRIC_COLUMNS = [
    ("q", "Q", True),
    ("tarif", "TARIF", True),
]


def _fake_equipment_group(param: EquipmentGroupHeatAndTariffs) -> SimpleNamespace:
    """Синтетическая «группа» для записей без привязки к EquipmentGroup."""
    label = (param.name_eto or "").strip() or (param.name_goroda or "").strip() or "—"
    # Отрицательный стабильный id для пагинации/группировки
    key_parts = (
        param.kod_goroda or 0,
        (param.name_eto or "")[:80],
        param.numb1120 or 0,
        param.var_razv or 0,
    )
    fake_id = -abs(hash(key_parts)) % 2_000_000_000 - 1
    return SimpleNamespace(
        id=fake_id,
        name=label,
        name_ext=None,
        regional_energy_system=None,
        database_version_id=param.database_version_id,
        numb=param.numb1120,
    )


def get_equipment_groups_with_heat_and_tariffs_data(
    filters=None,
    per_page=10,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Выбирает записи EquipmentGroupHeatAndTariffs с optional EquipmentGroup.
    Возвращает rows: list[(EquipmentGroup|SimpleNamespace, EquipmentGroupHeatAndTariffs)].
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
            EquipmentGroupHeatAndTariffs.database_version_id
            == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupHeatAndTariffs.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroup.id == EquipmentGroupHeatAndTariffs.equipment_group_id,
        version_match,
    )

    base_query = (
        db.session.query(EquipmentGroup, EquipmentGroupHeatAndTariffs)
        .select_from(EquipmentGroupHeatAndTariffs)
        .outerjoin(EquipmentGroup, join_cond)
        .filter(
            EquipmentGroupHeatAndTariffs.year_number >= _start,
            EquipmentGroupHeatAndTariffs.year_number <= _end,
        )
    )

    if current_version_id is not None:
        base_query = base_query.filter(
            or_(
                EquipmentGroupHeatAndTariffs.database_version_id == current_version_id,
                and_(
                    EquipmentGroupHeatAndTariffs.database_version_id.is_(None),
                    EquipmentGroupHeatAndTariffs.equipment_group_id.is_(None),
                ),
            )
        )
    else:
        base_query = base_query.filter(
            EquipmentGroupHeatAndTariffs.database_version_id.is_(None)
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
    equipment_group_name_filter = (
        (_filters.get("equipment_group_name_filter") or "").strip() or None
    )
    has_territorial = any(_filters.get(k) for k in territorial_keys)

    if has_territorial or equipment_group_name_filter:
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
        name_clauses = []
        if equipment_group_name_filter:
            like = f"%{equipment_group_name_filter}%"
            name_clauses = [
                EquipmentGroupHeatAndTariffs.name_eto.ilike(like),
                EquipmentGroupHeatAndTariffs.name_goroda.ilike(like),
                EquipmentGroup.name.ilike(like),
                EquipmentGroup.name_ext.ilike(like),
            ]
        if has_territorial:
            if filtered_ids:
                base_query = base_query.filter(EquipmentGroup.id.in_(filtered_ids))
            else:
                base_query = base_query.filter(
                    EquipmentGroupHeatAndTariffs.id != EquipmentGroupHeatAndTariffs.id
                )
        if name_clauses:
            base_query = base_query.filter(or_(*name_clauses))

    total_count = base_query.count()

    rows_raw = (
        base_query.options(
            selectinload(EquipmentGroup.regional_energy_system).selectinload(
                RegionalEnergySystem.union_energy_system
            ),
        )
        .order_by(
            EquipmentGroupHeatAndTariffs.name_goroda,
            EquipmentGroupHeatAndTariffs.name_eto,
            EquipmentGroupHeatAndTariffs.numb1120,
            EquipmentGroupHeatAndTariffs.year_number,
            EquipmentGroupHeatAndTariffs.id,
        )
        .all()
    )

    rows = []
    for eg, param in rows_raw:
        if eg is None and param is not None:
            eg = _fake_equipment_group(param)
        rows.append((eg, param))

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": total_count or 1,
    }


def _years_from_rows(rows):
    years = sorted(
        {
            int(param.year_number)
            for _eg, param in (rows or [])
            if param is not None and getattr(param, "year_number", None) is not None
        }
    )
    return years


def _pivot_heat_and_tariffs_group_block(eg_rows, years):
    """Схлопывает записи группы за несколько лет в identity + metric_rows × years."""
    eg = eg_rows[0][0] if eg_rows else None
    sample_param = eg_rows[0][1] if eg_rows else None
    identity = {
        attr: (getattr(sample_param, attr, None) if sample_param is not None else None)
        for attr, _label, _num in HEAT_AND_TARIFFS_IDENTITY_COLUMNS
    }
    by_year = {}
    for _eg, param in eg_rows or []:
        if param is None or getattr(param, "year_number", None) is None:
            continue
        by_year[int(param.year_number)] = param

    metric_rows = []
    for attr, label, _is_num in HEAT_AND_TARIFFS_METRIC_COLUMNS:
        values_by_year = {}
        for y in years:
            param = by_year.get(y)
            values_by_year[y] = getattr(param, attr, None) if param is not None else None
        metric_rows.append(
            {
                "attr": attr,
                "label": label,
                "values_by_year": values_by_year,
            }
        )

    return {
        "equipment_group": eg,
        "identity": identity,
        "metric_rows": metric_rows,
        "rows": eg_rows,
    }


def compute_heat_and_tariffs_year_summary(rows_to_sum, years):
    """
    Суммы по годам для сводных строк.
    Q суммируется; TARIF не агрегируется (в шаблоне «—»).
    """
    from decimal import Decimal

    years = list(years or [])
    q_by_year = {y: Decimal(0) for y in years}
    q_has_value = {y: False for y in years}

    for _eg, param in rows_to_sum or []:
        if param is None or getattr(param, "year_number", None) is None:
            continue
        y = int(param.year_number)
        if y not in q_by_year:
            continue
        val = getattr(param, "q", None)
        if val is None:
            continue
        try:
            q_by_year[y] += Decimal(str(val))
            q_has_value[y] = True
        except (TypeError, ValueError):
            pass

    return {
        "q": {y: (q_by_year[y] if q_has_value[y] else None) for y in years},
        "tarif": {y: None for y in years},
    }


def refresh_heat_and_tariffs_year_summaries(hierarchy_flat, years):
    """Пересчитывает station/res summary после пагинации в формат values_by_year."""
    years = list(years or [])
    for est_block in hierarchy_flat or []:
        for ues_block in est_block.get("ues_list") or []:
            for res_block in ues_block.get("res_list") or []:
                all_res_rows = []
                for station_block in res_block.get("station_blocks") or []:
                    station_rows = []
                    for gb in station_block.get("group_blocks") or []:
                        # На случай, если блок ещё не схлопнут (старый формат)
                        if "metric_rows" not in gb:
                            pivoted = _pivot_heat_and_tariffs_group_block(
                                gb.get("rows") or [], years
                            )
                            gb.update(pivoted)
                        station_rows.extend(gb.get("rows") or [])
                    station_block["station_summary"] = compute_heat_and_tariffs_year_summary(
                        station_rows, years
                    )
                    all_res_rows.extend(station_rows)
                res_block["res_summary"] = compute_heat_and_tariffs_year_summary(
                    all_res_rows, years
                )
    return hierarchy_flat


def build_equipment_group_heat_and_tariffs_hierarchy(rows, years=None):
    """Строит иерархию: energy_system_type → UES → РЭС → станция → группа/ЭТО.

    Группы схлопнуты по годам: identity + metric_rows (Q/TARIF) × years.
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

    years = list(years) if years is not None else _years_from_rows(rows)

    est_names = dict(get_energy_system_type_map())
    ues_names = dict(get_union_energy_systems_map())
    ues_display_orders = get_union_energy_system_display_order_map()
    res_names = dict(get_regional_energy_systems_name_map())
    est_names[-1] = "Не указано"
    ues_names[-1] = "Не указано"
    res_names[-1] = "Не указано"

    real_eg_ids = [
        eg.id
        for eg, _ in (rows or [])
        if eg is not None and getattr(eg, "id", None) is not None and eg.id > 0
    ]
    eg_station_metadata = _get_equipment_group_station_mapping_with_display_order(
        real_eg_ids, all_versions=True
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

    def _get_primary_station(eg_id, eg_obj, sample_param):
        if eg_id and eg_id > 0:
            stations = eg_to_stations.get(eg_id, [])
            if stations:
                st_id, st_name = stations[0]
                return (st_id, st_name or "—")
        city = (
            getattr(sample_param, "name_goroda", None) if sample_param else None
        ) or "—"
        return (None, city)

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
                    sample_param = eg_rows[0][1] if eg_rows else None
                    station_key = _get_primary_station(eg_id, eg, sample_param)
                    by_station[station_key].append(
                        _pivot_heat_and_tariffs_group_block(eg_rows, years)
                    )

                res_summary = (
                    compute_heat_and_tariffs_year_summary(all_res_rows, years)
                    if all_res_rows
                    else compute_heat_and_tariffs_year_summary([], years)
                )

                station_blocks = []
                for station_key in sorted(by_station.keys(), key=_station_sort_key):
                    group_blocks = by_station[station_key]
                    station_rows = []
                    for gb in group_blocks:
                        station_rows.extend(gb["rows"])
                    station_summary = compute_heat_and_tariffs_year_summary(
                        station_rows, years
                    )
                    st_id, st_name = station_key if station_key else (None, "—")
                    station_blocks.append(
                        {
                            "station_id": st_id,
                            "station_name": st_name,
                            "group_blocks": group_blocks,
                            "station_summary": station_summary,
                            "is_virtual": st_id is None,
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
