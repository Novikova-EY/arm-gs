#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Read/query/display для страницы «Топливные параметры групп оборудования (доп.)» (v2).

Запись в EquipmentGroupExtraFuelParam — в
equipment_group_extra_fuel_params_write_services.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from sqlalchemy import or_, and_

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.services.equipment_groups.composite_display_cluster_services import (
    apply_simple_station_summaries,
    build_station_blocks_from_group_items,
)
from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
    resolve_composite_parents_by_numb,
    territorial_ids_for_equipment_group,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    normalize_equipment_group_ids_filter,
)


# Названия параметров для таблицы «Дополнительные параметры топлива» на equipment_group_details
EXTRA_FUEL_PARAM_LABELS = {
    "gaz_prir": "gaz_prir", "gazpp": "gazpp", "disel": "disel", "maztop": "maztop",
    "gtt": "gtt", "nft_proch": "nft_proch", "domen_g": "domen_g", "koks_g": "koks_g",
    "prochgaz": "prochgaz", "tvproch": "tvproch", "szh_gaz": "szh_gaz", "inoe": "inoe",
    "nazar": "nazar", "ibor": "ibor", "berez": "berez", "per": "per", "irbei": "irbei",
    "kansk": "kansk", "gusin": "gusin", "tugn": "tugn", "okino": "okino", "azey": "azey",
    "mug": "mug", "cher": "cher", "jer": "jer", "karab": "karab", "vork": "vork",
    "intin": "intin", "sver": "sver", "chel": "chel", "kizel": "kizel", "har": "har",
    "urt": "urt", "tataur": "tataur", "tarbag": "tarbag", "zab_kam": "zab_kam",
    "rai": "rai", "erk": "erk", "ogodj": "ogodj", "svo": "svo", "bikin": "bikin",
    "razdol": "razdol", "hankai": "hankai", "neru": "neru", "zyryan": "zyryan",
    "pyak": "pyak", "kuzngd": "kuzngd", "kuznt": "kuznt", "kuznss": "kuznss",
    "kuznun": "kuznun", "bering": "bering", "anad": "anad", "ekib": "ekib",
    "maikub": "maikub", "karag": "karag", "karajyra": "karajyra", "teniz": "teniz",
    "sosv": "sosv", "luch": "luch", "tal": "tal",
}

# Атрибуты для таблицы дополнительных параметров топлива на equipment_group_details
EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS = [
    "gaz_prir", "gazpp", "disel", "maztop", "gtt", "nft_proch", "domen_g", "koks_g",
    "prochgaz", "tvproch", "szh_gaz", "inoe",
    "nazar", "ibor", "berez", "per", "irbei", "kansk", "gusin", "tugn", "okino", "azey",
    "mug", "cher", "jer", "karab", "vork", "intin", "sver", "chel", "kizel", "har",
    "urt", "tataur", "tarbag", "zab_kam", "rai", "erk", "ogodj", "svo", "bikin",
    "razdol", "hankai", "neru", "zyryan", "pyak", "kuzngd", "kuznt", "kuznss", "kuznun",
    "bering", "anad", "ekib", "maikub", "karag", "karajyra", "teniz",
    "sosv", "luch", "tal",
]


def resolve_extra_fuel_param_value(param, attr: str, children_by_parent: dict | None = None):
    """
    Значение ячейки доп. параметров.

    У ExtraFuelParam есть только «листовые» поля (gaz_prir, kuzngd, …).
    Родительские столбцы иерархии (gaz, ugol, kuzn, …) в модели отсутствуют —
    для них считаем сумму потомков по children_by_parent из build_fuel_param_columns_hierarchy.
    """
    if param is None or not attr:
        return None

    if hasattr(param, attr):
        direct = getattr(param, attr, None)
        if direct is not None:
            return direct

    kids = (children_by_parent or {}).get(attr) or []
    if not kids:
        return None

    total = None
    for child in kids:
        child_val = resolve_extra_fuel_param_value(param, child, children_by_parent)
        if child_val is None:
            continue
        try:
            dec = child_val if isinstance(child_val, Decimal) else Decimal(str(child_val))
        except (InvalidOperation, ValueError, TypeError):
            continue
        total = dec if total is None else total + dec
    return total


def sum_extra_fuel_attrs_for_rows(
    rows,
    attr_names: list[str],
    children_by_parent: dict | None = None,
) -> dict:
    """Суммы по атрибутам (с учётом родительских столбцов-агрегатов) для строк (eg, param)."""
    summary: dict[str, Decimal] = {}
    for attr in attr_names:
        total = Decimal(0)
        any_value = False
        for _eg, param in rows or []:
            val = resolve_extra_fuel_param_value(param, attr, children_by_parent)
            if val is None:
                continue
            try:
                total += val if isinstance(val, Decimal) else Decimal(str(val))
                any_value = True
            except (InvalidOperation, ValueError, TypeError):
                pass
        summary[attr] = total if any_value else Decimal(0)
    return summary


