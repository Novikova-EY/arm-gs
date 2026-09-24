# -*- coding: utf-8 -*-
"""Итоговые суммы модуля «Топливо»: ЕЭС / ТИТЭС / ФО / СЗ / Россия."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from app.common.services.help_services import format_decimal_trim_for_display
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    FUEL_EDIT_DATA_PARAM_COLUMNS,
    build_fuel_param_columns_hierarchy,
)
from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
    resolve_composite_parents_by_numb,
    territorial_ids_for_equipment_group,
)
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_row_participates,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    FUEL_PARAMS_HIERARCHY_SUMMARY_NUMERIC_ATTRS,
    FUEL_PARAMS_HIERARCHY_SUMMARY_SKIP_ATTRS,
    apply_fuel_param_derived_ratios_to_mapping,
)


# Колонки витрины итогов: как на edit_data, без идентификаторов/справочников.
_SKIP_DISPLAY_ATTRS = frozenset({"numb1120", "hfix", "ved"})

FUEL_TOTALS_COLUMNS: tuple[tuple[str, str, bool], ...] = tuple(
    (attr, label, is_numeric)
    for attr, label, is_numeric in FUEL_EDIT_DATA_PARAM_COLUMNS
    if attr not in _SKIP_DISPLAY_ATTRS
)

_SUM_ATTRS = tuple(
    attr
    for attr in FUEL_PARAMS_HIERARCHY_SUMMARY_NUMERIC_ATTRS
    if attr not in FUEL_PARAMS_HIERARCHY_SUMMARY_SKIP_ATTRS
)


def parse_aggregation_types(args) -> list[str]:
    """Как на generation/totals_summary: ees|tites|fo|oes|russia|sync_area_{id}."""
    aggregation_types = [
        (at or "").strip().lower()
        for at in args.getlist("aggregation_type")
        if (at or "").strip()
    ]
    if not aggregation_types:
        aggregation_types = ["ees"] if len(args) == 0 else []

    valid_types = {"fo", "oes", "ees", "tites", "russia"}
    filtered: list[str] = []
    for at in aggregation_types:
        if at in valid_types:
            filtered.append(at)
        elif at.startswith("sync_area_"):
            try:
                int(at.replace("sync_area_", ""))
            except ValueError:
                continue
            filtered.append(at)
    return filtered or (["ees"] if len(args) == 0 else [])


def resolve_rounding_digits(raw: Any, default: int = 1) -> int:
    try:
        digits = int(raw)
    except (TypeError, ValueError):
        return default
    if digits is None or digits < -1:
        return default
    return digits


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _add_into(acc: dict[str, Decimal | None], attr: str, value: Any) -> None:
    part = _as_decimal(value)
    if part is None:
        return
    cur = acc.get(attr)
    acc[attr] = part if cur is None else cur + part


def _fo_sa_ids_for_equipment_group(eg) -> tuple[int | None, int | None]:
    district = getattr(eg, "regional_district", None)
    if district is None:
        return None, None
    fo_id = getattr(district, "id_federal_district", None)
    sa_id = getattr(district, "id_synchronous_area", None)
    return (
        int(fo_id) if fo_id is not None else None,
        int(sa_id) if sa_id is not None else None,
    )


def _load_fuel_param_rows(start_year: int, end_year: int) -> list[tuple[Any, Any]]:
    from sqlalchemy import and_, or_
    from sqlalchemy.orm import selectinload

    from app.common.services.database_version_filter import get_current_db_version_id
    from app.extensions import db
    from app.fuel.models.fue_equipment_group_fuel_param_model import (
        EquipmentGroupFuelParam,
    )
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        restrict_equipment_group_query_to_current_version,
    )
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.energy_systems.union_energy_system_model import (
        UnionEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    current_version_id = get_current_db_version_id()
    version_match = or_(
        and_(
            EquipmentGroupFuelParam.database_version_id
            == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupFuelParam.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupFuelParam.year_number >= start_year,
        EquipmentGroupFuelParam.year_number <= end_year,
        version_match,
    )
    query = (
        db.session.query(EquipmentGroup, EquipmentGroupFuelParam)
        .join(EquipmentGroupFuelParam, join_cond)
        .options(
            selectinload(EquipmentGroup.regional_energy_system)
            .selectinload(RegionalEnergySystem.union_energy_system)
            .selectinload(UnionEnergySystem.energy_system_type),
            selectinload(EquipmentGroup.regional_district).selectinload(
                RegionalDistrict.federal_district
            ),
            selectinload(EquipmentGroup.regional_district).selectinload(
                RegionalDistrict.synchronous_area
            ),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
        )
    )
    query = restrict_equipment_group_query_to_current_version(
        query,
        current_version_id,
        skip=False,
    )
    return list(query.all())


def _sorted_sync_area_ids(synchronous_area_list: list) -> list[int]:
    from app.common.services.database_version_filter import filter_by_db_version
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    sa_ids = [sa.id for sa in synchronous_area_list if sa.id and sa.id > 0]
    kaliningrad_ids: list[int] = []
    try:
        rd_query = filter_by_db_version(RegionalDistrict.query, RegionalDistrict)
        rd_sa_ids = (
            rd_query.filter(RegionalDistrict.region_number.in_(["39", "039"]))
            .with_entities(RegionalDistrict.id_synchronous_area)
            .all()
        )
        kaliningrad_ids = [sa_id for (sa_id,) in rd_sa_ids if sa_id]
    except Exception:
        kaliningrad_ids = []
    if not kaliningrad_ids:
        for sa in synchronous_area_list:
            name_l = (getattr(sa, "name", None) or "").lower()
            sid = getattr(sa, "id", None)
            if sid and sid > 0 and "калининград" in name_l:
                kaliningrad_ids.append(sid)
    kaliningrad_ids = sorted({i for i in kaliningrad_ids if i in set(sa_ids)})
    rest = [i for i in sa_ids if i not in set(kaliningrad_ids)]
    return kaliningrad_ids + rest


def _format_cell(value: Any, digits: int) -> str:
    if value is None:
        return "—"
    if digits == -1:
        return format_decimal_trim_for_display(value, digits=0)
    if digits == 0:
        return format_decimal_trim_for_display(value, digits=None)
    return format_decimal_trim_for_display(value, digits=digits)


def _build_year_rows(
    by_year: dict[int, dict[str, Any]],
    *,
    label: str,
    years: list[int],
    digits: int,
    row_class: str,
    columns: list[tuple[str, str, bool]] | tuple[tuple[str, str, bool], ...],
) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    for year in years:
        summary = by_year.get(year)
        if not summary:
            continue
        apply_fuel_param_derived_ratios_to_mapping(summary)
        cells = [
            _format_cell(summary.get(attr), digits) if is_numeric else "—"
            for attr, _label, is_numeric in columns
        ]
        rows.append({"year": year, "cells": cells})
    if not rows:
        return None
    return {
        "label": label,
        "row_class": row_class,
        "rowspan": len(rows),
        "rows": rows,
    }


def build_fuel_totals_summary_context(
    *,
    start_year: int,
    end_year: int,
    aggregation_types: list[str],
    rounding_digits: int,
    filter_year_list: list[int] | None = None,
) -> dict[str, Any]:
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_list_full,
        get_energy_system_type_map,
    )
    from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
        get_synchronous_area_list_full,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
        get_union_energy_systems_map,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_federal_district_list_full,
        get_federal_districts_map,
    )
    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict,
    )
    from app.common.services.get_services.years.years_get_services import (
        get_year_numbers_sorted_for_current_db_version,
    )
    from app.common.services.database_version_filter import get_current_db_version_id

    years = list(range(int(start_year), int(end_year) + 1))
    raw_rows = _load_fuel_param_rows(int(start_year), int(end_year))
    parent_by_numb = resolve_composite_parents_by_numb(
        raw_rows,
        database_version_id=get_current_db_version_id(),
    )

    # (bucket_kind, bucket_id) -> year -> sums
    buckets: dict[tuple[str, Any], dict[int, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for eg, param in raw_rows:
        if eg is None or not fuel_param_row_participates(param):
            continue
        try:
            year = int(getattr(param, "year_number", None))
        except (TypeError, ValueError):
            continue
        if year < start_year or year > end_year:
            continue

        est_id, ues_id, _res_id = territorial_ids_for_equipment_group(
            eg, parent_by_numb
        )
        fo_id, sa_id = _fo_sa_ids_for_equipment_group(eg)

        targets: list[tuple[str, Any]] = [("russia", "russia")]
        if est_id is not None and est_id > 0:
            targets.append(("est", int(est_id)))
        if ues_id is not None and ues_id > 0:
            targets.append(("ues", int(ues_id)))
        if fo_id is not None and fo_id > 0:
            targets.append(("fo", int(fo_id)))
        if sa_id is not None and sa_id > 0:
            targets.append(("sa", int(sa_id)))

        for kind, key in targets:
            acc = buckets[(kind, key)][year]
            for attr in _SUM_ATTRS:
                _add_into(acc, attr, getattr(param, attr, None))

    energy_system_type_list = get_energy_system_type_list_full()
    energy_system_type_names = get_energy_system_type_map()
    sorted_energy_system_type_ids = [
        est.id for est in energy_system_type_list if est.id
    ]

    federal_district_list = get_federal_district_list_full()
    federal_district_names = get_federal_districts_map()
    sorted_federal_district_ids = [fd.id for fd in federal_district_list if fd.id]

    union_energy_system_list = [
        ues
        for ues in get_union_energy_system_list_full()
        if ues.id
        and (ues.name or "").strip()
        and (ues.name or "").strip().lower() not in {"не указано", "не указ"}
    ]
    union_energy_system_names = get_union_energy_systems_map()
    sorted_union_energy_system_ids = [
        ues.id for ues in union_energy_system_list if ues.id
    ]

    synchronous_area_list = [
        sa
        for sa in get_synchronous_area_list_full()
        if sa.id
        and (sa.name or "").strip()
        and (sa.name or "").strip().lower() not in {"не указано", "не указ"}
    ]
    synchronous_area_names = {sa.id: sa.name for sa in synchronous_area_list if sa.id}
    sorted_synchronous_area_ids = _sorted_sync_area_ids(synchronous_area_list)

    should_show_totals = {
        "energy_system_types": {},
        "union_energy_systems": False,
        "synchronous_areas": {},
        "federal_districts": False,
        "total": False,
    }
    if "russia" in aggregation_types:
        should_show_totals["total"] = True
    if "fo" in aggregation_types:
        should_show_totals["federal_districts"] = True
    if "oes" in aggregation_types:
        should_show_totals["union_energy_systems"] = True
    for est_id in sorted_energy_system_type_ids:
        name_u = (energy_system_type_names.get(est_id) or "").upper()
        if "ees" in aggregation_types and "ЕЭС" in name_u:
            should_show_totals["energy_system_types"][est_id] = True
        if "tites" in aggregation_types and "ТИТЭС" in name_u:
            should_show_totals["energy_system_types"][est_id] = True
    for sa_id in sorted_synchronous_area_ids:
        if f"sync_area_{sa_id}" in aggregation_types:
            should_show_totals["synchronous_areas"][sa_id] = True

    fuel_param_column_hierarchy = build_fuel_param_columns_hierarchy(
        list(FUEL_TOTALS_COLUMNS)
    )
    columns = list(
        fuel_param_column_hierarchy.get("fuel_param_columns") or FUEL_TOTALS_COLUMNS
    )

    blocks: list[dict[str, Any]] = []

    if should_show_totals["federal_districts"]:
        for fd_id in sorted_federal_district_ids:
            block = _build_year_rows(
                buckets.get(("fo", fd_id), {}),
                label=f"{federal_district_names.get(fd_id) or fd_id}, всего",
                years=years,
                digits=rounding_digits,
                row_class="table-primary",
                columns=columns,
            )
            if block:
                blocks.append(block)

    if should_show_totals["union_energy_systems"]:
        for ues_id in sorted_union_energy_system_ids:
            block = _build_year_rows(
                buckets.get(("ues", ues_id), {}),
                label=f"{union_energy_system_names.get(ues_id) or ues_id}, всего",
                years=years,
                digits=rounding_digits,
                row_class="table-success",
                columns=columns,
            )
            if block:
                blocks.append(block)

    for sa_id in sorted_synchronous_area_ids:
        if not should_show_totals["synchronous_areas"].get(sa_id):
            continue
        block = _build_year_rows(
            buckets.get(("sa", sa_id), {}),
            label=f"{synchronous_area_names.get(sa_id) or sa_id}, всего",
            years=years,
            digits=rounding_digits,
            row_class="table-secondary",
            columns=columns,
        )
        if block:
            blocks.append(block)

    for est_id in sorted_energy_system_type_ids:
        if not should_show_totals["energy_system_types"].get(est_id):
            continue
        name = energy_system_type_names.get(est_id) or str(est_id)
        name_u = name.upper()
        row_class = "table-info" if "ЕЭС" in name_u else "table-warning"
        block = _build_year_rows(
            buckets.get(("est", est_id), {}),
            label=f"{name}, всего",
            years=years,
            digits=rounding_digits,
            row_class=row_class,
            columns=columns,
        )
        if block:
            blocks.append(block)

    if should_show_totals["total"]:
        block = _build_year_rows(
            buckets.get(("russia", "russia"), {}),
            label="Россия, всего",
            years=years,
            digits=rounding_digits,
            row_class="table-danger",
            columns=columns,
        )
        if block:
            blocks.append(block)

    year_list = list(filter_year_list or [])
    if not year_list:
        year_list = get_year_numbers_sorted_for_current_db_version() or years

    return {
        "page_title": "Итоговые суммы (ЕЭС, ТИТЭС, ФО, СЗ, Россия)",
        "start_year": start_year,
        "end_year": end_year,
        "rounding_digits": rounding_digits,
        "aggregation_types": aggregation_types,
        "should_show_totals": should_show_totals,
        "sorted_energy_system_type_ids": sorted_energy_system_type_ids,
        "sorted_union_energy_system_ids": sorted_union_energy_system_ids,
        "sorted_synchronous_area_ids": sorted_synchronous_area_ids,
        "sorted_federal_district_ids": sorted_federal_district_ids,
        "energy_system_type_names": energy_system_type_names,
        "union_energy_system_names": union_energy_system_names,
        "synchronous_area_names": synchronous_area_names,
        "federal_district_names": federal_district_names,
        "year_features": get_year_feature_dict(),
        "filter_year_list": year_list,
        "columns": columns,
        "fuel_param_column_hierarchy": fuel_param_column_hierarchy,
        "blocks": blocks,
    }
