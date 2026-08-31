# -*- coding: utf-8 -*-
"""Страницы «Расчет балансов электрической энергии» по макету БЭ_ЕЭС.

Листы те же, что у баланса мощности (ЕЭС, СЗ, ОЭС). Строки — потребление ЭЭ,
заряд ГАЭС, экспорт, выработка по типам станций и перетоки (млн.кВт·ч); внизу —
установленная мощность по типам станций (МВт) и ЧЧИУМ (ч).
"""

from __future__ import annotations

from typing import Any

from app.energy_balance.services.ee_balance_consumption_services import (
    load_ee_balance_consumption_inputs,
)
from app.energy_balance.services.ee_balance_gaes_charge_services import (
    GAES_CHARGE_ROW_KEY,
    load_ee_balance_gaes_charge_inputs,
)
from app.energy_balance.services.ee_balance_export_services import (
    EXPORT_ROW_KEY,
    load_ee_balance_export_inputs,
)
from app.energy_balance.services.balance_sheet_note_services import (
    BALANCE_KIND_EE,
    attach_balance_sheet_notes,
)
from app.energy_balance.services.ee_balance_generation_services import (
    generation_type_groups,
    generation_type_keys,
    load_ee_balance_generation_inputs,
)
from app.energy_balance.services.ee_balance_manual_generation_services import (
    load_ee_balance_manual_generation_inputs,
    mark_manual_plan_generation_rows,
    overlay_manual_generation_inputs,
)
from app.energy_balance.services.power_balance_page_services import (
    EES_SOURCE_SLUGS,
    KIND_CHILD,
    KIND_TOTAL,
    KIND_TRANSFER,
    POWER_BALANCE_UNIT,
    SZ1_ADD_SLUGS,
    SZ1_SUB_SLUGS,
    apply_custom_flows_to_tables,
    apply_power_balance_input_values,
    build_power_balance_station_list_url,
    evaluate_power_balance_tables,
    format_power_balance_cell,
    get_power_balance_filter_year_list,
    get_power_balance_sheets,
    get_power_balance_year_columns,
    get_power_balance_year_features,
    first_row_active_slug,
    group_power_balance_sheets,
    is_persistable_power_balance_slug,
    is_power_balance_flow_block_row,
    load_power_balance_installed_capacity_inputs,
    mark_power_balance_empty_rows,
    power_balance_station_list_query,
    resolve_power_balance_rounding_digits,
    tites_east_child_nav_sheets,
    _attach_formula_tooltips,
    _diff_formula,
    _installed_capacity_rows,
    _merge_power_balance_inputs,
    _raw_cell,
    _row,
    _sheet_sum_formula,
    _sheets_including_slug,
    _sum_formula,
)

EE_BALANCE_UNIT = "млн.кВт·ч"
EE_BALANCE_TITLE_PREFIX = "Баланс электрической энергии"
CHIIM_UNIT = "ч."
# млн.кВт·ч / МВт → часы (1 млн.кВт·ч = 1000 МВт·ч).
CHIIM_HOURS_SCALE = 1000
CHIIM_ROUNDING_DIGITS = -1

HYDRO_YEAR_AVERAGE = "average"
HYDRO_YEAR_LOW = "low"
HYDRO_YEAR_AVERAGE_LABEL = "средневодный год"
HYDRO_YEAR_LOW_LABEL = "маловодный год"
HYDRO_INSTALLED_ROW_KEYS = ("installed_ges", "installed_gaes")

is_ee_balance_flow_block_row = is_power_balance_flow_block_row
is_persistable_ee_balance_slug = is_persistable_power_balance_slug
group_ee_balance_sheets = group_power_balance_sheets
get_ee_balance_filter_year_list = get_power_balance_filter_year_list
get_ee_balance_year_columns = get_power_balance_year_columns
get_ee_balance_year_features = get_power_balance_year_features
resolve_ee_balance_rounding_digits = resolve_power_balance_rounding_digits
format_ee_balance_cell = format_power_balance_cell


