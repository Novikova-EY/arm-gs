# -*- coding: utf-8 -*-
"""Страницы «Расчет балансов электрической энергии» по макету БЭ_ЕЭС.

Листы те же, что у баланса мощности (ЕЭС, СЗ, ОЭС). Строки – потребление ЭЭ,
заряд ГАЭС, зарубежные импорт и экспорт, выработка по типам станций и перетоки
(млн.кВт·ч); внизу –
установленная мощность по типам станций (МВт) и ЧЧИУМ (ч).
"""

from __future__ import annotations

import logging
from copy import deepcopy
from decimal import Decimal
from typing import Any

_logger = logging.getLogger(__name__)

from app.energy_balance.services.ee_balance_consumption_services import (
    load_ee_balance_consumption_inputs,
)
from app.energy_balance.services.ee_balance_gaes_charge_services import (
    GAES_CHARGE_ROW_KEY,
    load_ee_balance_gaes_charge_inputs,
)
from app.energy_balance.services.ee_balance_export_services import (
    load_ee_balance_export_inputs,
)
from app.energy_balance.services.balance_sheet_note_services import (
    BALANCE_KIND_EE,
    attach_balance_sheet_notes,
)
from app.energy_balance.services.ee_balance_generation_services import (
    GENERATION_GES_KEY,
    GENERATION_TES_KEY,
    classify_ee_balance_generation_years,
    generation_type_groups,
    generation_type_keys,
    hydro_year_for_balance_sheet,
    load_ee_balance_generation_inputs,
)
from app.energy_balance.services.ee_balance_manual_generation_services import (
    load_ee_balance_manual_generation_inputs,
    mark_manual_plan_generation_rows,
    overlay_manual_generation_inputs,
)
from app.energy_balance.services.ee_balance_tes_forecast_services import (
    is_tes_forecast_sheet,
    is_tites_sibir_tes_forecast_sheet,
    overlay_tes_forecast_generation_inputs,
)
from app.energy_balance.services.ee_import_export_page_services import (
    get_ee_import_export_page_data,
)
from app.energy_balance.services.ee_receive_transfer_oes_page_services import (
    get_ee_receive_transfer_oes_page_data,
)
from app.energy_balance.services.power_balance_page_services import (
    EES_SOURCE_SLUGS,
    GROUP_EES,
    GROUP_OES,
    GROUP_SZ,
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
    _append_formula_terms,
    _attach_formula_tooltips,
    _diff_formula,
    _eu_name_matches,
    _to_decimal,
    _append_station_type_group_rows,
    _installed_capacity_rows,
    _is_tites_isolated_balance_sheet,
    _mark_ses_ves_collapsible,
    _merge_power_balance_inputs,
    _raw_cell,
    _row,
    _section_insert_index,
    _sheet_sum_formula,
    _sheets_including_slug,
    _sum_formula,
)

EE_BALANCE_UNIT = "млн.кВт·ч"
EE_BALANCE_TITLE_PREFIX = "Баланс электрической энергии"
# Короткое имя для названия веб-страницы (заголовок вкладки браузера).
EE_BALANCE_BROWSER_TITLE_PREFIX = "Баланс ЭЭ"
CHIIM_UNIT = "ч."
# млн.кВт·ч / МВт → часы (1 млн.кВт·ч = 1000 МВт·ч).
CHIIM_HOURS_SCALE = 1000
CHIIM_ROUNDING_DIGITS = -1
EE_IMPORT_TOTAL_TOOLTIP = "Сумма импортов электрической энергии"
EE_EXPORT_TOTAL_TOOLTIP = "Сумма экспортов электрической энергии"

HYDRO_YEAR_AVERAGE = "average"
HYDRO_YEAR_LOW = "low"
HYDRO_YEAR_AVERAGE_LABEL = "средневодный год"
HYDRO_YEAR_LOW_LABEL = "маловодный год"
HYDRO_INSTALLED_ROW_KEYS = ("installed_ges", "installed_gaes")

is_ee_balance_flow_block_row = is_power_balance_flow_block_row
is_persistable_ee_balance_slug = is_persistable_power_balance_slug
get_ee_balance_filter_year_list = get_power_balance_filter_year_list
get_ee_balance_year_columns = get_power_balance_year_columns
get_ee_balance_year_features = get_power_balance_year_features
resolve_ee_balance_rounding_digits = resolve_power_balance_rounding_digits
format_ee_balance_cell = format_power_balance_cell


