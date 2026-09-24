# -*- coding: utf-8 -*-
"""Итоговые суммы модуля «Экология»: ЕЭС / ТИТЭС / ФО / СЗ / Россия."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.ecology.services.gis_tes_fuel_comparison_constants import (
    ANALYSIS_SHEET_SLUGS,
    DEFAULT_PER_PAGE,
    PG_ANALYSIS_SHEET_SLUGS,
    PG_ECOLOGY_EDITABLE_KEYS,
    REPORTED_TABLE_COLUMN_KEYS,
    ZV_ANALYSIS_SHEET_SLUGS,
    get_comparison_sheet,
    list_comparison_sheets_for_group,
)
from app.ecology.services.gis_tes_fuel_comparison_services import (
    ROWSPAN_COLUMN_KEYS,
    _year_features,
    apply_fuel_tce_headers,
    apply_fuel_tep_headers,
    apply_pg_ecology_headers,
    apply_pg_fuel_group_headers,
    apply_zv_display_column_order,
    apply_zv_analysis_banner_headers,
    apply_zv_leaf_group_headers,
    ensure_zv_electricity_specific_column,
    build_region_summary_block,
    drop_key_header_row,
    load_comparison_sheet_layout,
    prepare_visible_table,
)
from app.ecology.services.operating_tes_page_services import resolve_rounding_digits
from app.fuel.services.totals_summary.fuel_totals_summary_services import (
    parse_aggregation_types,
)


DEFAULT_ECOLOGY_TOTALS_SHEET = "pg-vse"


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


def _index_groups(groups: list[dict[str, Any]]) -> dict[str, dict[Any, list[dict[str, Any]]]]:
    by_est: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    by_ues: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    by_fo: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    by_sa: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        meta = group.get("meta") or {}
        est_id = meta.get("est_id")
        ues_id = meta.get("ues_id")
        fo_id = meta.get("fo_id")
        sa_id = meta.get("sa_id")
        if est_id is not None and est_id != -1:
            by_est[est_id].append(group)
        if ues_id is not None and ues_id != -1:
            by_ues[ues_id].append(group)
        if fo_id is not None and fo_id != -1:
            by_fo[fo_id].append(group)
        if sa_id is not None and sa_id != -1:
            by_sa[sa_id].append(group)
    return {"est": by_est, "ues": by_ues, "fo": by_fo, "sa": by_sa}


def _attach_block_style(block: dict[str, Any] | None, row_class: str) -> dict[str, Any] | None:
    if not block:
        return None
    block = dict(block)
    block["row_class"] = row_class
    return block


_TOTALS_HIDDEN_COLUMN_KEYS = frozenset({"numb1120"})


def _drop_columns_from_visible_table(
    visible_columns: list[dict[str, Any]],
    header_rows: list[list[dict[str, Any]]],
    *,
    drop_keys: frozenset[str],
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], int]:
    """Убирает столбцы из витрины итогов и пересчитывает sticky-индексы."""
    kept: list[dict[str, Any]] = []
    for column in visible_columns:
        if column.get("key") in drop_keys:
            continue
        kept.append(dict(column))

    sticky_n = 0
    for column in kept:
        if column.get("sticky"):
            column["sticky_index"] = sticky_n
            sticky_n += 1
        else:
            column["sticky_index"] = None

    new_headers: list[list[dict[str, Any]]] = []
    for row in header_rows:
        new_row: list[dict[str, Any]] = []
        for cell in row:
            key = cell.get("column_key")
            if key in drop_keys:
                continue
            new_cell = dict(cell)
            if key:
                for column in kept:
                    if column.get("key") == key:
                        new_cell["sticky"] = bool(column.get("sticky"))
                        if column.get("sticky"):
                            new_cell["col_index"] = column.get("sticky_index")
                        break
            new_row.append(new_cell)
        if new_row:
            new_headers.append(new_row)
    return kept, new_headers, sticky_n


def build_ecology_totals_summary_context(
    *,
    sheet_slug: str = DEFAULT_ECOLOGY_TOTALS_SHEET,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    aggregation_types: list[str] | None = None,
    filter_year_list: list[int] | None = None,
    source_path: str | Path | None = None,
) -> dict[str, Any] | None:
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
    from app.common.services.get_services.years.years_get_services import (
        get_filter_end_year,
        get_filter_start_year,
        get_year_numbers_sorted_for_current_db_version,
    )
    from app.ecology.services.gis_tes_pg_from_fuel_services import (
        collect_pg_groups_from_fuel,
    )

    slug = (sheet_slug or DEFAULT_ECOLOGY_TOTALS_SHEET).strip()
    if slug not in ANALYSIS_SHEET_SLUGS:
        slug = DEFAULT_ECOLOGY_TOTALS_SHEET
    sheet = get_comparison_sheet(slug)
    if sheet is None:
        return None

    parsed = load_comparison_sheet_layout(sheet["slug"], source_path)
    if parsed is None:
        return None

    # Селект = справочник Year текущей версии БД; start/end резолвятся в route (буфер / версия).
    years_catalog = list(filter_year_list or get_year_numbers_sorted_for_current_db_version())
    if not years_catalog:
        years_catalog = list(range(get_filter_start_year(), get_filter_end_year() + 1))
    if not years_catalog:
        return None

    def _clip_year(raw: Any, fallback: int) -> int:
        try:
            year = int(raw)
        except (TypeError, ValueError):
            return fallback
        if year in years_catalog:
            return year
        return min(years_catalog, key=lambda y: abs(y - year))

    default_start = get_filter_start_year()
    default_end = get_filter_end_year()
    start = (
        _clip_year(start_year, default_start)
        if start_year not in (None, "")
        else _clip_year(default_start, years_catalog[0])
    )
    end = (
        _clip_year(end_year, default_end)
        if end_year not in (None, "")
        else _clip_year(default_end, years_catalog[-1])
    )
    if start > end:
        start, end = end, start
    digits = resolve_rounding_digits(rounding_digits)
    if aggregation_types is None:
        agg_types = ["ees"]
    else:
        agg_types = list(aggregation_types)
    if not agg_types:
        # Годы/округление в URL без aggregation_type — как при первом заходе, показываем ЕЭС.
        agg_types = ["ees"]
    source_columns = parsed["columns"]
    if sheet["slug"] in ZV_ANALYSIS_SHEET_SLUGS:
        ensure_zv_electricity_specific_column(
            source_columns,
            parsed["header_rows"],
            parsed.get("rows"),
        )
    visible_columns, header_rows, sticky_col_count = prepare_visible_table(
        source_columns,
        parsed["header_rows"],
    )
    apply_fuel_tep_headers(visible_columns, header_rows)
    apply_fuel_tce_headers(visible_columns, header_rows)
    if sheet["slug"] in PG_ANALYSIS_SHEET_SLUGS:
        apply_pg_fuel_group_headers(visible_columns, header_rows)
        apply_pg_ecology_headers(visible_columns, header_rows)
    if sheet["slug"] in ZV_ANALYSIS_SHEET_SLUGS:
        apply_zv_display_column_order(visible_columns, header_rows)
        apply_zv_leaf_group_headers(visible_columns, header_rows)
        apply_zv_analysis_banner_headers(visible_columns, header_rows)
    drop_key_header_row(header_rows)
    drop_keys = set(_TOTALS_HIDDEN_COLUMN_KEYS)
    if sheet["slug"] in ZV_ANALYSIS_SHEET_SLUGS:
        drop_keys |= set(REPORTED_TABLE_COLUMN_KEYS)
    visible_columns, header_rows, sticky_col_count = _drop_columns_from_visible_table(
        visible_columns,
        header_rows,
        drop_keys=frozenset(drop_keys),
    )
    for column in visible_columns:
        if column.get("key") in PG_ECOLOGY_EDITABLE_KEYS:
            column["editable"] = False

    groups, _choices = collect_pg_groups_from_fuel(
        sheet["slug"],
        start_year=start,
        end_year=end,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=visible_columns,
        digits=digits,
    )
    indexed = _index_groups(groups)

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
    if "russia" in agg_types:
        should_show_totals["total"] = True
    if "fo" in agg_types:
        should_show_totals["federal_districts"] = True
    if "oes" in agg_types:
        should_show_totals["union_energy_systems"] = True
    for est_id in sorted_energy_system_type_ids:
        name_u = (energy_system_type_names.get(est_id) or "").upper()
        if "ees" in agg_types and "ЕЭС" in name_u:
            should_show_totals["energy_system_types"][est_id] = True
        if "tites" in agg_types and "ТИТЭС" in name_u:
            should_show_totals["energy_system_types"][est_id] = True
    for sa_id in sorted_synchronous_area_ids:
        if f"sync_area_{sa_id}" in agg_types:
            should_show_totals["synchronous_areas"][sa_id] = True

    blocks: list[dict[str, Any]] = []
    common = dict(
        source_columns=source_columns,
        visible_columns=visible_columns,
        digits=digits,
    )

    if should_show_totals["federal_districts"]:
        for fd_id in sorted_federal_district_ids:
            fd_groups = indexed["fo"].get(fd_id) or []
            if not fd_groups:
                continue
            block = _attach_block_style(
                build_region_summary_block(
                    fd_groups,
                    federal_district_names.get(fd_id) or str(fd_id),
                    key_prefix=f"sum-fo-{fd_id}",
                    **common,
                ),
                "table-primary",
            )
            if block:
                blocks.append(block)

    if should_show_totals["union_energy_systems"]:
        for ues_id in sorted_union_energy_system_ids:
            ues_groups = indexed["ues"].get(ues_id) or []
            if not ues_groups:
                continue
            block = _attach_block_style(
                build_region_summary_block(
                    ues_groups,
                    union_energy_system_names.get(ues_id) or str(ues_id),
                    key_prefix=f"sum-ues-{ues_id}",
                    **common,
                ),
                "table-success",
            )
            if block:
                blocks.append(block)

    for sa_id in sorted_synchronous_area_ids:
        if not should_show_totals["synchronous_areas"].get(sa_id):
            continue
        sa_groups = indexed["sa"].get(sa_id) or []
        if not sa_groups:
            continue
        block = _attach_block_style(
            build_region_summary_block(
                sa_groups,
                synchronous_area_names.get(sa_id) or str(sa_id),
                key_prefix=f"sum-sa-{sa_id}",
                **common,
            ),
            "table-secondary",
        )
        if block:
            blocks.append(block)

    for est_id in sorted_energy_system_type_ids:
        if not should_show_totals["energy_system_types"].get(est_id):
            continue
        est_groups = indexed["est"].get(est_id) or []
        if not est_groups:
            continue
        name = energy_system_type_names.get(est_id) or str(est_id)
        name_u = name.upper()
        row_class = "table-info" if "ЕЭС" in name_u else "table-warning"
        block = _attach_block_style(
            build_region_summary_block(
                est_groups,
                name,
                key_prefix=f"sum-est-{est_id}",
                **common,
            ),
            row_class,
        )
        if block:
            blocks.append(block)

    if should_show_totals["total"] and groups:
        block = _attach_block_style(
            build_region_summary_block(
                groups,
                "Россия",
                key_prefix="sum-russia",
                **common,
            ),
            "table-danger",
        )
        if block:
            blocks.append(block)

    return {
        "page_title": f"{sheet['page_title']} - агрегационные суммы",
        "sheet": sheet,
        "comparison_sheets": list_comparison_sheets_for_group(sheet["group"]),
        "header_rows": header_rows,
        "columns": visible_columns,
        "blocks": blocks,
        "start_year": start,
        "end_year": end,
        "rounding_digits": digits,
        "aggregation_types": agg_types,
        "should_show_totals": should_show_totals,
        "sorted_energy_system_type_ids": sorted_energy_system_type_ids,
        "sorted_union_energy_system_ids": sorted_union_energy_system_ids,
        "sorted_synchronous_area_ids": sorted_synchronous_area_ids,
        "sorted_federal_district_ids": sorted_federal_district_ids,
        "energy_system_type_names": energy_system_type_names,
        "union_energy_system_names": union_energy_system_names,
        "synchronous_area_names": synchronous_area_names,
        "federal_district_names": federal_district_names,
        "filter_year_list": years_catalog,
        "year_features": _year_features(),
        "sticky_col_count": sticky_col_count,
        "rowspan_column_keys": frozenset(
            key for key in ROWSPAN_COLUMN_KEYS if key not in drop_keys
        ),
        "default_per_page": str(DEFAULT_PER_PAGE),
    }
