# -*- coding: utf-8 -*-
"""Страницы анализа ПГ: состав групп из модуля «Топливо», данные ТЭП + PGParamCalc."""
from __future__ import annotations

from typing import Any

from app.ecology.services.ecology_text_helpers import text_contains
from app.ecology.services.gis_tes_fuel_comparison_constants import (
    ANALYSIS_SHEET_SLUGS,
    BEZ_KOT_SHEET_SLUGS,
    PG_ANALYSIS_SHEET_SLUGS,
    UNSPECIFIED_LEVEL_NAME,
    ZV_ANALYSIS_SHEET_SLUGS,
)


def _eg_display_numb(eg: Any, param: Any = None) -> int | None:
    for raw in (
        getattr(param, "numb1120", None) if param else None,
        getattr(eg, "numb", None),
    ):
        if raw is None or raw is False:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _eg_display_name(eg: Any) -> str:
    return (
        (getattr(eg, "name", None) or getattr(eg, "name_ext", None) or "").strip()
        or UNSPECIFIED_LEVEL_NAME
    )


def _type_name_is_boiler(name: Any) -> bool:
    return "котельн" in str(name or "").strip().lower()


def _is_boiler_group(eg: Any, boiler_eg_ids: set[int]) -> bool:
    eg_id = getattr(eg, "id", None)
    return eg_id is not None and int(eg_id) in boiler_eg_ids


def get_boiler_equipment_group_ids(version_id: int | None = None) -> set[int]:
    """ID групп оборудования, у которых тип группы — котельная."""
    from sqlalchemy import func

    from app.extensions import db
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import (
        EquipmentGroupSetStation,
    )
    from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
        EquipmentGroupType,
    )

    q = (
        db.session.query(EquipmentGroupSet.equipment_group_id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id
            == EquipmentGroupSetStation.id,
        )
        .join(
            EquipmentGroupType,
            EquipmentGroupSetStation.equipment_group_type_id == EquipmentGroupType.id,
        )
        .filter(func.lower(EquipmentGroupType.name).like("%котельн%"))
    )
    if version_id is not None:
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
        q = q.filter(EquipmentGroupType.database_version_id == version_id)
    return {int(row[0]) for row in q.all() if row[0] is not None}