def group_ee_balance_sheets(
    sheets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items = sheets if sheets is not None else get_ee_balance_sheets()
    groups = group_power_balance_sheets(items)
    if not any(sheet["slug"] == "2-sz-ees-vostok" for sheet in items):
        return groups
    # Вторая зона и ОЭС Востока используют один баланс, без дублирования в расчётах.
    oes_group = next((group for group in groups if group["group"] == GROUP_OES), None)
    if oes_group is None:
        oes_group = {"group": GROUP_OES, "sheets": []}
        groups.append(oes_group)
    oes_sheets = oes_group["sheets"]
    if any(sheet["slug"] == "vostok" for sheet in oes_sheets):
        return groups
    sibir_index = next(
        (index for index, sheet in enumerate(oes_sheets) if sheet["slug"] == "sibir"),
        None,
    )
    insert_at = sibir_index + 1 if sibir_index is not None else len(oes_sheets)
    oes_sheets.insert(
        insert_at,
        {"slug": "vostok", "sheet_name": "ОЭС Востока", "group": GROUP_OES},
    )
    return groups


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


def format_ee_balance_browser_title(base_title: str) -> str:
    """«Баланс электрической энергии Северо-Запад» → «Баланс ЭЭ Северо-Запад»."""
    title = str(base_title or "").strip()
    if not title.startswith(EE_BALANCE_TITLE_PREFIX):
        return title
    return f"{EE_BALANCE_BROWSER_TITLE_PREFIX}{title[len(EE_BALANCE_TITLE_PREFIX):]}"


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
                _logger.exception("ee balance page: hydro installed cell parse failed")
                continue
    return False


def _ee_sheets_including_slug(slug: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    sheets, sheet = _sheets_including_slug(slug)
    return [_as_ee_sheet(item) for item in sheets], _as_ee_sheet(sheet)


def _ee_row(key: str, label: str, **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("unit", EE_BALANCE_UNIT)
    return _row(key, label, **kwargs)


_FILTER_LIST_KEYS = (
    "union_energy_system_filter",
    "energy_system_type_filter",
    "regional_energy_system_filter",
    "federal_district_filter",
    "regional_district_filter",
)


def _ee_transfer_filters(
    sheet: dict[str, Any],
    sheets: list[dict[str, Any]],
    years: list[int],
) -> dict[str, Any]:
    """Фильтры перетоков: одиночные id приводим к спискам, как ждет загрузчик."""
    query = power_balance_station_list_query(
        sheet,
        sheets,
        years[0] if years else None,
        years[-1] if years else None,
    )
    for key in _FILTER_LIST_KEYS:
        value = query.get(key)
        if value is None or isinstance(value, (list, tuple, set)):
            continue
        query[key] = [value]
    return query


def _ee_import_export_rows_for_sheet(
    sheet: dict[str, Any],
    sheets: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    plan_years: list[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[int, Decimal]]]:
    """Добавляет к листу зарубежные перетоки из таблицы «Импорт/Экспорт ЭЭ»."""
    query = _ee_transfer_filters(sheet, sheets, years)
    page_data = get_ee_import_export_page_data(
        start_year=years[0] if years else None,
        end_year=years[-1] if years else None,
        rounding_digits=rounding_digits,
        filters=query,
    )

    directions: dict[str, dict[int, dict[str, Any]]] = {
        "export": {},
        "import": {},
    }
    for oes_block in page_data.get("hierarchy") or []:
        try:
            oes_id = int(oes_block.get("ues_id"))
        except (TypeError, ValueError):
            territory = sheet.get("territory") or {}
            if territory.get("kind") != "ues":
                continue
            try:
                oes_id = int(territory.get("id"))
            except (TypeError, ValueError):
                continue
        for transfer_row in oes_block.get("rows") or []:
            direction = transfer_row.get("direction")
            if direction not in directions:
                continue
            try:
                country_id = int(transfer_row.get("country_id"))
            except (TypeError, ValueError):
                continue
            country = directions[direction].setdefault(
                country_id,
                {
                    "name": str(transfer_row.get("country_name") or "").strip(),
                    "ues_id": oes_id,
                    "periods": {},
                },
            )
            for year, value in (transfer_row.get("periods") or {}).items():
                year_int = int(year)
                if value is None:
                    continue
                amount = abs(Decimal(str(value)))
                country["periods"][year_int] = (
                    country["periods"].get(year_int, Decimal(0)) + amount
                )

    rows: list[dict[str, Any]] = []
    inputs: dict[str, dict[int, Decimal]] = {}
    # Экспорт увеличивает, а импорт уменьшает итог потребности.
    for direction, stem, label, total_coeff in (
        ("export", "ee_export", "Экспорт ЭЭ", 1),
        ("import", "ee_import", "Импорт ЭЭ", -1),
    ):
        countries = sorted(
            directions[direction].items(),
            key=lambda item: item[1]["name"].casefold(),
        )
        if not countries:
            row = _ee_row(stem, label)
            row["css_class"] = ""
            row["demand_total_coeff"] = total_coeff
            rows.append(row)
            continue

        total_by_year: dict[int, Decimal] = {}
        for _country_id, country in countries:
            for year, value in country["periods"].items():
                total_by_year[year] = total_by_year.get(year, Decimal(0)) + value

        total_key = f"{stem}_total"
        total_row = _ee_row(
            total_key,
            f"{label}, всего",
            kind=KIND_TOTAL,
            formula=_sum_formula(*(f"{stem}_country_{country_id}" for country_id, _ in countries)),
        )
        total_row["css_class"] = ""
        total_row["demand_total_coeff"] = total_coeff
        total_row["collapsible"] = True
        rows.append(total_row)
        inputs[total_key] = total_by_year

        for country_id, country in countries:
            row_key = f"{stem}_country_{country_id}"
            row = _ee_row(row_key, f"{label} – {country['name']}", indent=1)
            row["value_save_kind"] = "import_export"
            row["row_key"] = row_key
            row["is_group_child"] = True
            row["parent_group_key"] = total_key
            row["direction"] = direction
            row["ues_id"] = country["ues_id"]
            row["country_id"] = country_id
            if plan_years:
                row["editable_values"] = True
                row["editable_years"] = list(plan_years)
            rows.append(row)
            inputs[row_key] = country["periods"]

    return rows, inputs


def _ee_receive_transfer_rows_for_sheet(
    sheet: dict[str, Any],
    sheets: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    plan_years: list[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[int, Decimal]]]:
    """Строит строки межОЭС-перетоков для подразделов «Получение/Передача»."""
    query = _ee_transfer_filters(sheet, sheets, years)
    page_data = get_ee_receive_transfer_oes_page_data(
        start_year=years[0] if years else None,
        end_year=years[-1] if years else None,
        rounding_digits=rounding_digits,
        filters=query,
    )

    allowed_source_ids: set[int] = set()
    raw_source_filter = query.get("union_energy_system_filter")
    if raw_source_filter is not None:
        if not isinstance(raw_source_filter, (list, tuple, set)):
            raw_source_filter = [raw_source_filter]
        for source_id in raw_source_filter:
            try:
                allowed_source_ids.add(int(source_id))
            except (TypeError, ValueError):
                continue
    elif sheet.get("layout") == "ees_rossii":
        for source_sheet in sheets:
            territory = source_sheet.get("territory") or {}
            if source_sheet.get("group") != GROUP_OES or not source_sheet.get("is_ees_member"):
                continue
            if territory.get("kind") != "ues":
                continue
            try:
                allowed_source_ids.add(int(territory.get("id")))
            except (TypeError, ValueError):
                continue

    source_blocks = []
    for block in page_data.get("hierarchy") or []:
        try:
            source_id = int(block.get("ues_id"))
        except (TypeError, ValueError):
            continue
        if allowed_source_ids and source_id not in allowed_source_ids:
            continue
        source_blocks.append(block)
    show_source_name = len(source_blocks) > 1
    rows: list[dict[str, Any]] = []
    inputs: dict[str, dict[int, Decimal]] = {}
    for source_block in source_blocks:
        source_id = int(source_block["ues_id"])
        source_name = str(source_block.get("ues_name") or "").strip()
        for transfer_row in source_block.get("rows") or []:
            direction = transfer_row.get("direction")
            if direction not in {"receive", "transfer"}:
                continue
            try:
                target_id = int(transfer_row.get("country_id"))
            except (TypeError, ValueError):
                continue
            parent_key = "flow_in" if direction == "receive" else "flow_out"
            row_key = f"{parent_key}_oes_{source_id}_{target_id}"
            target_name = str(transfer_row.get("country_name") or "").strip()
            label = f"{source_name} – {target_name}" if show_source_name else target_name
            row = _ee_row(row_key, label, indent=2, kind=KIND_TRANSFER)
            row["flow_section"] = parent_key
            row["is_group_child"] = True
            row["parent_group_key"] = parent_key
            row["value_save_kind"] = "receive_transfer"
            row["row_key"] = row_key
            row["source_ues_id"] = source_id
            row["target_ues_id"] = target_id
            if plan_years:
                row["editable_values"] = True
                row["editable_years"] = list(plan_years)
            rows.append(row)
            inputs[row_key] = {
                int(year): Decimal(str(value))
                for year, value in (transfer_row.get("periods") or {}).items()
                if value is not None
            }

    return rows, inputs


def _add_import_export_to_demand_total(
    rows: list[dict[str, Any]],
    trade_rows: list[dict[str, Any]],
) -> None:
    """Добавляет зарубежные экспорт и импорт как положительные слагаемые итога."""
    total_row = next(
        (row for row in rows if str(row.get("key") or "") == "demand_total"), None
    )
    if total_row is None:
        return
    formula = total_row.get("formula")
    if not isinstance(formula, dict) or formula.get("op") == "ratio":
        return
    terms = list(formula.get("terms") or [])
    for trade_row in trade_rows:
        coeff = trade_row.pop("demand_total_coeff", None)
        if coeff is None:
            continue
        terms.append({"row_key": trade_row["key"], "coeff": coeff})
    total_row["formula"] = {**formula, "terms": terms}


def _is_plan_tes_from_consumption_sheet(sheet: dict[str, Any] | None) -> bool:
    if not sheet:
        return False
    if is_tites_sibir_tes_forecast_sheet(sheet):
        return True
    name = sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
    return any(
        _eu_name_matches(name, needles)
        for needles in (
            ("анад",),
            ("центральный", "сахалин"),
            ("чаун", "билибин"),
            ("центральный", "камчат"),
        )
    )


def _other_generation_amount_for_year(
    row_map: dict[str, dict[int, Any]],
    groups: list[dict[str, Any]],
    tes_key: str,
    year: int,
) -> Decimal:
    total = Decimal("0")
    for group in groups:
        key = str(group.get("key") or "")
        if not key or key == tes_key:
            continue
        children = [child for child in (group.get("children") or []) if child.get("key")]
        if children:
            child_sum = sum(
                (
                    _to_decimal((row_map.get(str(child["key"])) or {}).get(year))
                    for child in children
                ),
                Decimal("0"),
            )
            total += (
                child_sum
                if child_sum != 0
                else _to_decimal((row_map.get(key) or {}).get(year))
            )
        else:
            total += _to_decimal((row_map.get(key) or {}).get(year))
    return total


def _apply_plan_tes_from_consumption(
    inputs: dict[str, dict[str, dict[int, Any]]] | None,
    sheets: list[dict[str, Any]] | None,
    years: list[int],
) -> dict[str, dict[str, dict[int, Any]]]:
    """Плановые годы отдельных энергорайонов: ТЭС = потребление − прочая выработка."""
    merged = inputs or {}
    if not sheets or not years:
        return merged
    _fact, plan_years = classify_ee_balance_generation_years(
        years, get_ee_balance_year_features()
    )
    if not plan_years:
        return merged
    groups = generation_type_groups()
    tes_key = GENERATION_TES_KEY
    for sheet in sheets:
        if not _is_plan_tes_from_consumption_sheet(sheet):
            continue
        slug = str(sheet.get("slug") or "")
        if not slug:
            continue
        row_map = merged.setdefault(slug, {})
        tes_years = dict(row_map.get(tes_key) or {})
        consumption = row_map.get("consumption") or {}
        for year in plan_years:
            residual = _to_decimal(consumption.get(year)) - (
                _other_generation_amount_for_year(row_map, groups, tes_key, int(year))
            )
            tes_years[int(year)] = residual if residual > 0 else Decimal("0")
        row_map[tes_key] = tes_years
    return merged


def _plan_tes_from_consumption_tooltip(groups: list[dict[str, Any]], tes_key: str) -> str:
    pieces: list[str] = ["Потребление электрической энергии"]
    for group in groups:
        key = str(group.get("key") or "")
        if not key or key == tes_key:
            continue
        children = [child for child in (group.get("children") or []) if child.get("label")]
        if children:
            pieces.extend(str(child.get("label") or "").strip() for child in children)
        else:
            label = str(group.get("label") or "").strip()
            if label:
                pieces.append(label)
    tes_label = "ТЭС"
    for group in groups:
        if str(group.get("key") or "") == tes_key:
            tes_label = str(group.get("label") or tes_label).strip() or tes_label
            break
    return f"В прогнозном периоде: {tes_label} = " + " − ".join(pieces)


MAGADAN_TES_FORECAST_TOOLTIP = (
    "Плановые годы: годовые итоги со страницы помесячного расчёта "
    "(форма «БЭ по месяцам») по одноименным строкам."
)


def _mark_plan_tes_from_consumption_tooltip(
    tables: dict[str, dict[str, Any]],
    sheets: list[dict[str, Any]] | None,
) -> None:
    if not sheets:
        return
    groups = generation_type_groups()
    tes_key = GENERATION_TES_KEY
    tooltip = _plan_tes_from_consumption_tooltip(groups, tes_key)
    for sheet in sheets:
        if not _is_plan_tes_from_consumption_sheet(sheet):
            continue
        payload = tables.get(str(sheet.get("slug") or ""))
        if not payload:
            continue
        for row in payload.get("rows") or []:
            if str(row.get("key") or "") == tes_key:
                row["formula_tooltip"] = tooltip
                break


def _mark_magadan_tes_forecast_tooltip(
    tables: dict[str, dict[str, Any]],
    sheets: list[dict[str, Any]] | None,
) -> None:
    if not sheets:
        return
    overlay_keys = {GENERATION_TES_KEY, GENERATION_GES_KEY, "consumption"}
    for sheet in sheets:
        if not is_tes_forecast_sheet(sheet):
            continue
        payload = tables.get(str(sheet.get("slug") or ""))
        if not payload:
            continue
        for row in payload.get("rows") or []:
            if str(row.get("key") or "") in overlay_keys:
                row["formula_tooltip"] = MAGADAN_TES_FORECAST_TOOLTIP


def _mark_import_export_total_tooltips(
    tables: dict[str, dict[str, Any]],
) -> None:
    tooltip_by_key = {
        "ee_import_total": EE_IMPORT_TOTAL_TOOLTIP,
        "ee_export_total": EE_EXPORT_TOTAL_TOOLTIP,
    }
    for payload in tables.values():
        for row in payload.get("rows") or []:
            tooltip = tooltip_by_key.get(str(row.get("key") or ""))
            if tooltip:
                row["formula_tooltip"] = tooltip


def load_ee_balance_custom_flows(
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    try:
        from app.energy_balance.services.ee_balance_custom_flow_services import (
            load_ee_balance_custom_flows as _load,
        )

        return _load(sheets=sheets)
    except Exception:
        _logger.exception("ee balance page: custom flows load failed")
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
    _append_station_type_group_rows(
        rows,
        type_groups,
        make_row=_ee_row,
        type_formula_builder=type_formula_builder,
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
        _ee_row(
            "demand_total",
            "Итого потребность в электрической энергии",
            kind=KIND_TOTAL,
            formula=_sum_formula("consumption", GAES_CHARGE_ROW_KEY),
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
        parent = _chiim_row(
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
        children = list(group.get("children") or [])
        if children:
            _mark_ses_ves_collapsible(parent)
        rows.append(parent)
        for child in children:
            child_gen = str(child.get("key") or "")
            if not child_gen:
                continue
            child_suffix = (
                child_gen[len("generation_") :]
                if child_gen.startswith("generation_")
                else child_gen
            )
            child_label = str(child.get("label") or "").strip() or child_suffix
            child_row = _chiim_row(
                f"chiim_{child_suffix}",
                child_label,
                indent=2,
                kind=KIND_CHILD,
                formula=_ratio_formula(
                    child_gen,
                    f"installed_{child_suffix}",
                    tooltip=(
                        f"{child_label} = Выработка электрической энергии {child_label} (млн.кВт·ч) × 1000 "
                        f"/ Установленная мощность {child_label} (МВт)"
                    ),
                ),
            )
            child_row["italic"] = True
            child_row["is_group_child"] = True
            child_row["parent_group_key"] = f"chiim_{suffix}"
            rows.append(child_row)
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
    del hydro_year
    if years is None:
        years = get_ee_balance_year_columns()
    digits = resolve_ee_balance_rounding_digits(rounding_digits)
    if sheets is None:
        sheets = get_ee_balance_sheets()
    flowless_slugs = {
        sheet["slug"]
        for sheet in sheets
        if sheet["slug"] == "kaliningradskaya-sz-ees"
        or _is_tites_isolated_balance_sheet(sheet)
    }
    receive_transfer_enabled_slugs = {
        str(sheet.get("slug") or "")
        for sheet in sheets
        if sheet.get("ee_balance_receive_transfer")
    }
    tables: dict[str, dict[str, Any]] = {}
    sheets_by_slug: dict[str, dict[str, Any]] = {}
    for sheet in sheets:
        if sheet.get("skip_table"):
            continue
        slug = sheet["slug"]
        sheets_by_slug[slug] = dict(sheet)
        rows = build_ee_balance_rows(
            sheet["layout"],
            source_slugs=sheet.get("source_slugs"),
            subtract_slugs=sheet.get("subtract_slugs"),
        )
        if slug in flowless_slugs and slug not in receive_transfer_enabled_slugs:
            rows = [row for row in rows if not is_ee_balance_flow_block_row(row)]
        tables[slug] = {
            "sheet": dict(sheet),
            "rows": rows,
        }
    import_export_inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    receive_transfer_inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    try:
        _fact_current, plan_years = classify_ee_balance_generation_years(years)
    except Exception:
        _logger.exception("ee balance page: year classification failed")
        plan_years = []
    plan_list = [int(year) for year in plan_years]
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        payload = tables.get(slug)
        if payload is None:
            continue
        if slug not in flowless_slugs:
            try:
                trade_rows, row_inputs = _ee_import_export_rows_for_sheet(
                    sheet, sheets, years, digits, plan_list
                )
            except Exception:
                _logger.exception(
                    "ee balance page: import/export inputs load failed for %s", slug
                )
                import_row = _ee_row("ee_import", "Импорт ЭЭ")
                import_row["css_class"] = ""
                import_row["demand_total_coeff"] = -1
                export_row = _ee_row("ee_export", "Экспорт ЭЭ")
                export_row["css_class"] = ""
                export_row["demand_total_coeff"] = 1
                trade_rows = [export_row, import_row]
                row_inputs = {}
            row_keys = [row.get("key") for row in payload["rows"]]
            insert_at = (
                row_keys.index("demand_total")
                if "demand_total" in row_keys
                else len(payload["rows"])
            )
            payload["rows"][insert_at:insert_at] = trade_rows
            _add_import_export_to_demand_total(payload["rows"], trade_rows)
            if row_inputs:
                import_export_inputs[slug] = row_inputs
        elif slug not in receive_transfer_enabled_slugs:
            continue
        try:
            flow_rows, flow_inputs = _ee_receive_transfer_rows_for_sheet(
                sheet, sheets, years, digits, plan_list
            )
        except Exception:
            _logger.exception(
                "ee balance page: receive/transfer inputs load failed for %s", slug
            )
            flow_rows, flow_inputs = [], {}
        for flow_row in flow_rows:
            parent_key = str(flow_row.get("flow_section") or "")
            insert_at = _section_insert_index(payload["rows"], parent_key)
            if insert_at is None:
                continue
            payload["rows"].insert(insert_at, flow_row)
            parent = next(row for row in payload["rows"] if row.get("key") == parent_key)
            parent["collapsible"] = True
            _append_formula_terms(parent, [str(flow_row["key"])])
        if flow_inputs:
            receive_transfer_inputs[slug] = flow_inputs
    if custom_flows is None:
        try:
            custom_flows = load_ee_balance_custom_flows(sheets=sheets)
        except Exception:
            _logger.exception("ee balance page: custom flows load failed")
            custom_flows = {}
    custom_inputs = apply_custom_flows_to_tables(tables, custom_flows)
    manual_generation_inputs: dict[str, dict[str, dict[int, Any]]] = {}
    if inputs is None:
        generation_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        consumption_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        gaes_charge_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        capacity_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        try:
            generation_inputs = load_ee_balance_generation_inputs(
                years,
                sheets=sheets,
            )
        except Exception:
            _logger.exception("ee balance page: generation inputs load failed")
            generation_inputs = {}
        try:
            manual_generation_inputs = load_ee_balance_manual_generation_inputs(
                years, sheets=sheets
            )
        except Exception:
            _logger.exception("ee balance page: manual generation inputs load failed")
        try:
            consumption_inputs = load_ee_balance_consumption_inputs(years, sheets=sheets)
        except Exception:
            _logger.exception("ee balance page: consumption inputs load failed")
            consumption_inputs = {}
        try:
            gaes_charge_inputs = load_ee_balance_gaes_charge_inputs(years, sheets=sheets)
        except Exception:
            _logger.exception("ee balance page: gaes charge inputs load failed")
            gaes_charge_inputs = {}
        try:
            capacity_inputs = load_power_balance_installed_capacity_inputs(
                years, sheets=sheets
            )
        except Exception:
            _logger.exception("ee balance page: capacity inputs load failed")
            capacity_inputs = {}
        inputs = _merge_power_balance_inputs(
            generation_inputs,
            consumption_inputs,
            gaes_charge_inputs,
            capacity_inputs,
        )
    inputs = _merge_power_balance_inputs(
        inputs, custom_inputs, import_export_inputs, receive_transfer_inputs
    )
    try:
        inputs = overlay_tes_forecast_generation_inputs(inputs, sheets, years)
    except Exception:
        _logger.exception("ee balance page: tes monthly forecast overlay failed")
    _apply_plan_tes_from_consumption(inputs, sheets, years)
    inputs = overlay_manual_generation_inputs(
        inputs, manual_generation_inputs, sheets=sheets, plan_years=plan_list
    )
    apply_power_balance_input_values(tables, inputs, rounding_digits=digits)
    _force_ee_units(tables)
    _attach_formula_tooltips(tables, sheets_by_slug, rounding_digits=digits)
    _mark_import_export_total_tooltips(tables)
    _mark_magadan_tes_forecast_tooltip(tables, sheets)
    _mark_plan_tes_from_consumption_tooltip(tables, sheets)
    evaluate_power_balance_tables(tables, years, rounding_digits=digits)
    mark_manual_plan_generation_rows(tables, years)
    for payload in tables.values():
        mark_power_balance_empty_rows(payload["rows"], years)
    attach_balance_sheet_notes(tables, BALANCE_KIND_EE)
    return tables


URAL_WITHOUT_TYUMEN_SLUG = "ural-without-tyumen"
SEVERO_ZAPAD_CENTER_SLUG = "severo-zapad-center"
EUROPEAN_EES_SLUG = "european-ees"
EUROPEAN_EES_SOURCE_SLUGS = (
    "severo-zapad",
    "centr",
    "yug",
    "srednyaya-volga",
    "ural",
)
EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG = "european-ees-without-south-ural"
EUROPEAN_EES_WITHOUT_SOUTH_URAL_SOURCE_SLUGS = (
    "severo-zapad",
    "centr",
    "srednyaya-volga",
)
EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME = (
    "Европейская часть ЕЭС (без ОЭС Юга и ОЭС Урала)"
)
EES_RUSSIA_WITH_TITES_SLUG = "ees-rossii-with-tites"
EES_RUSSIA_WITH_TITES_NAME = "ЭЭС России"
SYNCHRONOUS_ZONES_SLUG = "synchronous-zones"
SYNCHRONOUS_ZONES_NAME = "Синхронные зоны"


def _ees_rossii_with_tites_navigation_sheet() -> dict[str, Any]:
    return {
        "slug": EES_RUSSIA_WITH_TITES_SLUG,
        "sheet_name": EES_RUSSIA_WITH_TITES_NAME,
        "title": f"{EE_BALANCE_TITLE_PREFIX} {EES_RUSSIA_WITH_TITES_NAME}",
        "group": GROUP_EES,
        "layout": "ees_rossii",
        "source_slugs": EES_SOURCE_SLUGS,
        "subtract_slugs": (),
    }


def _ees_rossii_with_tites_source_slugs(
    sheets: list[dict[str, Any]],
) -> tuple[str, ...]:
    ees_sheet = next(
        (
            item
            for item in sheets
            if item.get("slug") == "ees-rossii" or item.get("layout") == "ees_rossii"
        ),
        None,
    )
    source_slugs = list((ees_sheet or {}).get("source_slugs") or EES_SOURCE_SLUGS)
    tites_hubs = {
        str(item.get("slug") or "")
        for item in sheets
        if item.get("is_tites_east_hub")
    }
    for item in sheets:
        slug = str(item.get("slug") or "")
        if not slug or slug in source_slugs or item.get("skip_table"):
            continue
        name = str(item.get("sheet_name") or "").casefold().replace("ё", "е")
        is_tites = "титес" in name
        is_tites_child = str(item.get("parent_slug") or "") in tites_hubs
        if is_tites or is_tites_child or item.get("station_capacity_breakdown"):
            source_slugs.append(slug)
    return tuple(source_slugs)


def _european_ees_navigation_sheet() -> dict[str, Any]:
    return {
        "slug": EUROPEAN_EES_SLUG,
        "sheet_name": "Европейская часть ЕЭС",
        "group": GROUP_SZ,
        "layout": "sz1",
        "source_slugs": EUROPEAN_EES_SOURCE_SLUGS,
    }


def _european_ees_subtab_sheets() -> list[dict[str, str]]:
    return [
        {"slug": EUROPEAN_EES_SLUG, "sheet_name": "Европейская часть ЕЭС"},
        {
            "slug": EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG,
            "sheet_name": EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME,
        },
    ]


def _ee_balance_navigation_sheets(
    sheets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = list(sheets)
    if not any(item.get("slug") == EES_RUSSIA_WITH_TITES_SLUG for item in result):
        insert_at = next(
            (
                index
                for index, item in enumerate(result)
                if item.get("slug") == "ees-rossii"
            ),
            0,
        )
        result.insert(insert_at, _ees_rossii_with_tites_navigation_sheet())
    sz_index = next(
        (index for index, item in enumerate(result) if item.get("group") == GROUP_SZ),
        None,
    )
    if not any(item.get("slug") == EUROPEAN_EES_SLUG for item in result):
        result.insert(
            sz_index if sz_index is not None else len(result),
            _european_ees_navigation_sheet(),
        )
    if not any(item.get("slug") == SYNCHRONOUS_ZONES_SLUG for item in result):
        first_zone = next(
            (
                item
                for item in result
                if item.get("group") == GROUP_SZ
                and item.get("slug") != EUROPEAN_EES_SLUG
            ),
            None,
        )
        zone_nav_sheet = {
            "slug": SYNCHRONOUS_ZONES_SLUG,
            "sheet_name": SYNCHRONOUS_ZONES_NAME,
            "group": GROUP_SZ,
        }
        if first_zone is not None:
            zone_nav_sheet["first_child_slug"] = first_zone["slug"]
            insert_at = result.index(first_zone)
        else:
            european_index = next(
                (
                    index
                    for index, item in enumerate(result)
                    if item.get("slug") == EUROPEAN_EES_SLUG
                ),
                len(result),
            )
            insert_at = european_index + 1
        result.insert(insert_at, zone_nav_sheet)
    return result


def _synchronous_zone_subtab_sheets(
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Синхронные зоны во второй строке кнопок, без кнопок-хабов."""
    group = next((item for item in groups if item.get("group") == GROUP_SZ), None)
    return [
        sheet
        for sheet in (group or {}).get("sheets") or []
        if sheet.get("slug") not in {SYNCHRONOUS_ZONES_SLUG, EUROPEAN_EES_SLUG}
    ]


def _ural_tyumen_energy_system(sheets: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve the Tyumen regional energy system under ОЭС Ural."""
    ural = next((item for item in sheets if item.get("slug") == "ural"), None)
    territory = (ural or {}).get("territory") or {}
    try:
        ural_id = int(territory["id"])
    except (KeyError, TypeError, ValueError):
        return None

    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
    )

    try:
        regional_systems = list(get_regional_energy_system_list_full() or [])
    except Exception:
        _logger.exception("ee balance page: failed to resolve Tyumen energy system")
        return None

    for res in regional_systems:
        try:
            res_id = int(res.id)
            parent_id = int(res.id_union_energy_system)
        except (AttributeError, TypeError, ValueError):
            continue
        name = str(getattr(res, "name", None) or "").strip()
        normalized_name = name.casefold().replace("ё", "е")
        if parent_id != ural_id or "тюмен" not in normalized_name:
            continue
        if "ханты" not in normalized_name and "ямало" not in normalized_name:
            continue

        from app.energy_balance.services.power_balance_page_services import (
            _synthetic_sheet_for_slug,
        )

        sheet = _as_ee_sheet(_synthetic_sheet_for_slug(f"res-{res_id}"))
        if sheet is None:
            return None
        sheet["sheet_name"] = "Тюменская ЭС"
        sheet["title"] = f"{EE_BALANCE_TITLE_PREFIX} Тюменская ЭС"
        sheet.pop("parent_slug", None)
        sheet["tyumen_energy_system"] = True
        return sheet
    return None


def _severo_zapad_region_sheets(
    sheets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    severo_zapad = next(
        (item for item in sheets if item.get("slug") == "severo-zapad"), None
    )
    try:
        ues_id = int((severo_zapad or {}).get("territory", {})["id"])
    except (KeyError, TypeError, ValueError):
        return []

    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
    )
    from app.energy_balance.services.power_balance_page_services import (
        _synthetic_sheet_for_slug,
    )

    wanted = {
        "archangelsk": ("архангель", "ЭС Архангельской области"),
        "kaliningrad": ("калининград", "ЭС Калининградской области"),
        "komi": ("коми", "ЭС Республики Коми"),
    }
    found: dict[str, dict[str, Any]] = {}
    try:
        regional_systems = list(get_regional_energy_system_list_full() or [])
    except Exception:
        _logger.exception("ee balance page: failed to resolve Severo-Zapad energy systems")
        return []

    for res in regional_systems:
        try:
            parent_id = int(res.id_union_energy_system)
            res_id = int(res.id)
        except (AttributeError, TypeError, ValueError):
            continue
        if parent_id != ues_id:
            continue
        name = str(getattr(res, "name", None) or "").strip()
        normalized_name = name.casefold().replace("ё", "е")
        for key, (token, label) in wanted.items():
            if key in found or token not in normalized_name:
                continue
            sheet = _as_ee_sheet(_synthetic_sheet_for_slug(f"res-{res_id}"))
            if sheet is None:
                continue
            sheet["sheet_name"] = label
            sheet["title"] = f"{EE_BALANCE_TITLE_PREFIX} {label}"
            sheet["severo_zapad_child"] = True
            sheet["ee_balance_receive_transfer"] = key in {"archangelsk", "komi"}
            found[key] = sheet
            break

    return [found[key] for key in wanted] if len(found) == len(wanted) else []


def _severo_zapad_subtab_sheets(
    regional_sheets: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {"slug": "severo-zapad", "sheet_name": "ЭС ОЭС Северо-Запада"},
        {
            "slug": SEVERO_ZAPAD_CENTER_SLUG,
            "sheet_name": "ОЭС Северо-Запада (центр)",
        },
        *[
            {"slug": str(sheet["slug"]), "sheet_name": sheet["sheet_name"]}
            for sheet in regional_sheets
        ],
    ]


def _append_severo_zapad_center_table(
    tables: dict[str, dict[str, Any]],
    regional_slugs: list[str],
    years: list[int],
    rounding_digits: int,
) -> None:
    source = tables.get("severo-zapad")
    regions = [tables.get(slug) for slug in regional_slugs]
    if source is None or any(payload is None for payload in regions):
        return

    center_sheet = dict(source["sheet"])
    center_sheet.update(
        slug=SEVERO_ZAPAD_CENTER_SLUG,
        sheet_name="ОЭС Северо-Запада (центр)",
        title=f"{EE_BALANCE_TITLE_PREFIX} ОЭС Северо-Запада (центр)",
        parent_slug="severo-zapad",
    )
    rows_by_region = [
        {str(row.get("key") or ""): row for row in payload["rows"]}
        for payload in regions
    ]
    center_rows = deepcopy(source["rows"])
    for row in center_rows:
        if not row.get("formula"):
            raw_values = row.setdefault("year_values_raw", {})
            display_values = row.setdefault("year_values", {})
            key = str(row.get("key") or "")
            for year in years:
                value = _to_decimal(raw_values.get(year))
                for region_rows in rows_by_region:
                    value -= _to_decimal(
                        (region_rows.get(key) or {}).get("year_values_raw", {}).get(year)
                    )
                raw_values[year] = value
                display_values[year] = format_ee_balance_cell(
                    value, digits=rounding_digits
                )
        row["editable_values"] = False
        row["editable_label"] = False
        row["can_add_custom_flow"] = False
        row.pop("editable_years", None)
        row.pop("value_save_kind", None)
        row.pop("row_key", None)

    tables[SEVERO_ZAPAD_CENTER_SLUG] = {
        "sheet": center_sheet,
        "rows": center_rows,
    }
    evaluate_power_balance_tables(tables, years, rounding_digits=rounding_digits)
    attach_balance_sheet_notes(
        {SEVERO_ZAPAD_CENTER_SLUG: tables[SEVERO_ZAPAD_CENTER_SLUG]},
        BALANCE_KIND_EE,
    )
    for row in tables[SEVERO_ZAPAD_CENTER_SLUG]["rows"]:
        row["editable_values"] = False
        row["editable_label"] = False
        row["can_add_custom_flow"] = False
        row.pop("editable_years", None)
        row.pop("value_save_kind", None)
        row.pop("row_key", None)
    mark_power_balance_empty_rows(tables[SEVERO_ZAPAD_CENTER_SLUG]["rows"], years)


def _append_european_ees_table(
    tables: dict[str, dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    slug: str = EUROPEAN_EES_SLUG,
    sheet_name: str = "Европейская часть ЕЭС",
    source_slugs: tuple[str, ...] = EUROPEAN_EES_SOURCE_SLUGS,
) -> None:
    source_payloads = [tables.get(source_slug) for source_slug in source_slugs]
    if any(payload is None for payload in source_payloads):
        return

    source_sheet = source_payloads[0]["sheet"]
    aggregate_sheet = dict(source_sheet)
    aggregate_sheet.update(
        slug=slug,
        sheet_name=sheet_name,
        title=f"{EE_BALANCE_TITLE_PREFIX} {sheet_name}",
        group=GROUP_SZ,
        layout="sz1",
        source_slugs=source_slugs,
        subtract_slugs=(),
    )
    aggregate_sheet.pop("territory", None)
    aggregate_sheet.pop("is_ees_member", None)

    aggregate_rows: list[dict[str, Any]] = []
    rows_by_key: dict[str, dict[str, Any]] = {}
    for payload in source_payloads:
        for source_row in payload["rows"]:
            key = str(source_row.get("key") or "")
            if not key:
                continue
            aggregate_row = rows_by_key.get(key)
            if aggregate_row is None:
                aggregate_row = deepcopy(source_row)
                rows_by_key[key] = aggregate_row
                if aggregate_row.get("parent_group_key"):
                    insert_at = _section_insert_index(
                        aggregate_rows, str(aggregate_row["parent_group_key"])
                    )
                    if insert_at is None:
                        aggregate_rows.append(aggregate_row)
                    else:
                        aggregate_rows.insert(insert_at, aggregate_row)
                else:
                    aggregate_rows.append(aggregate_row)
                continue

            formula = aggregate_row.get("formula")
            source_formula = source_row.get("formula")
            if formula is None and source_formula is None:
                raw_values = aggregate_row.setdefault("year_values_raw", {})
                display_values = aggregate_row.setdefault("year_values", {})
                source_raw_values = source_row.get("year_values_raw") or {}
                for year in years:
                    value = _to_decimal(raw_values.get(year)) + _to_decimal(
                        source_raw_values.get(year)
                    )
                    raw_values[year] = value
                    display_values[year] = format_ee_balance_cell(
                        value, digits=rounding_digits
                    )
            elif formula is None and source_formula is not None:
                aggregate_row["formula"] = deepcopy(source_formula)

            if isinstance(aggregate_row.get("formula"), dict) and isinstance(
                source_formula, dict
            ):
                merged_formula = dict(aggregate_row["formula"])
                terms = list(merged_formula.get("terms") or [])
                seen_terms = {repr(term) for term in terms}
                for term in source_formula.get("terms") or []:
                    if repr(term) not in seen_terms:
                        terms.append(deepcopy(term))
                        seen_terms.add(repr(term))
                if "terms" in merged_formula or terms:
                    merged_formula["terms"] = terms
                aggregate_row["formula"] = merged_formula

    for row in aggregate_rows:
        row["editable_values"] = False
        row["editable_label"] = False
        row["can_add_custom_flow"] = False
        row.pop("editable_years", None)
        row.pop("value_save_kind", None)
        row.pop("row_key", None)

    tables[slug] = {"sheet": aggregate_sheet, "rows": aggregate_rows}
    evaluate_power_balance_tables(tables, years, rounding_digits=rounding_digits)
    attach_balance_sheet_notes({slug: tables[slug]}, BALANCE_KIND_EE)
    mark_power_balance_empty_rows(tables[slug]["rows"], years)


def _append_ural_without_tyumen_table(
    tables: dict[str, dict[str, Any]],
    tyumen_slug: str,
    years: list[int],
    rounding_digits: int,
) -> None:
    ural = tables.get("ural")
    tyumen = tables.get(tyumen_slug)
    if ural is None or tyumen is None:
        return

    excluded_slug = URAL_WITHOUT_TYUMEN_SLUG
    excluded_sheet = dict(ural["sheet"])
    excluded_sheet.update(
        slug=excluded_slug,
        sheet_name="ОЭС Урала (без Тюменской ЭС)",
        title=f"{EE_BALANCE_TITLE_PREFIX} ОЭС Урала (без Тюменской ЭС)",
        parent_slug="ural",
    )
    tyumen_rows = {str(row.get("key") or ""): row for row in tyumen["rows"]}
    excluded_rows = deepcopy(ural["rows"])
    for row in excluded_rows:
        tyumen_row = tyumen_rows.get(str(row.get("key") or ""), {})
        if not row.get("formula"):
            raw_values = row.setdefault("year_values_raw", {})
            display_values = row.setdefault("year_values", {})
            tyumen_raw = tyumen_row.get("year_values_raw") or {}
            for year in years:
                value = _to_decimal(raw_values.get(year)) - _to_decimal(tyumen_raw.get(year))
                raw_values[year] = value
                display_values[year] = format_ee_balance_cell(value, digits=rounding_digits)
        row["editable_values"] = False
        row["editable_label"] = False
        row["can_add_custom_flow"] = False
        row.pop("editable_years", None)
        row.pop("value_save_kind", None)
        row.pop("row_key", None)
    tables[excluded_slug] = {"sheet": excluded_sheet, "rows": excluded_rows}
    evaluate_power_balance_tables(tables, years, rounding_digits=rounding_digits)
    attach_balance_sheet_notes({excluded_slug: tables[excluded_slug]}, BALANCE_KIND_EE)
    for row in tables[excluded_slug]["rows"]:
        row["editable_values"] = False
        row["editable_label"] = False
        row["can_add_custom_flow"] = False
        row.pop("editable_years", None)
        row.pop("value_save_kind", None)
        row.pop("row_key", None)
    mark_power_balance_empty_rows(tables[excluded_slug]["rows"], years)


def _overlay_ural_without_tyumen_manual_generation(
    tables: dict[str, dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    payload = tables.get(URAL_WITHOUT_TYUMEN_SLUG)
    if payload is None:
        return
    sheet = payload["sheet"]
    manual_inputs = load_ee_balance_manual_generation_inputs(years, sheets=[sheet])
    row_inputs = manual_inputs.get(URAL_WITHOUT_TYUMEN_SLUG, {})
    for row in payload.get("rows") or []:
        values = row_inputs.get(str(row.get("key") or ""), {})
        if not values:
            continue
        raw_values = row.setdefault("year_values_raw", {})
        display_values = row.setdefault("year_values", {})
        for year, value in values.items():
            year_int = int(year)
            raw_values[year_int] = value
            display_values[year_int] = format_ee_balance_cell(
                value, digits=rounding_digits
            )
    evaluate_power_balance_tables(tables, years, rounding_digits=rounding_digits)
    mark_manual_plan_generation_rows(
        {URAL_WITHOUT_TYUMEN_SLUG: payload}, years
    )
    mark_power_balance_empty_rows(payload["rows"], years)


def _ural_subtab_sheets(tyumen_sheet: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"slug": "ural", "sheet_name": "ОЭС Урала (с Тюменской ЭС)"},
        {
            "slug": URAL_WITHOUT_TYUMEN_SLUG,
            "sheet_name": "ОЭС Урала (без Тюменской ЭС)",
        },
        {"slug": str(tyumen_sheet["slug"]), "sheet_name": "Тюменская ЭС"},
    ]


def build_ee_balance_table_context(
    slug: str,
    *,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    hydro_year: Any = None,
) -> dict[str, Any] | None:
    del hydro_year
    balance_slug = "2-sz-ees-vostok" if slug == "vostok" else slug
    base_sheets = get_ee_balance_sheets()
    is_european_ees = slug in {
        EUROPEAN_EES_SLUG,
        EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG,
    }
    synchronous_zone_slugs = {
        str(item.get("slug") or "")
        for item in base_sheets
        if item.get("group") == GROUP_SZ
        and item.get("slug") != EUROPEAN_EES_SLUG
    }
    is_synchronous_zones = slug == SYNCHRONOUS_ZONES_SLUG
    is_synchronous_zone = slug in synchronous_zone_slugs
    is_ees_rossii_with_tites = slug == EES_RUSSIA_WITH_TITES_SLUG
    tyumen_sheet = None
    if (
        slug == "ural"
        or slug == URAL_WITHOUT_TYUMEN_SLUG
        or str(slug).startswith("res-")
    ):
        tyumen_sheet = _ural_tyumen_energy_system(base_sheets)
        if (
            str(slug).startswith("res-")
            and tyumen_sheet
            and slug != tyumen_sheet["slug"]
        ):
            tyumen_sheet = None

    ural_subtabs = _ural_subtab_sheets(tyumen_sheet) if tyumen_sheet else []
    severo_zapad_regions = []
    severo_zapad_subtabs = []
    if (
        slug == "severo-zapad"
        or slug == SEVERO_ZAPAD_CENTER_SLUG
        or str(slug).startswith("res-")
    ):
        severo_zapad_regions = _severo_zapad_region_sheets(base_sheets)
        candidate_subtabs = (
            _severo_zapad_subtab_sheets(severo_zapad_regions)
            if severo_zapad_regions
            else []
        )
        if slug in {item["slug"] for item in candidate_subtabs}:
            severo_zapad_subtabs = candidate_subtabs

    if is_synchronous_zones:
        sheets = list(base_sheets)
        first_zone = next(item for item in sheets if item.get("slug") in synchronous_zone_slugs)
        sheet = dict(first_zone)
        sheet.update(
            slug=SYNCHRONOUS_ZONES_SLUG,
            sheet_name=SYNCHRONOUS_ZONES_NAME,
            title=f"{EE_BALANCE_TITLE_PREFIX} {SYNCHRONOUS_ZONES_NAME}",
            subtract_slugs=(),
        )
        sheets.insert(sheets.index(first_zone), sheet)
    elif is_ees_rossii_with_tites:
        sheets = list(base_sheets)
        ees_sheet = next(
            (
                item
                for item in sheets
                if item.get("slug") == "ees-rossii" or item.get("layout") == "ees_rossii"
            ),
            None,
        )
        if ees_sheet is None:
            return None
        sheet = dict(ees_sheet)
        sheet.update(
            slug=EES_RUSSIA_WITH_TITES_SLUG,
            sheet_name=EES_RUSSIA_WITH_TITES_NAME,
            title=f"{EE_BALANCE_TITLE_PREFIX} {EES_RUSSIA_WITH_TITES_NAME}",
            source_slugs=_ees_rossii_with_tites_source_slugs(sheets),
            subtract_slugs=(),
        )
        sheets.insert(sheets.index(ees_sheet), sheet)
    elif is_european_ees:
        sheets = list(base_sheets)
        sheet = dict(next(item for item in sheets if item.get("slug") == "severo-zapad"))
        sheet.update(_european_ees_navigation_sheet())
        if slug == EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG:
            sheet.update(
                slug=EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG,
                sheet_name=EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME,
                title=(
                    f"{EE_BALANCE_TITLE_PREFIX} "
                    f"{EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME}"
                ),
                source_slugs=EUROPEAN_EES_WITHOUT_SOUTH_URAL_SOURCE_SLUGS,
            )
        else:
            sheet.update(
                title=f"{EE_BALANCE_TITLE_PREFIX} Европейская часть ЕЭС",
                source_slugs=EUROPEAN_EES_SOURCE_SLUGS,
            )
        sheet.update(subtract_slugs=())
        sheet.pop("territory", None)
        sheet.pop("is_ees_member", None)
    elif ural_subtabs and slug in {item["slug"] for item in ural_subtabs}:
        sheets = list(base_sheets)
        if not any(item.get("slug") == tyumen_sheet["slug"] for item in sheets):
            sheets.append(tyumen_sheet)
        if slug == URAL_WITHOUT_TYUMEN_SLUG:
            sheet = dict(next(item for item in sheets if item.get("slug") == "ural"))
            sheet.update(
                slug=URAL_WITHOUT_TYUMEN_SLUG,
                sheet_name="ОЭС Урала (без Тюменской ЭС)",
                title=f"{EE_BALANCE_TITLE_PREFIX} ОЭС Урала (без Тюменской ЭС)",
                parent_slug="ural",
            )
        else:
            sheet = next(item for item in sheets if item.get("slug") == slug)
    elif severo_zapad_subtabs:
        sheets = list(base_sheets)
        sheets.extend(
            region
            for region in severo_zapad_regions
            if not any(item.get("slug") == region.get("slug") for item in sheets)
        )
        if slug == SEVERO_ZAPAD_CENTER_SLUG:
            sheet = dict(next(item for item in sheets if item.get("slug") == "severo-zapad"))
            sheet.update(
                slug=SEVERO_ZAPAD_CENTER_SLUG,
                sheet_name="ОЭС Северо-Запада (центр)",
                title=f"{EE_BALANCE_TITLE_PREFIX} ОЭС Северо-Запада (центр)",
                parent_slug="severo-zapad",
            )
        else:
            sheet = next(item for item in sheets if item.get("slug") == slug)
    else:
        sheets, sheet = _ee_sheets_including_slug(balance_slug)
    if sheet is None:
        return None
    page_title = (
        f"{EE_BALANCE_TITLE_PREFIX} ОЭС Востока" if slug == "vostok" else sheet["title"]
    )
    if ural_subtabs and slug == "ural":
        page_title = f"{EE_BALANCE_TITLE_PREFIX} ОЭС Урала (с Тюменской ЭС)"
    years = get_ee_balance_year_columns(start_year, end_year)
    digits = resolve_ee_balance_rounding_digits(rounding_digits)
    tables = build_ee_balance_tables(
        years,
        rounding_digits=digits,
        sheets=sheets,
    )
    european_ees_subtab_sheets = []
    if is_european_ees:
        _append_european_ees_table(tables, years, digits)
        _append_european_ees_table(
            tables,
            years,
            digits,
            slug=EUROPEAN_EES_WITHOUT_SOUTH_URAL_SLUG,
            sheet_name=EUROPEAN_EES_WITHOUT_SOUTH_URAL_NAME,
            source_slugs=EUROPEAN_EES_WITHOUT_SOUTH_URAL_SOURCE_SLUGS,
        )
        european_ees_subtab_sheets = _european_ees_subtab_sheets()
        sheet = tables.get(slug, {}).get("sheet") or sheet
    if ural_subtabs:
        _append_ural_without_tyumen_table(tables, str(tyumen_sheet["slug"]), years, digits)
        _overlay_ural_without_tyumen_manual_generation(tables, years, digits)
        if slug == URAL_WITHOUT_TYUMEN_SLUG:
            sheet = tables.get(URAL_WITHOUT_TYUMEN_SLUG, {}).get("sheet") or sheet
    if severo_zapad_subtabs:
        _append_severo_zapad_center_table(
            tables,
            [str(region["slug"]) for region in severo_zapad_regions],
            years,
            digits,
        )
        if slug == SEVERO_ZAPAD_CENTER_SLUG:
            sheet = tables.get(SEVERO_ZAPAD_CENTER_SLUG, {}).get("sheet") or sheet
    payload = tables.get(sheet["slug"])
    if payload is None:
        return None
    start = years[0] if years else None
    end = years[-1] if years else None
    station_query = power_balance_station_list_query(sheet, sheets, start, end)
    sheet_hydro_year = hydro_year_for_balance_sheet(sheet, sheets)
    show_hydro_in_title = (
        sheet_hydro_year is not None
        and sheet_has_ges_or_gaes_capacity(payload["rows"], years)
    )
    tes_forecast_url = None
    if is_tes_forecast_sheet(sheet):
        from flask import url_for

        tes_forecast_url = url_for(
            "energy_balance_bp.ee_balance_tes_forecast",
            slug=sheet["slug"],
            start_year=start,
            end_year=end,
            rounding_digits=digits,
        )
    from app.energy_balance.services.ee_balance_ves_ses_page_services import (
        _can_edit_ves_ses_energy,
    )

    page_title = format_ee_balance_page_title(
        page_title,
        hydro_year=sheet_hydro_year if show_hydro_in_title else None,
    )
    navigation_sheets = _ee_balance_navigation_sheets(sheets)
    sheet_groups = group_ee_balance_sheets(navigation_sheets)
    synchronous_zone_subtab_sheets = (
        _synchronous_zone_subtab_sheets(sheet_groups)
        if is_synchronous_zones or is_synchronous_zone
        else []
    )
    return {
        "sheet": payload["sheet"],
        "page_slug": slug,
        "sheets": sheets,
        "sheet_groups": sheet_groups,
        "tites_east_child_sheets": (
            []
            if severo_zapad_subtabs
            else tites_east_child_nav_sheets(sheets, sheet["slug"])
        ),
        "ural_subtab_sheets": ural_subtabs,
        "severo_zapad_subtabs": severo_zapad_subtabs,
        "european_ees_subtab_sheets": european_ees_subtab_sheets,
        "synchronous_zone_subtab_sheets": synchronous_zone_subtab_sheets,
        "first_row_active_slug": (
            SYNCHRONOUS_ZONES_SLUG
            if is_synchronous_zones or is_synchronous_zone
            else EUROPEAN_EES_SLUG
            if is_european_ees
            else (
                "ural"
                if ural_subtabs
                else (
                    "severo-zapad"
                    if severo_zapad_subtabs
                    else (
                        "vostok"
                        if slug == "vostok"
                        else first_row_active_slug(sheet, sheet["slug"])
                    )
                )
            )
        ),
        "page_title": page_title,
        "browser_title": format_ee_balance_browser_title(page_title),
        "years": years,
        "year_features": get_ee_balance_year_features(),
        "start_year": start,
        "end_year": end,
        "filter_year_list": get_ee_balance_filter_year_list(),
        "rounding_digits": digits,
        "station_list_url": build_power_balance_station_list_url(station_query),
        "rows": payload["rows"],
        "show_hydro_year_nav": False,
        "hydro_year": sheet_hydro_year if show_hydro_in_title else None,
        "hydro_year_buttons": [],
        "tes_forecast_url": tes_forecast_url,
        "can_edit": _can_edit_ves_ses_energy(),
    }