def _as_ee_sheet(sheet: dict[str, Any] | None) -> dict[str, Any] | None:
    if sheet is None:
        return None
    item = dict(sheet)
    name = str(item.get("sheet_name") or "").strip()
    item["title"] = f"{EE_BALANCE_TITLE_PREFIX} {name}".strip()
    item["unit"] = EE_BALANCE_UNIT
    return item


def get_ee_balance_sheets() -> list[dict[str, Any]]:
    return [_as_ee_sheet(sheet) for sheet in get_power_balance_sheets()]


def get_ee_balance_sheet(slug: str) -> dict[str, Any] | None:
    wanted = str(slug or "").strip()
    if not wanted:
        return None
    for sheet in get_ee_balance_sheets():
        if sheet["slug"] == wanted:
            return sheet
    from app.energy_balance.services.power_balance_page_services import (
        _synthetic_sheet_for_slug,
    )

    return _as_ee_sheet(_synthetic_sheet_for_slug(wanted))


def resolve_ee_balance_hydro_year(value: Any) -> str:
    raw = str(value or "").strip().casefold().replace("ё", "е")
    if raw in {HYDRO_YEAR_LOW, "malovodnyy", "маловодный"}:
        return HYDRO_YEAR_LOW
    return HYDRO_YEAR_AVERAGE


def ee_balance_hydro_year_label(hydro_year: Any) -> str:
    if resolve_ee_balance_hydro_year(hydro_year) == HYDRO_YEAR_LOW:
        return HYDRO_YEAR_LOW_LABEL
    return HYDRO_YEAR_AVERAGE_LABEL


def format_ee_balance_page_title(base_title: str, *, hydro_year: Any = None) -> str:
    """«Баланс электрической энергии … (средневодный/маловодный год)»."""
    title = str(base_title or "").strip()
    if not title or hydro_year is None:
        return title
    suffix = ee_balance_hydro_year_label(hydro_year)
    marker = f"({suffix})"
    if title.endswith(marker):
        return title
    return f"{title} {marker}"


def sheet_has_ges_or_gaes_capacity(
    rows: list[dict[str, Any]] | None,
    years: list[int] | None,
) -> bool:
    """True, если установленная мощность ГЭС или ГАЭС > 0 хотя бы в одном году."""
    if not rows or not years:
        return False
    wanted = set(HYDRO_INSTALLED_ROW_KEYS)
    for row in rows:
        if str(row.get("key") or "") not in wanted:
            continue
        for year in years:
            try:
                if _raw_cell(row, year) > 0:
                    return True
            except Exception:
                continue
    return False


def _hydro_year_buttons(sheet_name: str) -> list[dict[str, str]]:
    name = str(sheet_name or "").strip()
    suffix_average = HYDRO_YEAR_AVERAGE_LABEL
    suffix_low = HYDRO_YEAR_LOW_LABEL
    return [
        {
            "key": HYDRO_YEAR_AVERAGE,
            "label": f"{name} ({suffix_average})" if name else suffix_average,
        },
        {
            "key": HYDRO_YEAR_LOW,
            "label": f"{name} ({suffix_low})" if name else suffix_low,
        },
    ]