def _territory_filters_to_fuel_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Фильтры страницы анализа → формат get_equipment_groups_with_fuel_params_data."""
    out: dict[str, Any] = {}
    for key in (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
        "numb1120_filter",
    ):
        values = filters.get(key) or []
        if values:
            out[key] = list(values)
    station = (filters.get("station_name_filter") or "").strip()
    if station:
        out["equipment_group_name_filter"] = station
    return out


def _blank_filled(source_columns: list[dict[str, Any]]) -> list[Any]:
    return [None] * len(source_columns)


def _set_column_value(
    filled: list[Any],
    source_columns: list[dict[str, Any]],
    keys: set[str],
    value: Any,
) -> None:
    from app.ecology.services.gis_tes_fuel_comparison_services import _column_index

    idx = _column_index(source_columns, keys)
    if idx is None:
        return
    if len(filled) <= idx:
        filled.extend([None] * (idx - len(filled) + 1))
    filled[idx] = value


def _apply_group_identity(
    filled: list[Any],
    source_columns: list[dict[str, Any]],
    *,
    eg: Any,
    year: int,
    param: Any = None,
) -> list[Any]:
    out = list(filled)
    name = _eg_display_name(eg)
    numb = _eg_display_numb(eg, param)
    _set_column_value(out, source_columns, {"NAME", "Stancia"}, name)
    _set_column_value(out, source_columns, {"numb1120"}, numb)
    _set_column_value(out, source_columns, {"Year"}, year)
    return out


def _iter_fuel_group_blocks(fuel_hierarchy: list[dict[str, Any]]):
    for est_block in fuel_hierarchy or []:
        for ues_block in est_block.get("ues_list") or []:
            for res_block in ues_block.get("res_list") or []:
                station_blocks = res_block.get("station_blocks")
                if station_blocks:
                    for station_block in station_blocks:
                        for group_block in station_block.get("group_blocks") or []:
                            yield est_block, ues_block, res_block, station_block, group_block
                else:
                    for group_block in res_block.get("group_blocks") or []:
                        yield est_block, ues_block, res_block, None, group_block


def _unique_eg_rows(rows: list[tuple[Any, Any]]) -> list[tuple[Any, Any]]:
    seen: set[int] = set()
    out: list[tuple[Any, Any]] = []
    for eg, param in rows or []:
        eg_id = getattr(eg, "id", None) if eg is not None else None
        if eg_id is None or int(eg_id) in seen:
            continue
        seen.add(int(eg_id))
        out.append((eg, param))
    return out


def _text_contains_ci(needle: str, value: Any) -> bool:
    return text_contains(needle, value, reject_empty_needle=True)


def _eg_ids_matching_ved(
    eg_ids: set[int],
    allowed: set[int],
    start_year: int,
    end_year: int,
    version_id: int | None,
) -> set[int] | None:
    if not eg_ids or not allowed:
        return set()
    try:
        from sqlalchemy import or_

        from app.extensions import db
        from app.fuel.models.fue_equipment_group_fuel_param_model import (
            EquipmentGroupFuelParam,
        )

        query = db.session.query(EquipmentGroupFuelParam.equipment_group_id).filter(
            EquipmentGroupFuelParam.equipment_group_id.in_(list(eg_ids)),
            EquipmentGroupFuelParam.year_number >= int(start_year),
            EquipmentGroupFuelParam.year_number <= int(end_year),
            EquipmentGroupFuelParam.ved.in_(list(allowed)),
        )
        if version_id is not None:
            query = query.filter(
                or_(
                    EquipmentGroupFuelParam.database_version_id == version_id,
                    EquipmentGroupFuelParam.database_version_id.is_(None),
                )
            )
        return {int(row[0]) for row in query.distinct().all() if row[0] is not None}
    except Exception:
        return None


def _filter_listing_rows(
    rows: list[tuple[Any, Any]],
    territory_filters: dict[str, Any],
    *,
    start_year: int,
    end_year: int,
    version_id: int | None,
) -> list[tuple[Any, Any]]:
    from app.ecology.services.gis_tes_fuel_comparison_constants import (
        VED_FILTER_TO_VALUES,
    )

    out = list(rows or [])
    gen_q = (territory_filters.get("gen_company_filter") or "").strip()
    if gen_q:
        filtered = []
        for eg, param in out:
            gk = getattr(eg, "gen_company_external_mapping", None) if eg is not None else None
            name = getattr(gk, "external_name", None) if gk is not None else None
            if _text_contains_ci(gen_q, name):
                filtered.append((eg, param))
        out = filtered

    ved_group = str(territory_filters.get("ved_filter") or "").strip()
    allowed = set(VED_FILTER_TO_VALUES.get(ved_group, ()))
    if not allowed:
        return out
    eg_ids = {
        int(eg.id)
        for eg, _param in out
        if eg is not None and getattr(eg, "id", None) is not None
    }
    matching = _eg_ids_matching_ved(
        eg_ids, allowed, start_year, end_year, version_id
    )
    if matching is not None:
        return [
            (eg, param)
            for eg, param in out
            if eg is not None
            and getattr(eg, "id", None) is not None
            and int(eg.id) in matching
        ]
    filtered = []
    for eg, param in out:
        try:
            ved_value = int(getattr(param, "ved", None))
        except (TypeError, ValueError):
            continue
        if ved_value in allowed:
            filtered.append((eg, param))
    return filtered


def _fallback_fuel_dict(
    eg: Any,
    param: Any,
    est_block: dict[str, Any],
    ues_block: dict[str, Any],
    res_block: dict[str, Any],
) -> dict[str, Any]:
    district = getattr(eg, "regional_district", None)
    federal = getattr(district, "federal_district", None) if district else None
    sync_area = getattr(district, "synchronous_area", None) if district else None
    return {
        "energy_system_type_id": est_block.get("est_id"),
        "est_name": est_block.get("est_name"),
        "ues_id": ues_block.get("ues_id"),
        "ues": ues_block.get("ues_name"),
        "res_id": res_block.get("res_id"),
        "res_name": res_block.get("res_name"),
        "station_name": _eg_display_name(eg),
        "ved": getattr(param, "ved", None),
        "federal_district_id": getattr(federal, "id", None)
        or getattr(district, "id_federal_district", None),
        "federal_district": (getattr(federal, "name", None) or "").strip() or None,
        "synchronous_area_id": getattr(sync_area, "id", None)
        or getattr(district, "id_synchronous_area", None),
        "synchronous_area": (getattr(sync_area, "name", None) or "").strip() or None,
    }


def _list_pg_groups_from_fuel(
    sheet_slug: str,
    *,
    start_year: int,
    end_year: int,
    territory_filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[int]]:
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        build_equipment_group_fuel_params_hierarchy,
        collect_numb1120_filter_choices,
        get_equipment_groups_with_fuel_params_data,
        should_suppress_aggregate_rows_for_filters,
    )

    slug = str(sheet_slug or "").strip()
    if slug not in ANALYSIS_SHEET_SLUGS:
        return [], []

    fuel_filters = _territory_filters_to_fuel_filters(territory_filters)
    # Годы ячеек подставляются позже из оверлеев; здесь достаточно уникальных групп.
    fuel_data = get_equipment_groups_with_fuel_params_data(
        filters=fuel_filters,
        start_year=start_year,
        end_year=start_year,
        show_all=True,
        per_page="all",
        page=1,
    )
    rows = _unique_eg_rows(list(fuel_data.get("rows") or []))
    numb1120_filter_choices = list(fuel_data.get("numb1120_filter_choices") or [])
    if not numb1120_filter_choices:
        numb1120_filter_choices = collect_numb1120_filter_choices(rows)

    version_id = get_current_db_version_id()
    if slug in BEZ_KOT_SHEET_SLUGS:
        boiler_eg_ids = get_boiler_equipment_group_ids(version_id)
        rows = [
            (eg, param)
            for eg, param in rows
            if eg is not None and not _is_boiler_group(eg, boiler_eg_ids)
        ]
    rows = _filter_listing_rows(
        rows,
        territory_filters,
        start_year=start_year,
        end_year=end_year,
        version_id=version_id,
    )

    fuel_hierarchy = build_equipment_group_fuel_params_hierarchy(
        rows,
        use_equipment_group_hierarchy_only=False,
        suppress_aggregate_rows=should_suppress_aggregate_rows_for_filters(fuel_filters),
    )

    groups: list[dict[str, Any]] = []
    for est_block, ues_block, res_block, _station_block, group_block in _iter_fuel_group_blocks(
        fuel_hierarchy
    ):
        if group_block.get("is_composite_total_row"):
            continue
        eg = group_block.get("equipment_group")
        if eg is None:
            continue
        sample_param = None
        for _eg, param in group_block.get("rows") or []:
            sample_param = param
            break
        group_id = _eg_display_numb(eg, sample_param) or f"eg-{getattr(eg, 'id', None)}"
        groups.append(
            {
                "id": group_id,
                "numb": group_id if isinstance(group_id, int) else None,
                "meta": {
                    "est_id": est_block.get("est_id"),
                    "est_name": est_block.get("est_name"),
                    "ues_id": ues_block.get("ues_id"),
                    "ues_name": ues_block.get("ues_name"),
                    "res_id": res_block.get("res_id"),
                    "res_name": res_block.get("res_name"),
                    "station_name": _eg_display_name(eg),
                },
                "rowspan": 0,
                "filled_by_year": {},
                "equipment_group": eg,
                "sample_param": sample_param,
                "is_composite_parent": bool(group_block.get("is_composite_parent")),
                "is_composite_child": bool(group_block.get("is_composite_child")),
                "show_composite_cluster": bool(group_block.get("show_composite_cluster")),
                "rows": [],
            }
        )
    return groups, numb1120_filter_choices


def fill_pg_group_year_rows(
    groups: list[dict[str, Any]],
    *,
    sheet_slug: str,
    start_year: int,
    end_year: int,
    territory_filters: dict[str, Any],
    source_columns: list[dict[str, Any]],
    visible_columns: list[dict[str, Any]],
    digits: int,
) -> None:
    """Заполняет годовые строки только для переданных групп (обычно текущая страница)."""
    from app.ecology.services.analysis_pg_param_services import (
        seed_missing_analysis_pg_params_from_reports,
    )
    from app.ecology.services.gis_tes_fuel_comparison_services import (
        _compute_derived_columns,
        _display_is_nonzero,
        _format_value,
        _group_meta,
        _is_empty_numeric_row,
        apply_fuel_indicators,
        apply_pg_ecology_overlay,
        apply_zv_ecology_overlay,
        load_fuel_indicators_by_numb_year,
        load_pg_ecology_overlay_by_numb_year,
        load_zv_ecology_overlay_by_numb_year,
        row_matches_territory_filters,
    )

    slug = str(sheet_slug or "").strip()
    if slug not in ANALYSIS_SHEET_SLUGS or not groups:
        return
    years: list[int] = list(range(int(start_year), int(end_year) + 1))
    numbs: set[int] = {
        int(group["numb"])
        for group in groups
        if isinstance(group.get("numb"), int)
    }
    if slug in PG_ANALYSIS_SHEET_SLUGS:
        seed_missing_analysis_pg_params_from_reports(
            slug,
            station_numbs=numbs or None,
            years=years,
        )
    fuel_overlay = load_fuel_indicators_by_numb_year(numbs, years)
    pg_overlay = (
        load_pg_ecology_overlay_by_numb_year(slug, numbs, years)
        if slug in PG_ANALYSIS_SHEET_SLUGS
        else {}
    )
    zv_overlay = (
        load_zv_ecology_overlay_by_numb_year(slug, numbs, years)
        if slug in ZV_ANALYSIS_SHEET_SLUGS
        else {}
    )

    for group in groups:
        eg = group.get("equipment_group")
        if eg is None:
            continue
        sample_param = group.get("sample_param")
        meta = group.get("meta") or {}
        est_block = {
            "est_id": meta.get("est_id"),
            "est_name": meta.get("est_name"),
        }
        ues_block = {
            "ues_id": meta.get("ues_id"),
            "ues_name": meta.get("ues_name"),
        }
        res_block = {
            "res_id": meta.get("res_id"),
            "res_name": meta.get("res_name"),
        }
        year_items: list[dict[str, Any]] = []
        filled_by_year: dict[int, list[Any]] = {}
        for year in years:
            numb = _eg_display_numb(eg, sample_param)
            filled = _blank_filled(source_columns)
            filled = _apply_group_identity(
                filled,
                source_columns,
                eg=eg,
                year=year,
                param=sample_param,
            )
            filled = apply_fuel_indicators(filled, source_columns, fuel_overlay)
            if pg_overlay:
                filled = apply_pg_ecology_overlay(filled, source_columns, pg_overlay)
            if zv_overlay:
                filled = apply_zv_ecology_overlay(filled, source_columns, zv_overlay)
            fuel = fuel_overlay.get((numb, year)) if numb is not None else None
            if fuel is None:
                fuel = _fallback_fuel_dict(
                    eg, sample_param, est_block, ues_block, res_block
                )
            if not row_matches_territory_filters(
                filled, source_columns, fuel, territory_filters
            ):
                continue
            filled = _compute_derived_columns(filled, source_columns)
            cells = [
                _format_value(
                    filled[column["source_index"]]
                    if column["source_index"] < len(filled)
                    else None,
                    column["numeric"],
                    digits,
                )
                for column in visible_columns
            ]
            cell_nonzero = [
                bool(column.get("diff_highlight")) and _display_is_nonzero(text)
                for column, text in zip(visible_columns, cells)
            ]
            visible_filled = [
                filled[column["source_index"]]
                if column["source_index"] < len(filled)
                else None
                for column in visible_columns
            ]
            year_items.append(
                {
                    "key": f"{slug}-eg{getattr(eg, 'id', '')}-{year}",
                    "year": year,
                    "cells": cells,
                    "cell_nonzero": cell_nonzero,
                    "is_empty": _is_empty_numeric_row(visible_filled, visible_columns),
                    "fuel": fuel,
                    "filled": filled,
                }
            )
            filled_by_year[year] = filled

        if not year_items:
            group["rows"] = []
            group["rowspan"] = 0
            group["filled_by_year"] = {}
            continue
        year_items.sort(key=lambda item: (item["year"] is None, item["year"] or 0))
        meta_src = next(
            (
                item
                for item in year_items
                if (item.get("fuel") or {}).get("ues_id") is not None
            ),
            year_items[0],
        )
        filled_meta = _group_meta(
            meta_src.get("fuel"),
            meta_src.get("filled") or [],
            source_columns,
        )
        filled_meta["est_id"] = meta.get("est_id")
        filled_meta["est_name"] = meta.get("est_name") or filled_meta.get("est_name")
        filled_meta["ues_id"] = meta.get("ues_id")
        filled_meta["ues_name"] = meta.get("ues_name") or filled_meta.get("ues_name")
        filled_meta["res_id"] = meta.get("res_id")
        filled_meta["res_name"] = meta.get("res_name") or filled_meta.get("res_name")
        filled_meta["station_name"] = _eg_display_name(eg)
        group["meta"] = filled_meta
        group["rowspan"] = len(year_items)
        group["filled_by_year"] = filled_by_year
        group["rows"] = [
            {
                "key": item["key"],
                "year": item["year"],
                "cells": item["cells"],
                "cell_nonzero": item["cell_nonzero"],
                "is_empty": item["is_empty"],
                "is_group_first": loop_i == 0,
            }
            for loop_i, item in enumerate(year_items)
        ]


def collect_pg_groups_from_fuel(
    sheet_slug: str,
    *,
    start_year: int,
    end_year: int,
    territory_filters: dict[str, Any],
    source_columns: list[dict[str, Any]],
    visible_columns: list[dict[str, Any]],
    digits: int,
    hydrate: bool = True,
) -> tuple[list[dict[str, Any]], list[int]]:
    """
    Состав отображаемых групп — из модуля Топливо (как edit_data).
    К строкам подтягиваются ТЭП и параметры/отчёт ПГ либо отчётные ЗВ.

    hydrate=False — только состав/иерархия без расчёта ячеек (для пагинации).
    """
    groups, numb1120_filter_choices = _list_pg_groups_from_fuel(
        sheet_slug,
        start_year=start_year,
        end_year=end_year,
        territory_filters=territory_filters,
    )
    if hydrate:
        fill_pg_group_year_rows(
            groups,
            sheet_slug=sheet_slug,
            start_year=start_year,
            end_year=end_year,
            territory_filters=territory_filters,
            source_columns=source_columns,
            visible_columns=visible_columns,
            digits=digits,
        )
        groups = [group for group in groups if group.get("rows")]
    return groups, numb1120_filter_choices