def get_equipment_groups_with_extra_fuel_params_data(
    filters=None,
    per_page=25,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Выбирает позиции из EquipmentGroup с присоединением дополнительных параметров
    EquipmentGroupExtraFuelParam. Логика формирования как на stations_equipment_group_fuel_params.
    Возвращает rows: list[(EquipmentGroup, EquipmentGroupExtraFuelParam)].
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
            EquipmentGroupExtraFuelParam.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupExtraFuelParam.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupExtraFuelParam.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupExtraFuelParam.year_number >= _start,
        EquipmentGroupExtraFuelParam.year_number <= _end,
        version_match,
    )

    base_query = (
        db.session.query(EquipmentGroup, EquipmentGroupExtraFuelParam)
        .outerjoin(EquipmentGroupExtraFuelParam, join_cond)
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
    id_list = normalize_equipment_group_ids_filter(_filters.get("equipment_group_ids"))
    if id_list:
        base_query = base_query.filter(EquipmentGroup.id.in_(id_list))
    elif any(_filters.get(k) for k in territorial_keys) or equipment_group_name_filter:
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

    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        apply_numb1120_filter_to_eg_param_rows,
    )

    rows, numb1120_filter_choices = apply_numb1120_filter_to_eg_param_rows(
        rows, _filters
    )
    total_count = len(rows)

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": total_count or 1,
        "numb1120_filter_choices": numb1120_filter_choices,
    }


def build_equipment_group_extra_fuel_params_hierarchy(rows, children_by_parent=None):
    """
    Строит иерархию как на stations_equipment_group_fuel_params:
    energy_system_type → UES → РЭС → станция → группа оборудования.
    Группировка по regional_energy_system_id и по одной электростанции.

    children_by_parent — карта из build_fuel_param_columns_hierarchy: для родительских
    столбцов (gaz/ugol/…) итоги считаются как сумма листовых полей ExtraFuelParam.
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

    _children_by_parent = children_by_parent or {}
    _summary_attrs = list(EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS) + list(
        _children_by_parent.keys()
    )

    est_names = dict(get_energy_system_type_map())
    ues_names = dict(get_union_energy_systems_map())
    ues_display_orders = get_union_energy_system_display_order_map()
    res_names = dict(get_regional_energy_systems_name_map())
    est_names[-1] = "Не указано"
    ues_names[-1] = "Не указано"
    res_names[-1] = "Не указано"

    equipment_group_ids = [eg.id for eg, _ in (rows or []) if eg]
    _vid = get_current_db_version_id()
    parent_by_numb = resolve_composite_parents_by_numb(rows, database_version_id=_vid)
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
        _est, _ues, _res = territorial_ids_for_equipment_group(
            eg, parent_by_numb=parent_by_numb
        )
        hierarchy[_est][_ues][_res][eg.id].append((eg, param))

    def _sort_key_est(eid):
        return (1 if eid == -1 else 0, est_names.get(eid, ""))

    def _sort_key_ues(uid):
        return union_energy_system_hierarchy_sort_key(uid, ues_names, ues_display_orders)

    def _sort_key_res(rid):
        return (1 if rid == -1 else 0, res_names.get(rid, ""))

    def _compute_summary(rows_to_sum):
        return sum_extra_fuel_attrs_for_rows(
            rows_to_sum, _summary_attrs, _children_by_parent
        )

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

                for _eg_id, eg_rows in eg_items:
                    all_res_rows.extend(eg_rows)

                res_summary = _compute_summary(all_res_rows) if all_res_rows else {}

                station_blocks = build_station_blocks_from_group_items(
                    eg_items,
                    eg_to_stations,
                    allow_station_composite_fallback=False,
                    should_suppress_summary=should_suppress_fuel_params_station_summary_row,
                    parent_by_numb=parent_by_numb,
                )
                apply_simple_station_summaries(
                    station_blocks,
                    _compute_summary,
                    parent_by_numb=parent_by_numb,
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


def attach_extra_fuel_params_to_station_groups(stations, selected_year=None):
    """
    Вешает extra_fuel_params на элементы group в station.equipment_group_v2_groups.
    Сопоставление по EquipmentGroup.id (equipment_group_id).
    При загрузке из Excel: EquipmentGroup.numb == EquipmentGroupExtraFuelParam.numb1120.
    """
    if not stations:
        return
    version_id = get_current_db_version_id()

    equipment_group_ids = set()
    for station in stations:
        for group in getattr(station, "equipment_group_v2_groups", []) or []:
            eg = group.get("equipment_group")
            if eg and getattr(eg, "id", None):
                equipment_group_ids.add(eg.id)

    if not equipment_group_ids:
        return

    query = EquipmentGroupExtraFuelParam.query.filter(
        EquipmentGroupExtraFuelParam.equipment_group_id.in_(list(equipment_group_ids))
    )
    if selected_year is not None:
        query = query.filter(EquipmentGroupExtraFuelParam.year_number == selected_year)
    if version_id is None:
        query = query.filter(EquipmentGroupExtraFuelParam.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroupExtraFuelParam.database_version_id == version_id)

    params = query.all()
    params_by_group = defaultdict(list)
    for p in params:
        if p.equipment_group_id is not None:
            params_by_group[p.equipment_group_id].append(p)

    for station in stations:
        for group in getattr(station, "equipment_group_v2_groups", []) or []:
            eg = group.get("equipment_group")
            eg_id = getattr(eg, "id", None) if eg else None
            group["extra_fuel_params"] = (
                sorted(params_by_group.get(eg_id, []), key=lambda p: p.year_number or 0)
                if eg_id is not None
                else []
            )