def _ee_sheets_including_slug(slug: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    sheets, sheet = _sheets_including_slug(slug)
    return [_as_ee_sheet(item) for item in sheets], _as_ee_sheet(sheet)


def _ee_row(key: str, label: str, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("unit", EE_BALANCE_UNIT)
    return _row(key, label, **kwargs)


def load_ee_balance_custom_flows(
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    try:
        from app.energy_balance.services.ee_balance_custom_flow_services import (
            load_ee_balance_custom_flows as _load,
        )

        return _load(sheets=sheets)
    except Exception:
        return {}


def _generation_rows(*, type_formula_builder=None) -> list[dict[str, Any]]:
    type_groups = generation_type_groups()
    type_keys = generation_type_keys(type_groups)
    rows = [
        _ee_row(
            "generation_total",
            "Выработка электрической энергии",
            kind=KIND_TOTAL,
            formula=_sum_formula(*type_keys) if type_keys else None,
        ),
    ]
    for group in type_groups:
        formula = type_formula_builder(group["key"]) if type_formula_builder is not None else None
        rows.append(
            _ee_row(
                group["key"],
                group["label"],
                indent=1,
                kind=KIND_CHILD,
                formula=formula,
            )
        )
    return rows


def _demand_and_coverage_rows(
    *,
    source_slugs: tuple[str, ...] | None = None,
    subtract_slugs: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    def _agg(row_key: str) -> dict[str, Any] | None:
        if not source_slugs:
            return None
        return _sheet_sum_formula(row_key, source_slugs, subtract_slugs)

    return [
        _ee_row("consumption", "Потребление электрической энергии"),
        _ee_row(GAES_CHARGE_ROW_KEY, "Заряд ГАЭС"),
        _ee_row(EXPORT_ROW_KEY, "Экспорт электрической энергии", editable_values=True),
        _ee_row(
            "demand_total",
            "Итого потребность в электрической энергии",
            kind=KIND_TOTAL,
            formula=_sum_formula("consumption", GAES_CHARGE_ROW_KEY, EXPORT_ROW_KEY),
        ),
        *_generation_rows(type_formula_builder=_agg if source_slugs else None),
        _ee_row(
            "coverage_total",
            "Итого покрытие потребности",
            kind=KIND_TOTAL,
            formula=_sum_formula("generation_total"),
        ),
        _ee_row(
            "surplus_deficit",
            "Дефицит (−)/избыток (+)",
            kind=KIND_TOTAL,
            formula=_diff_formula("coverage_total", "demand_total"),
        ),
    ]


def _transfer_and_final_rows() -> list[dict[str, Any]]:
    return [
        _ee_row(
            "flow_total",
            "Переток электрической энергии в смежные энергосистемы выдача (−)/прием (+)",
            kind=KIND_TOTAL,
            formula=_sum_formula("flow_in", "flow_out"),
        ),
        _ee_row("flow_in", "Получение электрической энергии (+)", indent=1, kind=KIND_TRANSFER),
        _ee_row("flow_out", "Передача электрической энергии (−)", indent=1, kind=KIND_TRANSFER),
        _ee_row(
            "surplus_deficit_with_flow",
            "Дефицит (−)/избыток (+) с учетом перетока электрической энергии в смежные энергосистемы",
            kind=KIND_TOTAL,
            formula=_sum_formula("surplus_deficit", "flow_total"),
        ),
    ]


def _installed_capacity_block(
    *,
    source_slugs: tuple[str, ...] | None = None,
    subtract_slugs: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    def _agg(row_key: str) -> dict[str, Any] | None:
        if not source_slugs:
            return None
        return _sheet_sum_formula(row_key, source_slugs, subtract_slugs)

    rows = _installed_capacity_rows(
        type_formula_builder=_agg if source_slugs else None
    )
    for row in rows:
        row["unit"] = POWER_BALANCE_UNIT
    return rows


def _ratio_formula(numerator_key: str, denominator_key: str, *, tooltip: str) -> dict[str, Any]:
    return {
        "op": "ratio",
        "numerator": numerator_key,
        "denominator": denominator_key,
        "scale": CHIIM_HOURS_SCALE,
        "tooltip": tooltip,
    }


def _chiim_row(key: str, label: str, *, indent: int = 0, kind: str, formula: dict[str, Any]) -> dict[str, Any]:
    row = _ee_row(key, label, indent=indent, kind=kind, unit=CHIIM_UNIT, formula=formula)
    row["rounding_digits"] = CHIIM_ROUNDING_DIGITS
    return row


def _chiim_block() -> list[dict[str, Any]]:
    type_groups = generation_type_groups()
    rows = [
        _chiim_row(
            "chiim_total",
            "ЧЧИУМ",
            kind=KIND_TOTAL,
            formula=_ratio_formula(
                "generation_total",
                "installed_total",
                tooltip=(
                    "ЧЧИУМ = Выработка электрической энергии (млн.кВт·ч) × 1000 "
                    "/ Установленная мощность (МВт)"
                ),
            ),
        ),
    ]
    for group in type_groups:
        gen_key = str(group.get("key") or "")
        suffix = gen_key[len("generation_") :] if gen_key.startswith("generation_") else gen_key
        label = str(group.get("label") or "").strip() or suffix
        rows.append(
            _chiim_row(
                f"chiim_{suffix}",
                label,
                indent=1,
                kind=KIND_CHILD,
                formula=_ratio_formula(
                    gen_key,
                    f"installed_{suffix}",
                    tooltip=(
                        f"{label} = Выработка электрической энергии {label} (млн.кВт·ч) × 1000 "
                        f"/ Установленная мощность {label} (МВт)"
                    ),
                ),
            )
        )
    return rows


def _rows_standard() -> list[dict[str, Any]]:
    return [
        *_demand_and_coverage_rows(),
        *_transfer_and_final_rows(),
        *_installed_capacity_block(),
        *_chiim_block(),
    ]


def _rows_ees_rossii(
    source_slugs: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    slugs = tuple(source_slugs or EES_SOURCE_SLUGS)
    return [
        *_demand_and_coverage_rows(source_slugs=slugs),
        *_transfer_and_final_rows(),
        *_installed_capacity_block(source_slugs=slugs),
        *_chiim_block(),
    ]


def _rows_sz1(
    source_slugs: tuple[str, ...] | list[str] | None = None,
    subtract_slugs: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    add_slugs = tuple(source_slugs or SZ1_ADD_SLUGS)
    sub_slugs = tuple(SZ1_SUB_SLUGS if subtract_slugs is None else subtract_slugs)
    return [
        *_demand_and_coverage_rows(source_slugs=add_slugs, subtract_slugs=sub_slugs),
        *_transfer_and_final_rows(),
        *_installed_capacity_block(source_slugs=add_slugs, subtract_slugs=sub_slugs),
        *_chiim_block(),
    ]


_LAYOUT_BUILDERS = {
    "oes_standard": _rows_standard,
    "oes_yug": _rows_standard,
    "oes_sibir": _rows_standard,
    "oes_vostok": _rows_standard,
    "ees_rossii": _rows_ees_rossii,
    "sz1": _rows_sz1,
    "kaliningrad": _rows_standard,
}


def build_ee_balance_rows(
    layout: str,
    *,
    source_slugs: tuple[str, ...] | list[str] | None = None,
    subtract_slugs: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    if layout == "ees_rossii":
        return _rows_ees_rossii(source_slugs=source_slugs)
    if layout == "sz1":
        return _rows_sz1(source_slugs=source_slugs, subtract_slugs=subtract_slugs)
    builder = _LAYOUT_BUILDERS.get(layout)
    if builder is None:
        raise KeyError(f"Неизвестный макет баланса электрической энергии: {layout}")
    return builder()


def _force_ee_units(tables: dict[str, dict[str, Any]]) -> None:
    for payload in tables.values():
        for row in payload.get("rows") or []:
            key = str(row.get("key") or "")
            if key.startswith("installed_"):
                row["unit"] = POWER_BALANCE_UNIT
            elif key.startswith("chiim_"):
                row["unit"] = CHIIM_UNIT
            else:
                row["unit"] = EE_BALANCE_UNIT


def build_ee_balance_tables(
    years: list[int] | None = None,
    inputs: dict[str, dict[str, dict[int, Any]]] | None = None,
    rounding_digits: int | None = None,
    custom_flows: dict[str, list[dict[str, Any]]] | None = None,
    sheets: list[dict[str, Any]] | None = None,
    hydro_year: Any = None,
) -> dict[str, dict[str, Any]]:
    if years is None:
        years = get_ee_balance_year_columns()
    digits = resolve_ee_balance_rounding_digits(rounding_digits)
    if sheets is None:
        sheets = get_ee_balance_sheets()
    tables: dict[str, dict[str, Any]] = {}
    sheets_by_slug: dict[str, dict[str, Any]] = {}
    for sheet in sheets:
        if sheet.get("skip_table"):
            continue
        slug = sheet["slug"]
        sheets_by_slug[slug] = dict(sheet)
        tables[slug] = {
            "sheet": dict(sheet),
            "rows": build_ee_balance_rows(
                sheet["layout"],
                source_slugs=sheet.get("source_slugs"),
                subtract_slugs=sheet.get("subtract_slugs"),
            ),
        }
    if custom_flows is None:
        try:
            custom_flows = load_ee_balance_custom_flows(sheets=sheets)
        except Exception:
            custom_flows = {}
    custom_inputs = apply_custom_flows_to_tables(tables, custom_flows)
    if inputs is None:
        generation_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        consumption_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        gaes_charge_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        export_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        capacity_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        try:
            generation_inputs = load_ee_balance_generation_inputs(
                years,
                sheets=sheets,
                hydro_year=resolve_ee_balance_hydro_year(hydro_year),
            )
        except Exception:
            generation_inputs = {}
        try:
            generation_inputs = overlay_manual_generation_inputs(
                generation_inputs,
                load_ee_balance_manual_generation_inputs(years, sheets=sheets),
            )
        except Exception:
            pass
        try:
            consumption_inputs = load_ee_balance_consumption_inputs(years, sheets=sheets)
        except Exception:
            consumption_inputs = {}
        try:
            gaes_charge_inputs = load_ee_balance_gaes_charge_inputs(years, sheets=sheets)
        except Exception:
            gaes_charge_inputs = {}
        try:
            export_inputs = load_ee_balance_export_inputs(years, sheets=sheets)
        except Exception:
            export_inputs = {}
        try:
            capacity_inputs = load_power_balance_installed_capacity_inputs(
                years, sheets=sheets
            )
        except Exception:
            capacity_inputs = {}
        inputs = _merge_power_balance_inputs(
            generation_inputs,
            consumption_inputs,
            gaes_charge_inputs,
            export_inputs,
            capacity_inputs,
        )
    inputs = _merge_power_balance_inputs(inputs, custom_inputs)
    apply_power_balance_input_values(tables, inputs, rounding_digits=digits)
    _force_ee_units(tables)
    _attach_formula_tooltips(tables, sheets_by_slug, rounding_digits=digits)
    evaluate_power_balance_tables(tables, years, rounding_digits=digits)
    mark_manual_plan_generation_rows(tables, years)
    for payload in tables.values():
        mark_power_balance_empty_rows(payload["rows"], years)
    attach_balance_sheet_notes(tables, BALANCE_KIND_EE)
    return tables


def build_ee_balance_table_context(
    slug: str,
    *,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    hydro_year: Any = None,
) -> dict[str, Any] | None:
    sheets, sheet = _ee_sheets_including_slug(slug)
    if sheet is None:
        return None
    years = get_ee_balance_year_columns(start_year, end_year)
    digits = resolve_ee_balance_rounding_digits(rounding_digits)
    resolved_hydro_year = resolve_ee_balance_hydro_year(hydro_year)
    tables = build_ee_balance_tables(
        years,
        rounding_digits=digits,
        sheets=sheets,
        hydro_year=resolved_hydro_year,
    )
    payload = tables.get(sheet["slug"])
    if payload is None:
        return None
    start = years[0] if years else None
    end = years[-1] if years else None
    station_query = power_balance_station_list_query(sheet, sheets, start, end)
    show_hydro_year_nav = sheet_has_ges_or_gaes_capacity(payload["rows"], years)
    return {
        "sheet": payload["sheet"],
        "sheets": sheets,
        "sheet_groups": group_ee_balance_sheets(sheets),
        "tites_east_child_sheets": tites_east_child_nav_sheets(sheets, sheet["slug"]),
        "first_row_active_slug": first_row_active_slug(sheet, sheet["slug"]),
        "page_title": format_ee_balance_page_title(
            sheet["title"],
            hydro_year=resolved_hydro_year if show_hydro_year_nav else None,
        ),
        "years": years,
        "year_features": get_ee_balance_year_features(),
        "start_year": start,
        "end_year": end,
        "filter_year_list": get_ee_balance_filter_year_list(),
        "rounding_digits": digits,
        "station_list_url": build_power_balance_station_list_url(station_query),
        "rows": payload["rows"],
        "show_hydro_year_nav": show_hydro_year_nav,
        "hydro_year": resolved_hydro_year if show_hydro_year_nav else None,
        "hydro_year_buttons": (
            _hydro_year_buttons(sheet["sheet_name"]) if show_hydro_year_nav else []
        ),
    }
