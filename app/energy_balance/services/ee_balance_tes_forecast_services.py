# -*- coding: utf-8 -*-
"""Помесячный расчёт прогнозной выработки ТЭС (форма «БЭ по месяцам», Магадан).

Годовые итоги вкладок (потребление, ГЭС, ТЭС) переносятся в сводную таблицу БЭ
за тот же год. ПИВР ГЭС - прогноз выработки с карточек ГЭС Центрального энергорайона.
"""
from __future__ import annotations

import calendar
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

_logger = logging.getLogger(__name__)

from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.orm import joinedload

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.common.services.help_services import (
    format_decimal_trim_for_display,
    parse_decimal_from_display,
)
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.ee_balance_tes_monthly_value_model import (
    EeBalanceTesMonthlyValue,
)
from app.energy_balance.services.ee_balance_consumption_services import (
    CONSUMPTION_ROW_KEY,
    load_ee_balance_consumption_inputs,
)
from app.energy_balance.services.ee_balance_generation_services import (
    GENERATION_GES_KEY,
    GENERATION_TES_KEY,
    HYDRO_YEAR_LOW,
    _norm_year_feature,
    classify_ee_balance_generation_years,
)
from app.energy_balance.services.station_ee_generation_page_services import (
    load_annual_generation_by_station,
    load_monthly_generation_by_station,
)
from app.energy_balance.services.power_balance_installed_capacity_services import (
    _stable_type_key,
    _station_ids_for_capacity_territory,
    load_power_balance_station_capacity_breakdown,
)
from app.energy_balance.services.power_balance_page_services import (
    POWER_BALANCE_UNIT,
    _eu_name_matches,
    _is_tites_sibir_name,
    get_power_balance_filter_year_list,
    get_power_balance_year_columns,
    get_power_balance_year_features,
    resolve_power_balance_rounding_digits,
)
from app.extensions import db
from app.generation.prospective_places.models.prospective_place_hydro_energy_forecast_model import (
    HYDRO_MONTH_NAMES,
    HYDRO_MONTH_ORDER,
    SCENARIO_LOW_95,
)
from app.generation.prospective_places.services.hydro_energy_forecast_services import (
    hydro_forecast_owner_for_station,
    load_hydro_forecast_by_scenario,
)
from app.generation.services.station_services.station_type_flags import is_ges_station

CHIIM_SCALE = Decimal("1000")
TES_FORECAST_ENERGY_UNIT = "млн.кВт·ч"
TES_FORECAST_HOURS_UNIT = "ч."
TES_FORECAST_KIUM_UNIT = "%"
MAGADAN_TES_FORECAST_NEEDLES = ("центральный", "магадан")

ROW_HOURS = "hours"
ROW_CONSUMPTION_SHARE = "consumption_share"
ROW_CONSUMPTION = "consumption"
ROW_PRODUCTION = "production"
ROW_GES_USED = "ges_used"
ROW_PIVR_SUM = "pivr_sum"
ROW_TES_FACT_AVG = "tes_fact_avg"
ROW_TES_TOTAL = "tes_total"
TES_FACT_AVG_YEAR_COUNT = 5
ROW_DEFICIT = "deficit"
ROW_CAP_TOTAL = "capacity_total"
ROW_CAP_AES = "capacity_aes"
ROW_CAP_GES = "capacity_ges"
ROW_CAP_TES = "capacity_tes"
ROW_CHIIM_HEADER = "chiim_header"
ROW_CHIIM_TES = "chiim_tes"
ROW_KIUM_HEADER = "kium_header"
ROW_KIUM_TES = "kium_tes"

KIND_SECTION = "section"
KIND_TOTAL = "total"
KIND_VALUE = "value"
KIND_CHILD = "child"

EDITABLE_KEYS = frozenset({ROW_CONSUMPTION_SHARE, ROW_CONSUMPTION, ROW_GES_USED})
EDITABLE_PREFIXES = ("tes_station_", "tes_machine_")

_tables_ready = False

__all__ = [
    "CHIIM_SCALE",
    "GENERATION_TES_KEY",
    "HYDRO_MONTH_NAMES",
    "HYDRO_MONTH_ORDER",
    "MAGADAN_TES_FORECAST_NEEDLES",
    "ROW_TES_FACT_AVG",
    "ROW_TES_TOTAL",
    "TES_FACT_AVG_YEAR_COUNT",
    "build_tes_forecast_context",
    "compute_tes_forecast_year",
    "hours_in_month",
    "is_magadan_tes_forecast_sheet",
    "is_tes_forecast_sheet",
    "overlay_tes_forecast_generation_inputs",
    "tes_forecast_page_title",
    "tes_fact_average_sample_years",
    "tes_forecast_plan_years",
    "tes_forecast_year_tes_total",
    "tes_forecast_year_value",
    "update_tes_forecast_value",
    "year_hours_total",
]


def hours_in_month(month: int, year: int) -> Decimal:
    if month < 1 or month > 12:
        raise ValueError("Месяц должен быть от 1 до 12")
    return Decimal(calendar.monthrange(year, month)[1] * 24)


def year_hours_total(year: int) -> Decimal:
    return sum((hours_in_month(month, year) for month in HYDRO_MONTH_ORDER), Decimal("0"))


def is_magadan_tes_forecast_sheet(sheet: dict[str, Any] | None) -> bool:
    if not sheet:
        return False
    name = sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
    return _eu_name_matches(name, MAGADAN_TES_FORECAST_NEEDLES)


def is_tites_sibir_tes_forecast_sheet(sheet: dict[str, Any] | None) -> bool:
    if not sheet:
        return False
    name = sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
    return _is_tites_sibir_name(name)


def is_tes_forecast_sheet(sheet: dict[str, Any] | None) -> bool:
    return is_magadan_tes_forecast_sheet(sheet) or is_tites_sibir_tes_forecast_sheet(
        sheet
    )


def tes_forecast_page_title(sheet: dict[str, Any] | None) -> str:
    if is_tites_sibir_tes_forecast_sheet(sheet):
        return (
            "Помесячный баланс электрической энергии ТИТЭС Сибири "
            "для условий маловодного года"
        )
    return (
        "Помесячный баланс электрической энергии Центрального энергорайона "
        "Магаданской области для условий маловодного года"
    )


def _tes_forecast_ges_pivr_scope(sheet: dict[str, Any] | None) -> str:
    if is_tites_sibir_tes_forecast_sheet(sheet):
        return "ТИТЭС Сибири"
    return "Центрального энергорайона"


def tes_forecast_plan_years(
    years: list[int],
    year_features: dict[Any, Any] | None = None,
) -> list[int]:
    _fact, plan = classify_ee_balance_generation_years(years, year_features)
    return [int(year) for year in plan]


def _split_fact_and_current_years(
    year_features: dict[Any, Any] | None,
) -> tuple[list[int], int | None]:
    fact: list[int] = []
    current: int | None = None
    for raw_year, raw_name in (year_features or {}).items():
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue
        feature = _norm_year_feature(raw_name)
        if feature.startswith("текущий"):
            if current is None or year > current:
                current = year
        elif feature.startswith("факт"):
            fact.append(year)
    fact.sort()
    return fact, current


def tes_fact_average_sample_years(
    year_features: dict[Any, Any] | None,
    *,
    has_current_data: bool,
) -> list[int]:
    fact, current = _split_fact_and_current_years(year_features)
    if has_current_data and current is not None:
        return fact[-(TES_FACT_AVG_YEAR_COUNT - 1) :] + [current]
    return fact[-TES_FACT_AVG_YEAR_COUNT:]


def _generation_month_map(months: dict[Any, Any] | None) -> dict[int, Decimal | None]:
    month_map = _month_map()
    raw = months or {}
    for month in HYDRO_MONTH_ORDER:
        month_map[month] = _to_decimal(raw.get(month))
    return month_map


def _distribute_annual_by_hours(annual: Decimal | None, year: int) -> dict[int, Decimal | None]:
    result = _month_map()
    if annual is None:
        return result
    hours_year = year_hours_total(year)
    if hours_year == 0:
        return result
    for month in HYDRO_MONTH_ORDER:
        result[month] = annual * hours_in_month(month, year) / hours_year
    return result


def _month_map_has_values(values: dict[int, Decimal | None] | None) -> bool:
    if not values:
        return False
    return any(
        _to_decimal(values.get(month)) is not None for month in HYDRO_MONTH_ORDER
    )


def _average_month_maps(
    maps: list[dict[int, Decimal | None]],
) -> dict[int, Decimal | None]:
    result = _month_map()
    for month in HYDRO_MONTH_ORDER:
        result[month] = _average_present([item.get(month) for item in maps])
    return result


def resolve_tes_forecast_view_year(value: Any, years: list[int]) -> int | None:
    if not years:
        return None
    if value in (None, ""):
        return years[0]
    try:
        year = int(value)
    except (TypeError, ValueError):
        return years[0]
    return year if year in years else years[0]


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _sum_present(values: list[Decimal | None]) -> Decimal | None:
    present = [item for item in values if item is not None]
    if not present:
        return None
    return sum(present, Decimal("0"))


def _average_present(values: list[Decimal | None]) -> Decimal | None:
    present = [item for item in values if item is not None]
    if not present:
        return None
    return sum(present, Decimal("0")) / Decimal(len(present))


def _add(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None and right is None:
        return None
    return (left or Decimal("0")) + (right or Decimal("0"))


def _sub(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None and right is None:
        return None
    return (left or Decimal("0")) - (right or Decimal("0"))


def _chiim(generation: Decimal | None, capacity: Decimal | None) -> Decimal | None:
    if generation is None or capacity is None or capacity == 0:
        return None
    return generation / capacity * CHIIM_SCALE


def _kium(chiim: Decimal | None, hours: Decimal | None) -> Decimal | None:
    if chiim is None or hours is None or hours == 0:
        return None
    return chiim / hours * Decimal("100")


def _kium_map(
    chiim_values: dict[Any, Decimal | None],
    hours: dict[int, Decimal],
    hours_year: Decimal,
) -> dict[Any, Decimal | None]:
    result = _month_map()
    for month in HYDRO_MONTH_ORDER:
        result[month] = _kium(chiim_values.get(month), hours[month])
    result["year"] = _kium(chiim_values.get("year"), hours_year)
    return result


def _month_map(fill: Decimal | None = None) -> dict[int, Decimal | None]:
    return {month: fill for month in HYDRO_MONTH_ORDER}


def _constant_month_map(value: Decimal | None) -> dict[int, Decimal | None]:
    return {month: value for month in HYDRO_MONTH_ORDER}


def _with_year_total(values: dict[int, Decimal | None]) -> dict[Any, Decimal | None]:
    result: dict[Any, Decimal | None] = dict(values)
    result["year"] = _sum_present([values.get(month) for month in HYDRO_MONTH_ORDER])
    return result


def tes_station_row_key(station_id: int) -> str:
    return f"tes_station_{int(station_id)}"


def tes_fact_avg_station_row_key(station_id: int) -> str:
    return f"tes_fact_avg_station_{int(station_id)}"


def tes_fact_avg_year_row_key(station_id: int, year: int) -> str:
    return f"tes_fact_avg_station_{int(station_id)}_year_{int(year)}"


def tes_machine_row_key(machine_id: int) -> str:
    return f"tes_machine_{int(machine_id)}"


def machine_group_row_key(prefix: str, station_id: int, group_label: str) -> str:
    slug = re.sub(
        r"[^\w]+",
        "_",
        str(group_label or "").casefold().replace("ё", "е"),
        flags=re.UNICODE,
    ).strip("_")
    return f"{prefix}_group_{int(station_id)}_{slug or 'none'}"


def _machine_group_label(machine: dict[str, Any]) -> str:
    return " ".join(str(machine.get("machine_group") or "").split()).strip()


def _station_machine_groups(
    machines: list[dict[str, Any]],
) -> list[tuple[str | None, list[int]]]:
    named: dict[str, list[int]] = {}
    named_order: list[str] = []
    ungrouped: list[int] = []
    for index, machine in enumerate(machines):
        label = _machine_group_label(machine)
        if not label:
            ungrouped.append(index)
            continue
        if label not in named:
            named[label] = []
            named_order.append(label)
        named[label].append(index)
    groups: list[tuple[str | None, list[int]]] = [
        (label, named[label]) for label in named_order
    ]
    for index in ungrouped:
        groups.append((None, [index]))
    return groups


def _sum_month_maps(
    maps: list[dict[Any, Decimal | None]],
) -> dict[int, Decimal | None]:
    result = _month_map()
    for month in HYDRO_MONTH_ORDER:
        result[month] = _sum_present([item.get(month) for item in maps])
    return result


def _tes_generation_key_links(
    tes_stations: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    station_to_machines: dict[str, list[str]] = {}
    machine_to_station: dict[str, str] = {}
    for station in tes_stations:
        machines = list(station.get("machines") or [])
        if not machines:
            continue
        skey = tes_station_row_key(int(station["id"]))
        mkeys = [tes_machine_row_key(int(machine["id"])) for machine in machines]
        station_to_machines[skey] = mkeys
        for mkey in mkeys:
            machine_to_station[mkey] = skey
    return station_to_machines, machine_to_station


def ges_station_row_key(station_id: int) -> str:
    return f"ges_station_{int(station_id)}"


def cap_tes_station_row_key(station_id: int) -> str:
    return f"capacity_tes_station_{int(station_id)}"


def cap_tes_machine_row_key(machine_id: int) -> str:
    return f"capacity_tes_machine_{int(machine_id)}"


def cap_ges_station_row_key(station_id: int) -> str:
    return f"capacity_ges_station_{int(station_id)}"


def cap_ges_machine_row_key(machine_id: int) -> str:
    return f"capacity_ges_machine_{int(machine_id)}"


def cap_aes_station_row_key(station_id: int) -> str:
    return f"capacity_aes_station_{int(station_id)}"


def cap_aes_machine_row_key(machine_id: int) -> str:
    return f"capacity_aes_machine_{int(machine_id)}"


def chiim_tes_station_row_key(station_id: int) -> str:
    return f"chiim_tes_station_{int(station_id)}"


def chiim_tes_machine_row_key(machine_id: int) -> str:
    return f"chiim_tes_machine_{int(machine_id)}"


def kium_tes_station_row_key(station_id: int) -> str:
    return f"kium_tes_station_{int(station_id)}"


def kium_tes_machine_row_key(machine_id: int) -> str:
    return f"kium_tes_machine_{int(machine_id)}"


def is_tes_forecast_editable_key(row_key: str) -> bool:
    key = str(row_key or "").strip()
    if key in EDITABLE_KEYS:
        return True
    return key.startswith("tes_machine_") or key.startswith("tes_station_")


def _unit_for_key(key: str) -> str:
    if key in {ROW_CHIIM_HEADER, ROW_KIUM_HEADER}:
        return ""
    if key == ROW_HOURS:
        return TES_FORECAST_HOURS_UNIT
    if key == ROW_CONSUMPTION_SHARE:
        return ""
    if key.startswith("kium_"):
        return TES_FORECAST_KIUM_UNIT
    if key.startswith("capacity_"):
        return POWER_BALANCE_UNIT
    if key.startswith("chiim_"):
        return TES_FORECAST_HOURS_UNIT
    return TES_FORECAST_ENERGY_UNIT


def _row(
    key: str,
    label: str,
    values: dict[Any, Decimal | None],
    *,
    kind: str = KIND_VALUE,
    editable: bool = False,
    indent: int = 0,
    formula_tooltip: str | None = None,
    italic: bool = False,
    css_class: str | None = None,
    is_reference: bool = False,
    formula_months: list[int] | None = None,
) -> dict[str, Any]:
    if css_class is None:
        css_class = "table-info" if kind in {KIND_TOTAL, KIND_SECTION} else ""
    return {
        "key": key,
        "label": label,
        "kind": kind,
        "editable": editable,
        "indent": indent,
        "italic": italic,
        "formula_tooltip": formula_tooltip,
        "values": values,
        "css_class": css_class,
        "unit": _unit_for_key(key),
        "collapsible": False,
        "parent_station_key": None,
        "is_machine_row": False,
        "is_reference": is_reference,
        "formula_months": list(formula_months or []),
    }


def _section_row(key: str, label: str) -> dict[str, Any]:
    return _row(key, label, {}, kind=KIND_SECTION)


def _mark_station_collapsible(
    row: dict[str, Any],
    *,
    expand_title: str = "Показать агрегаты",
    collapse_title: str = "Скрыть агрегаты",
) -> dict[str, Any]:
    row["collapsible"] = True
    row["collapse_expand_title"] = expand_title
    row["collapse_collapse_title"] = collapse_title
    return row


def _mark_machine_child(row: dict[str, Any], parent_key: str) -> dict[str, Any]:
    row["is_machine_row"] = True
    row["parent_station_key"] = parent_key
    row["italic"] = True
    return row


def _mark_group_child(row: dict[str, Any], parent_key: str) -> dict[str, Any]:
    row["is_group_row"] = True
    row["parent_station_key"] = parent_key
    return row


def _attach_entity_ids(
    row: dict[str, Any],
    station: dict[str, Any],
    machine: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        row["station_id"] = int(station["id"])
    except (TypeError, ValueError, KeyError):
        return row
    if machine is None:
        return row
    try:
        row["machine_id"] = int(machine["id"])
    except (TypeError, ValueError, KeyError):
        return row
    return row


def _append_grouped_machine_children(
    rows: list[dict[str, Any]],
    *,
    station: dict[str, Any],
    parent_key: str,
    machines: list[dict[str, Any]],
    value_maps: list[dict[Any, Decimal | None]],
    machine_key_fn,
    group_prefix: str,
    editable: bool = False,
    wrap_year_total: bool = True,
    formula_tooltip: str | None = None,
    group_formula_tooltip: str | None = None,
) -> None:
    station_id = int(station["id"])
    group_tip = group_formula_tooltip or "Сумма агрегатов группы"
    for group_label, indices in _station_machine_groups(machines):
        child_parent = parent_key
        child_indent = 2
        if group_label:
            group_maps = [value_maps[index] for index in indices]
            if wrap_year_total:
                group_values = _with_year_total(_sum_month_maps(group_maps))
            else:
                total = _sum_present(
                    [_to_decimal(value_maps[index].get("year")) for index in indices]
                )
                group_values = {**_constant_month_map(total), "year": total}
            group_row = _row(
                machine_group_row_key(group_prefix, station_id, group_label),
                group_label,
                group_values,
                kind=KIND_CHILD,
                indent=2,
                formula_tooltip=group_tip,
            )
            _mark_group_child(group_row, parent_key)
            _mark_station_collapsible(group_row)
            rows.append(group_row)
            child_parent = group_row["key"]
            child_indent = 3
        for index in indices:
            machine = machines[index]
            values = value_maps[index]
            if wrap_year_total and "year" not in values:
                values = _with_year_total(values)
            rows.append(
                _attach_entity_ids(
                    _mark_machine_child(
                        _row(
                            machine_key_fn(int(machine["id"])),
                            str(machine.get("label") or ""),
                            values,
                            kind=KIND_CHILD,
                            editable=editable,
                            indent=child_indent,
                            formula_tooltip=formula_tooltip,
                        ),
                        child_parent,
                    ),
                    station,
                    machine,
                )
            )


def _station_listed_capacity(station: dict[str, Any]) -> Decimal | None:
    machines = list(station.get("machines") or [])
    if machines:
        return _sum_present(
            [_to_decimal(machine.get("capacity")) for machine in machines]
        )
    return _to_decimal(station.get("capacity"))


def _append_capacity_station_children(
    rows: list[dict[str, Any]],
    *,
    stations: list[dict[str, Any]],
    station_key_fn,
    machine_key_fn,
    group_prefix: str,
) -> None:
    for station in stations:
        machines = list(station.get("machines") or [])
        station_cap = _station_listed_capacity(station)
        parent_key = station_key_fn(int(station["id"]))
        station_row = _row(
            parent_key,
            str(station.get("label") or ""),
            {**_constant_month_map(station_cap), "year": station_cap},
            kind=KIND_CHILD,
            indent=1,
        )
        if machines:
            _mark_station_collapsible(station_row)
        rows.append(_attach_entity_ids(station_row, station))
        _append_grouped_machine_children(
            rows,
            station=station,
            parent_key=parent_key,
            machines=machines,
            value_maps=[
                {
                    **_constant_month_map(_to_decimal(machine.get("capacity"))),
                    "year": _to_decimal(machine.get("capacity")),
                }
                for machine in machines
            ],
            machine_key_fn=machine_key_fn,
            group_prefix=group_prefix,
            wrap_year_total=False,
        )


def compute_tes_forecast_year(
    *,
    year: int,
    stored: dict[str, dict[int, Decimal | None]] | None = None,
    annual_consumption: Decimal | None = None,
    ges_stations: list[dict[str, Any]] | None = None,
    tes_stations: list[dict[str, Any]] | None = None,
    aes_stations: list[dict[str, Any]] | None = None,
    aes_capacity: Decimal | None = None,
    ges_capacity: Decimal | None = None,
    ges_pivr_scope: str | None = None,
) -> list[dict[str, Any]]:
    """Строки одного года. Формулы как на листе «БЭ по месяцам СиПР … МВ»."""
    stored = stored or {}
    ges_stations = list(ges_stations or [])
    tes_stations = list(tes_stations or [])
    aes_stations = list(aes_stations or [])
    hours = {month: hours_in_month(month, year) for month in HYDRO_MONTH_ORDER}
    hours_year = year_hours_total(year)

    share_values = _month_map()
    consumption = _month_map()
    consumption_formula_months: list[int] = []
    stored_share = stored.get(ROW_CONSUMPTION_SHARE) or {}
    stored_cons = stored.get(ROW_CONSUMPTION) or {}
    for month in HYDRO_MONTH_ORDER:
        share_values[month] = _to_decimal(stored_share.get(month))
        if share_values[month] is not None and annual_consumption not in (None, 0):
            consumption[month] = annual_consumption * share_values[month]
            consumption_formula_months.append(month)
        else:
            consumption[month] = _to_decimal(stored_cons.get(month))

    pivr_by_ges: list[dict[int, Decimal | None]] = []
    for station in ges_stations:
        pivr = _month_map()
        raw = station.get("pivr") or {}
        for month in HYDRO_MONTH_ORDER:
            pivr[month] = _to_decimal(raw.get(month))
        pivr_by_ges.append(pivr)

    pivr_sum = _month_map()
    for month in HYDRO_MONTH_ORDER:
        pivr_sum[month] = _sum_present([item.get(month) for item in pivr_by_ges])

    stored_ges = stored.get(ROW_GES_USED) or {}
    ges_used = _month_map()
    for month in HYDRO_MONTH_ORDER:
        override = _to_decimal(stored_ges.get(month))
        ges_used[month] = override if override is not None else pivr_sum[month]

    tes_gen_by_station: list[dict[int, Decimal | None]] = []
    tes_machine_gen: list[list[dict[int, Decimal | None]]] = []
    for station in tes_stations:
        machines = list(station.get("machines") or [])
        if machines:
            per_machine: list[dict[int, Decimal | None]] = []
            station_gen = _month_map()
            stored_s = stored.get(tes_station_row_key(int(station["id"]))) or {}
            for machine in machines:
                mkey = tes_machine_row_key(int(machine["id"]))
                stored_m = stored.get(mkey) or {}
                month_map = _month_map()
                for month in HYDRO_MONTH_ORDER:
                    month_map[month] = _to_decimal(stored_m.get(month))
                per_machine.append(month_map)
            for month in HYDRO_MONTH_ORDER:
                machine_sum = _sum_present([item.get(month) for item in per_machine])
                if machine_sum is not None:
                    station_gen[month] = machine_sum
                else:
                    station_gen[month] = _to_decimal(stored_s.get(month))
            tes_machine_gen.append(per_machine)
            tes_gen_by_station.append(station_gen)
        else:
            skey = tes_station_row_key(int(station["id"]))
            stored_s = stored.get(skey) or {}
            month_map = _month_map()
            for month in HYDRO_MONTH_ORDER:
                month_map[month] = _to_decimal(stored_s.get(month))
            tes_machine_gen.append([])
            tes_gen_by_station.append(month_map)

    tes_total = _month_map()
    for month in HYDRO_MONTH_ORDER:
        tes_total[month] = _sum_present([item.get(month) for item in tes_gen_by_station])

    production = _month_map()
    deficit = _month_map()
    for month in HYDRO_MONTH_ORDER:
        production[month] = _add(ges_used[month], tes_total[month])
        deficit[month] = _sub(production[month], consumption[month])

    tes_cap_stations: list[Decimal | None] = []
    tes_cap_machines: list[list[Decimal | None]] = []
    for station in tes_stations:
        machines = list(station.get("machines") or [])
        if machines:
            caps = [_to_decimal(machine.get("capacity")) for machine in machines]
            tes_cap_machines.append(caps)
            tes_cap_stations.append(_sum_present(caps))
        else:
            tes_cap_machines.append([])
            tes_cap_stations.append(_to_decimal(station.get("capacity")))
    tes_capacity = _sum_present(tes_cap_stations)
    if ges_capacity is None:
        ges_capacity = _sum_present(
            [_station_listed_capacity(station) for station in ges_stations]
        )
    if aes_stations:
        aes_capacity = _sum_present(
            [_station_listed_capacity(station) for station in aes_stations]
        )
    cap_total = _sum_present([aes_capacity, ges_capacity, tes_capacity])

    chiim_tes = _month_map()
    for month in HYDRO_MONTH_ORDER:
        chiim_tes[month] = _chiim(tes_total[month], tes_capacity)
    chiim_tes["year"] = _chiim(_sum_present(list(tes_total.values())), tes_capacity)

    rows: list[dict[str, Any]] = [
        _row(
            ROW_HOURS,
            "Количество часов в месяц",
            {**hours, "year": hours_year},
            kind=KIND_VALUE,
            formula_tooltip="Число часов в месяце: количество дней в месяце выбранного года × 24",
        ),
        _row(
            ROW_CONSUMPTION_SHARE,
            "Доля месячного потребления",
            _with_year_total(share_values),
            editable=True,
            formula_tooltip="Доля месяца (сумма за год = 1). Если задана, потребление месяца = годовое потребление × доля",
        ),
        _row(
            ROW_CONSUMPTION,
            "Потребление электрической энергии",
            _with_year_total(consumption),
            editable=True,
            formula_months=consumption_formula_months,
            css_class="table-info",
            formula_tooltip="При наличии годового потребления листа БЭ и доли месяца: потребление = годовое потребление × доля; ячейка не редактируется. Иначе доступен ручной ввод. Итого = SUM(январь:декабрь)",
        ),
        _row(
            ROW_PRODUCTION,
            "Выработка электрической энергии",
            _with_year_total(production),
            kind=KIND_TOTAL,
            formula_tooltip="ГЭС (в объёме не выше ПИВР) + ТЭС",
        ),
        _row(
            ROW_PIVR_SUM,
            "Выработка ГЭС по ПИВР",
            _with_year_total(pivr_sum),
            kind=KIND_TOTAL,
            italic=True,
            css_class="tes-ref-row",
            is_reference=True,
            formula_tooltip=(
                "Справочно: сумма прогноза выработки электрической энергии электростанцией, млн кВтч "
                f"по ГЭС {ges_pivr_scope or 'Центрального энергорайона'} "
                "(маловодный год, обеспеченность 95%)"
            ),
        ),
    ]
    for station, pivr in zip(ges_stations, pivr_by_ges):
        rows.append(
            _attach_entity_ids(
                _row(
                    ges_station_row_key(int(station["id"])),
                    str(station.get("label") or ""),
                    _with_year_total(pivr),
                    kind=KIND_CHILD,
                    indent=1,
                    italic=True,
                    css_class="tes-ref-row",
                    formula_tooltip="Прогноз выработки электрической энергии электростанцией, млн кВтч",
                ),
                station,
            )
        )
    rows.append(
        _row(
            ROW_GES_USED,
            "ГЭС (в объеме не выше, чем предусмотрены ПИВР)",
            _with_year_total(ges_used),
            kind=KIND_TOTAL,
            editable=True,
            css_class="",
            formula_tooltip="По умолчанию равно выработке ГЭС по ПИВР. Можно снизить относительно прогноза ГЭС. Итого = SUM(январь:декабрь)",
        )
    )
    tes_fact_avg_by_station: list[dict[int, Decimal | None]] = []
    for station in tes_stations:
        raw_avg = station.get("fact_avg") or {}
        month_map = _month_map()
        for month in HYDRO_MONTH_ORDER:
            month_map[month] = _to_decimal(raw_avg.get(month))
        tes_fact_avg_by_station.append(month_map)
    tes_fact_avg_sum = _month_map()
    for month in HYDRO_MONTH_ORDER:
        tes_fact_avg_sum[month] = _sum_present(
            [item.get(month) for item in tes_fact_avg_by_station]
        )
    rows.append(
        _row(
            ROW_TES_FACT_AVG,
            "Выработка ТЭС (среднее за 5 лет)",
            _with_year_total(tes_fact_avg_sum),
            kind=KIND_TOTAL,
            italic=True,
            css_class="tes-ref-row",
            is_reference=True,
            formula_tooltip=(
                "Справочно: среднее помесячной выработки ТЭС со страницы «Выработка ЭЭ». "
                "Последние 5 фактических лет; если по станции есть данные текущего года — "
                "4 фактических и текущий"
            ),
        )
    )
    for station, fact_avg in zip(tes_stations, tes_fact_avg_by_station):
        parent_key = tes_fact_avg_station_row_key(int(station["id"]))
        year_items = list(station.get("fact_avg_years") or [])
        station_row = _row(
            parent_key,
            str(station.get("label") or ""),
            _with_year_total(fact_avg),
            kind=KIND_CHILD,
            indent=1,
            italic=True,
            css_class="tes-ref-row",
            formula_tooltip="Среднее помесячной выработки со страницы «Выработка ЭЭ»",
        )
        if year_items:
            _mark_station_collapsible(
                station_row,
                expand_title="Показать годы",
                collapse_title="Скрыть годы",
            )
        rows.append(_attach_entity_ids(station_row, station))
        for item in year_items:
            sample_year = int(item["year"])
            raw_values = item.get("values") or {}
            month_map = _month_map()
            for month in HYDRO_MONTH_ORDER:
                month_map[month] = _to_decimal(raw_values.get(month))
            year_row = _row(
                tes_fact_avg_year_row_key(int(station["id"]), sample_year),
                str(sample_year),
                _with_year_total(month_map),
                kind=KIND_CHILD,
                indent=2,
                italic=True,
                css_class="tes-ref-row",
            )
            year_row["parent_station_key"] = parent_key
            rows.append(year_row)
    rows.append(
        _row(
            ROW_TES_TOTAL,
            "ТЭС",
            _with_year_total(tes_total),
            kind=KIND_TOTAL,
            css_class="",
            formula_tooltip="Сумма выработки ТЭС (станции / агрегаты). Итого = SUM(январь:декабрь)",
        )
    )
    for station, station_gen, machine_gens in zip(
        tes_stations, tes_gen_by_station, tes_machine_gen
    ):
        machines = list(station.get("machines") or [])
        uses_machines = bool(machines)
        parent_key = tes_station_row_key(int(station["id"]))
        station_row = _row(
            parent_key,
            str(station.get("label") or ""),
            _with_year_total(station_gen),
            kind=KIND_CHILD,
            editable=True,
            indent=1,
            formula_tooltip=(
                "Если заполнены агрегаты — их сумма. Иначе значение по станции"
                if uses_machines
                else None
            ),
        )
        if uses_machines:
            _mark_station_collapsible(station_row)
        rows.append(_attach_entity_ids(station_row, station))
        _append_grouped_machine_children(
            rows,
            station=station,
            parent_key=parent_key,
            machines=machines,
            value_maps=machine_gens,
            machine_key_fn=tes_machine_row_key,
            group_prefix="tes",
            editable=True,
            wrap_year_total=True,
        )
    rows.append(
        _row(
            ROW_DEFICIT,
            "Дефицит (−)/Избыток (+)",
            _with_year_total(deficit),
            kind=KIND_TOTAL,
            formula_tooltip="Выработка − потребление",
        )
    )
    rows.append(
        _row(
            ROW_CAP_TOTAL,
            "Установленная мощность",
            {**_constant_month_map(cap_total), "year": cap_total},
            kind=KIND_TOTAL,
            formula_tooltip="АЭС + ГЭС + ТЭС",
        )
    )
    if aes_stations:
        rows.append(
            _row(
                ROW_CAP_AES,
                "АЭС",
                {**_constant_month_map(aes_capacity), "year": aes_capacity},
            )
        )
        _append_capacity_station_children(
            rows,
            stations=aes_stations,
            station_key_fn=cap_aes_station_row_key,
            machine_key_fn=cap_aes_machine_row_key,
            group_prefix="capacity_aes",
        )
    if ges_stations:
        rows.append(
            _row(
                ROW_CAP_GES,
                "ГЭС",
                {**_constant_month_map(ges_capacity), "year": ges_capacity},
            )
        )
        _append_capacity_station_children(
            rows,
            stations=ges_stations,
            station_key_fn=cap_ges_station_row_key,
            machine_key_fn=cap_ges_machine_row_key,
            group_prefix="capacity_ges",
        )
    if tes_stations:
        rows.append(
            _row(
                ROW_CAP_TES,
                "ТЭС",
                {**_constant_month_map(tes_capacity), "year": tes_capacity},
                kind=KIND_TOTAL,
                css_class="",
                formula_tooltip="Сумма станций ТЭС",
            )
        )
        _append_capacity_station_children(
            rows,
            stations=tes_stations,
            station_key_fn=cap_tes_station_row_key,
            machine_key_fn=cap_tes_machine_row_key,
            group_prefix="capacity_tes",
        )

    rows.append(_section_row(ROW_CHIIM_HEADER, "ЧЧИУМ"))
    rows.append(
        _row(
            ROW_CHIIM_TES,
            "ТЭС",
            {**chiim_tes},
            kind=KIND_TOTAL,
            css_class="",
            formula_tooltip="Выработка ТЭС / установленная мощность ТЭС × 1000",
        )
    )
    chiim_station_payloads: list[tuple[Any, ...]] = []
    for station, station_gen, station_cap, machine_gens, machine_caps in zip(
        tes_stations,
        tes_gen_by_station,
        tes_cap_stations,
        tes_machine_gen,
        tes_cap_machines,
    ):
        station_chiim = _month_map()
        for month in HYDRO_MONTH_ORDER:
            station_chiim[month] = _chiim(station_gen.get(month), station_cap)
        station_chiim["year"] = _chiim(
            _sum_present([station_gen.get(month) for month in HYDRO_MONTH_ORDER]),
            station_cap,
        )
        parent_key = chiim_tes_station_row_key(int(station["id"]))
        machines = list(station.get("machines") or [])
        station_row = _row(
            parent_key,
            str(station.get("label") or ""),
            station_chiim,
            kind=KIND_CHILD,
            indent=1,
            formula_tooltip="Выработка / установленная мощность × 1000",
        )
        if machines:
            _mark_station_collapsible(station_row)
        rows.append(_attach_entity_ids(station_row, station))
        machine_chiims: list[dict[Any, Decimal | None]] = []
        for month_map, cap in zip(machine_gens, machine_caps):
            machine_chiim = _month_map()
            for month in HYDRO_MONTH_ORDER:
                machine_chiim[month] = _chiim(month_map.get(month), cap)
            machine_chiim["year"] = _chiim(
                _sum_present([month_map.get(month) for month in HYDRO_MONTH_ORDER]),
                cap,
            )
            machine_chiims.append(machine_chiim)
        for group_label, indices in _station_machine_groups(machines):
            child_parent = parent_key
            child_indent = 2
            if group_label:
                group_gen = _sum_month_maps([machine_gens[index] for index in indices])
                group_cap = _sum_present([machine_caps[index] for index in indices])
                group_chiim = _month_map()
                for month in HYDRO_MONTH_ORDER:
                    group_chiim[month] = _chiim(group_gen.get(month), group_cap)
                group_chiim["year"] = _chiim(
                    _sum_present([group_gen.get(month) for month in HYDRO_MONTH_ORDER]),
                    group_cap,
                )
                group_row = _row(
                    machine_group_row_key("chiim_tes", int(station["id"]), group_label),
                    group_label,
                    group_chiim,
                    kind=KIND_CHILD,
                    indent=2,
                    formula_tooltip="Выработка / установленная мощность × 1000",
                )
                _mark_group_child(group_row, parent_key)
                _mark_station_collapsible(group_row)
                rows.append(group_row)
                child_parent = group_row["key"]
                child_indent = 3
            for index in indices:
                machine = machines[index]
                rows.append(
                    _attach_entity_ids(
                        _mark_machine_child(
                            _row(
                                chiim_tes_machine_row_key(int(machine["id"])),
                                str(machine.get("label") or ""),
                                machine_chiims[index],
                                kind=KIND_CHILD,
                                indent=child_indent,
                                formula_tooltip="Выработка / установленная мощность × 1000",
                            ),
                            child_parent,
                        ),
                        station,
                        machine,
                    )
                )
        chiim_station_payloads.append(
            (station, station_chiim, machines, machine_chiims, machine_gens, machine_caps)
        )

    rows.append(_section_row(ROW_KIUM_HEADER, "КИУМ"))
    rows.append(
        _row(
            ROW_KIUM_TES,
            "ТЭС",
            _kium_map(chiim_tes, hours, hours_year),
            kind=KIND_TOTAL,
            css_class="",
            formula_tooltip="ЧЧИУМ / количество часов в месяц × 100",
        )
    )
    for station, station_chiim, machines, machine_chiims, machine_gens, machine_caps in chiim_station_payloads:
        parent_key = kium_tes_station_row_key(int(station["id"]))
        station_row = _row(
            parent_key,
            str(station.get("label") or ""),
            _kium_map(station_chiim, hours, hours_year),
            kind=KIND_CHILD,
            indent=1,
            formula_tooltip="ЧЧИУМ / количество часов в месяц × 100",
        )
        if machines:
            _mark_station_collapsible(station_row)
        rows.append(_attach_entity_ids(station_row, station))
        for group_label, indices in _station_machine_groups(machines):
            child_parent = parent_key
            child_indent = 2
            if group_label:
                group_gen = _sum_month_maps([machine_gens[index] for index in indices])
                group_cap = _sum_present([machine_caps[index] for index in indices])
                group_chiim = _month_map()
                for month in HYDRO_MONTH_ORDER:
                    group_chiim[month] = _chiim(group_gen.get(month), group_cap)
                group_chiim["year"] = _chiim(
                    _sum_present([group_gen.get(month) for month in HYDRO_MONTH_ORDER]),
                    group_cap,
                )
                group_row = _row(
                    machine_group_row_key("kium_tes", int(station["id"]), group_label),
                    group_label,
                    _kium_map(group_chiim, hours, hours_year),
                    kind=KIND_CHILD,
                    indent=2,
                    formula_tooltip="ЧЧИУМ / количество часов в месяц × 100",
                )
                _mark_group_child(group_row, parent_key)
                _mark_station_collapsible(group_row)
                rows.append(group_row)
                child_parent = group_row["key"]
                child_indent = 3
            for index in indices:
                machine = machines[index]
                rows.append(
                    _attach_entity_ids(
                        _mark_machine_child(
                            _row(
                                kium_tes_machine_row_key(int(machine["id"])),
                                str(machine.get("label") or ""),
                                _kium_map(machine_chiims[index], hours, hours_year),
                                kind=KIND_CHILD,
                                indent=child_indent,
                                formula_tooltip="ЧЧИУМ / количество часов в месяц × 100",
                            ),
                            child_parent,
                        ),
                        station,
                        machine,
                    )
                )
    return rows


def format_tes_forecast_rows(
    rows: list[dict[str, Any]],
    rounding_digits: int,
) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        displays: dict[Any, str] = {}
        for key, raw in (row.get("values") or {}).items():
            if raw is None:
                displays[key] = ""
            elif row.get("key") == ROW_HOURS:
                displays[key] = format_decimal_trim_for_display(raw, digits=-1)
            else:
                displays[key] = format_decimal_trim_for_display(raw, digits=rounding_digits)
        item["displays"] = displays
        formatted.append(item)
    return formatted


def tes_forecast_year_value(rows: list[dict[str, Any]], row_key: str) -> Decimal | None:
    wanted = str(row_key or "")
    for row in rows:
        if str(row.get("key") or "") == wanted:
            return _to_decimal((row.get("values") or {}).get("year"))
    return None


def tes_forecast_year_tes_total(rows: list[dict[str, Any]]) -> Decimal | None:
    return tes_forecast_year_value(rows, ROW_TES_TOTAL)


def tes_forecast_year_has_tes_input(
    stored: dict[str, dict[int, Decimal | None]],
    tes_stations: list[dict[str, Any]],
) -> bool:
    keys: list[str] = []
    for station in tes_stations:
        keys.append(tes_station_row_key(int(station["id"])))
        keys.extend(
            tes_machine_row_key(int(machine["id"]))
            for machine in (station.get("machines") or [])
        )
    for key in keys:
        for raw in (stored.get(key) or {}).values():
            if raw is not None:
                return True
    return False


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        EeBalanceTesMonthlyValue.__table__.create(bind, checkfirst=True)
        _tables_ready = True
    except Exception:
        _logger.exception("ee balance tes forecast: table ensure failed")


def _version_id() -> int | None:
    try:
        raw = get_current_db_version_id()
    except Exception:
        _logger.exception("ee balance tes forecast: db version id lookup failed")
        return None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _value_query():
    return filter_by_db_version(
        EeBalanceTesMonthlyValue.query, EeBalanceTesMonthlyValue
    )


def load_tes_forecast_stored(
    sheet_slug: str,
    year: int,
) -> dict[str, dict[int, Decimal | None]]:
    _ensure_tables()
    stored: dict[str, dict[int, Decimal | None]] = {}
    try:
        rows = (
            _value_query()
            .filter(
                EeBalanceTesMonthlyValue.sheet_slug == str(sheet_slug),
                EeBalanceTesMonthlyValue.year_number == int(year),
            )
            .all()
        )
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return stored
    except Exception:
        _logger.exception("ee balance tes forecast: stored values query failed")
        return stored
    for row in rows:
        key = str(row.row_key or "")
        month = int(row.month_number) if row.month_number is not None else 0
        if not key or month not in HYDRO_MONTH_ORDER:
            continue
        stored.setdefault(key, {})[month] = _to_decimal(row.value_mln_kvtch)
    return stored


def load_tes_forecast_stored_years(
    sheet_slug: str,
    years: list[int],
) -> dict[int, dict[str, dict[int, Decimal | None]]]:
    result: dict[int, dict[str, dict[int, Decimal | None]]] = {}
    if not years:
        return result
    _ensure_tables()
    wanted = {int(year) for year in years}
    try:
        rows = (
            _value_query()
            .filter(
                EeBalanceTesMonthlyValue.sheet_slug == str(sheet_slug),
                EeBalanceTesMonthlyValue.year_number.in_(wanted),
            )
            .all()
        )
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return result
    except Exception:
        _logger.exception("ee balance tes forecast: stored years query failed")
        return result
    for row in rows:
        try:
            year = int(row.year_number)
        except (TypeError, ValueError):
            continue
        if year not in wanted:
            continue
        key = str(row.row_key or "")
        month = int(row.month_number) if row.month_number is not None else 0
        if not key or month not in HYDRO_MONTH_ORDER:
            continue
        result.setdefault(year, {}).setdefault(key, {})[month] = _to_decimal(
            row.value_mln_kvtch
        )
    return result


def _capacity_for_year(year_values: dict[Any, Any] | None, year: int) -> Decimal | None:
    if not year_values:
        return None
    return _to_decimal(year_values.get(int(year)))


def _station_type_group_key(station: Any) -> str:
    stype = getattr(station, "station_type", None)
    type_name = getattr(stype, "name", None) if stype is not None else None
    type_id = getattr(station, "id_station_type", None)
    try:
        type_int = int(type_id) if type_id is not None else None
    except (TypeError, ValueError):
        type_int = None
    key = _stable_type_key(str(type_name or ""), type_int)
    blob = f"{type_name or ''} {getattr(station, 'name', '')}".casefold().replace("ё", "е")
    if "дэс" in blob and key not in {"installed_ges", "installed_gaes", "installed_aes"}:
        return "installed_tes"
    return key


def _load_sheet_stations(sheet: dict[str, Any]) -> list[Any]:
    from app.generation.models.station.station_model import Station

    territory = sheet.get("territory") or {}
    try:
        station_ids = _station_ids_for_capacity_territory(territory)
    except Exception:
        _logger.exception("ee balance tes forecast: station ids load failed")
        station_ids = []
    if not station_ids:
        return []
    query = Station.query.filter(Station.id.in_(station_ids)).options(
        joinedload(Station.station_type)
    )
    query = filter_by_db_version(query, Station)
    return list(query.all())


def _machines_for_station(breakdown_station: dict[str, Any] | None, year: int) -> list[dict[str, Any]]:
    if not breakdown_station:
        return []
    machines = []
    for machine in breakdown_station.get("machines") or []:
        machine_id = machine.get("id")
        if machine_id is None:
            continue
        machines.append(
            {
                "id": int(machine_id),
                "label": str(machine.get("label") or "").strip() or f"Агрегат {machine_id}",
                "capacity": _capacity_for_year(machine.get("year_values"), year),
            }
        )
    return machines


def _load_machine_group_names(machine_ids: list[int]) -> dict[int, str]:
    if not machine_ids:
        return {}
    from app.generation.models.machine.machine_model import Machine

    try:
        query = Machine.query.filter(Machine.id.in_(machine_ids)).with_entities(
            Machine.id, Machine.machine_group
        )
        query = filter_by_db_version(query, Machine)
        names: dict[int, str] = {}
        for row in query.all():
            names[int(row.id)] = " ".join(str(row.machine_group or "").split()).strip()
        return names
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return {}


def _apply_machine_groups(stations: list[dict[str, Any]]) -> None:
    machine_ids: list[int] = []
    for station in stations:
        for machine in station.get("machines") or []:
            machine_id = machine.get("id")
            if machine_id is not None:
                machine_ids.append(int(machine_id))
    names = _load_machine_group_names(machine_ids)
    for station in stations:
        for machine in station.get("machines") or []:
            machine_id = machine.get("id")
            if machine_id is None:
                continue
            machine["machine_group"] = names.get(int(machine_id), "")


def _load_ges_pivr_months(station: Any) -> dict[int, Decimal | None]:
    result = _month_map()
    if not is_ges_station(station):
        return result
    try:
        owner = hydro_forecast_owner_for_station(station)
    except Exception:
        _logger.exception("ee balance tes forecast: hydro owner lookup failed")
        return result
    if owner is None:
        return result
    try:
        by_scenario = load_hydro_forecast_by_scenario(owner[0], owner[1])
    except Exception:
        _logger.exception("ee balance tes forecast: hydro forecast load failed")
        return result
    months = by_scenario.get(SCENARIO_LOW_95) or {}
    for month in HYDRO_MONTH_ORDER:
        result[month] = _to_decimal(months.get(month))
    return result


def _load_tes_fact_avg_by_station(
    station_ids: list[int],
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {
        int(station_id): {"avg": _month_map(), "years": []}
        for station_id in station_ids
    }
    if not station_ids:
        return result
    try:
        year_features = get_power_balance_year_features()
    except Exception:
        _logger.exception("ee balance tes forecast: year features for TES fact average failed")
        return result
    fact, current = _split_fact_and_current_years(year_features)
    years_needed = list(fact[-TES_FACT_AVG_YEAR_COUNT:])
    if current is not None and current not in years_needed:
        years_needed.append(current)
    by_station_year: dict[int, dict[int, dict[int, Decimal | None]]] = {}
    for year in years_needed:
        try:
            monthly = load_monthly_generation_by_station(station_ids, int(year))
        except Exception:
            _logger.exception(
                "ee balance tes forecast: monthly generation for TES fact average failed"
            )
            continue
        for station_id, months in monthly.items():
            month_map = _generation_month_map(months)
            if _month_map_has_values(month_map):
                by_station_year.setdefault(int(station_id), {})[int(year)] = month_map
    annual_by_station: dict[int, dict[int, Decimal | None]] = {}
    if years_needed:
        try:
            annual_by_station = load_annual_generation_by_station(
                station_ids, int(min(years_needed)), int(max(years_needed))
            )
        except Exception:
            _logger.exception(
                "ee balance tes forecast: annual generation for TES fact average failed"
            )
            annual_by_station = {}
    for station_id in station_ids:
        sid = int(station_id)
        year_ann = annual_by_station.get(sid) or {}
        for year in years_needed:
            year_int = int(year)
            existing = (by_station_year.get(sid) or {}).get(year_int)
            if _month_map_has_values(existing):
                continue
            annual = _to_decimal(year_ann.get(year_int))
            if annual is None:
                continue
            by_station_year.setdefault(sid, {})[year_int] = _distribute_annual_by_hours(
                annual, year_int
            )
    for station_id in station_ids:
        year_maps = by_station_year.get(int(station_id)) or {}
        has_current = current is not None and _month_map_has_values(
            year_maps.get(current)
        )
        sample = tes_fact_average_sample_years(
            year_features, has_current_data=has_current
        )
        sample_maps = []
        sample_years: list[dict[str, Any]] = []
        for year in sample:
            month_map = year_maps.get(year) or _month_map()
            if not _month_map_has_values(month_map):
                continue
            sample_maps.append(month_map)
            sample_years.append({"year": year, "values": month_map})
        result[int(station_id)] = {
            "avg": _average_month_maps(sample_maps),
            "years": sample_years,
        }
    return result


def _station_capacity_entity(
    station: Any,
    breakdown: dict[str, Any] | None,
    year: int,
) -> dict[str, Any]:
    station_id = int(station.id)
    machines = _machines_for_station(breakdown, year)
    capacity = _capacity_for_year((breakdown or {}).get("year_values"), year)
    return {
        "id": station_id,
        "label": str(getattr(station, "name", None) or "").strip()
        or f"Станция {station_id}",
        "capacity": (
            _sum_present([machine.get("capacity") for machine in machines])
            if machines
            else capacity
        ),
        "machines": machines,
    }


def load_tes_forecast_entities(
    sheet: dict[str, Any],
    year: int,
    *,
    hydro_year: Any = None,
) -> dict[str, Any]:
    stations = _load_sheet_stations(sheet)
    breakdown_by_id: dict[int, dict[str, Any]] = {}
    try:
        payload = load_power_balance_station_capacity_breakdown(
            [int(year)], sheets=[sheet]
        )
        for item in (payload.get(str(sheet.get("slug") or "")) or {}).get("stations") or []:
            station_id = item.get("id")
            if station_id is not None:
                breakdown_by_id[int(station_id)] = item
    except Exception:
        _logger.exception("ee balance tes forecast: capacity breakdown load failed")

    ges_stations: list[dict[str, Any]] = []
    tes_stations: list[dict[str, Any]] = []
    aes_stations: list[dict[str, Any]] = []
    sheet_hydro = hydro_year if hydro_year is not None else HYDRO_YEAR_LOW
    for station in stations:
        station_id = getattr(station, "id", None)
        if station_id is None:
            continue
        group = _station_type_group_key(station)
        breakdown = breakdown_by_id.get(int(station_id))
        entity = _station_capacity_entity(station, breakdown, year)
        if group == "installed_ges":
            entity["pivr"] = _load_ges_pivr_months(station)
            ges_stations.append(entity)
        elif group == "installed_aes":
            aes_stations.append(entity)
        elif group == "installed_tes":
            tes_stations.append(entity)
    ges_stations.sort(key=lambda item: (str(item.get("label") or "").casefold(), item["id"]))
    tes_stations.sort(key=lambda item: (str(item.get("label") or "").casefold(), item["id"]))
    aes_stations.sort(key=lambda item: (str(item.get("label") or "").casefold(), item["id"]))
    _apply_machine_groups(ges_stations)
    _apply_machine_groups(tes_stations)
    _apply_machine_groups(aes_stations)
    tes_fact_avg = _load_tes_fact_avg_by_station(
        [int(station["id"]) for station in tes_stations]
    )
    for station in tes_stations:
        payload = tes_fact_avg.get(int(station["id"])) or {}
        station["fact_avg"] = payload.get("avg") or _month_map()
        station["fact_avg_years"] = list(payload.get("years") or [])
    return {
        "ges_stations": ges_stations,
        "tes_stations": tes_stations,
        "aes_stations": aes_stations,
        "aes_capacity": _sum_present(
            [_to_decimal(item.get("capacity")) for item in aes_stations]
        ),
        "ges_capacity": _sum_present(
            [_to_decimal(item.get("capacity")) for item in ges_stations]
        ),
        "hydro_year": sheet_hydro,
    }


def load_tes_forecast_annual_consumption(sheet: dict[str, Any], year: int) -> Decimal | None:
    slug = str(sheet.get("slug") or "")
    if not slug:
        return None
    try:
        inputs = load_ee_balance_consumption_inputs([int(year)], sheets=[sheet])
    except Exception:
        _logger.exception("ee balance tes forecast: consumption load failed")
        return None
    year_map = (inputs.get(slug) or {}).get(CONSUMPTION_ROW_KEY) or {}
    return _to_decimal(year_map.get(int(year)))


def build_tes_forecast_year_payload(
    sheet: dict[str, Any],
    year: int,
    *,
    rounding_digits: int,
    stored: dict[str, dict[int, Decimal | None]] | None = None,
    entities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entities = entities or load_tes_forecast_entities(sheet, year)
    stored = stored if stored is not None else load_tes_forecast_stored(
        str(sheet.get("slug") or ""), year
    )
    rows = compute_tes_forecast_year(
        year=int(year),
        stored=stored,
        annual_consumption=load_tes_forecast_annual_consumption(sheet, year),
        ges_stations=entities.get("ges_stations"),
        tes_stations=entities.get("tes_stations"),
        aes_stations=entities.get("aes_stations"),
        aes_capacity=entities.get("aes_capacity"),
        ges_capacity=entities.get("ges_capacity"),
        ges_pivr_scope=_tes_forecast_ges_pivr_scope(sheet),
    )
    formatted = format_tes_forecast_rows(rows, rounding_digits)
    return {
        "year": int(year),
        "rows": formatted,
        "tes_total": tes_forecast_year_tes_total(rows),
        "has_tes_input": tes_forecast_year_has_tes_input(
            stored, entities.get("tes_stations") or []
        ),
        "entities": entities,
    }


def cells_payload(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = str(row.get("key") or "")
        if not key or row.get("kind") == KIND_SECTION:
            continue
        displays = row.get("displays") or {}
        result[key] = {
            str(col): str(displays.get(col) or "")
            for col in list(HYDRO_MONTH_ORDER) + ["year"]
        }
    return result


def build_tes_forecast_context(
    sheet: dict[str, Any],
    *,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    view_year: Any = None,
) -> dict[str, Any] | None:
    if not is_tes_forecast_sheet(sheet):
        return None
    years = get_power_balance_year_columns(start_year, end_year)
    year_features = get_power_balance_year_features()
    plan_years = tes_forecast_plan_years(years, year_features)
    tab_years = list(years)
    selected = resolve_tes_forecast_view_year(view_year, tab_years)
    if selected is None:
        return None
    digits = resolve_power_balance_rounding_digits(rounding_digits)
    hydro_year = HYDRO_YEAR_LOW
    payload = build_tes_forecast_year_payload(sheet, selected, rounding_digits=digits)
    rows = payload["rows"]
    if sheet.get("slug") == "oes-318" and is_tites_sibir_tes_forecast_sheet(sheet):
        rows = [
            row
            for row in rows
            if row["key"] not in {ROW_CHIIM_HEADER, ROW_KIUM_HEADER}
            and not row["key"].startswith(
                ("tes_", "capacity_tes", "chiim_tes", "kium_tes")
            )
        ]
    page_title = tes_forecast_page_title(sheet)
    return {
        "sheet": sheet,
        "page_title": page_title,
        "years": years,
        "range_years": tab_years,
        "view_year": selected,
        "year_features": year_features,
        "start_year": years[0] if years else None,
        "end_year": years[-1] if years else None,
        "filter_year_list": get_power_balance_filter_year_list(),
        "rounding_digits": digits,
        "rows": rows,
        "months": list(HYDRO_MONTH_ORDER),
        "month_names": HYDRO_MONTH_NAMES,
        "hydro_year": hydro_year,
        "is_plan_year": selected in set(plan_years),
        "update_endpoint": "energy_balance_bp.ee_balance_tes_forecast_value",
        "table_endpoint": "energy_balance_bp.ee_balance_tes_forecast",
    }


_EE_OVERLAY_YEAR_FIELDS = (
    (ROW_TES_TOTAL, GENERATION_TES_KEY),
    (ROW_GES_USED, GENERATION_GES_KEY),
    (ROW_CONSUMPTION, CONSUMPTION_ROW_KEY),
)


def _put_year_input(
    sheet_map: dict[str, dict[int, Any]],
    row_key: str,
    year: int,
    value: Decimal | None,
) -> None:
    if value is None:
        return
    year_map = dict(sheet_map.get(row_key) or {})
    year_map[int(year)] = value
    sheet_map[row_key] = year_map


def overlay_tes_forecast_generation_inputs(
    inputs: dict[str, dict[str, dict[int, Any]]] | None,
    sheets: list[dict[str, Any]] | None,
    years: list[int],
) -> dict[str, dict[str, dict[int, Any]]]:
    merged = inputs if inputs is not None else {}
    if not sheets or not years:
        return merged
    tab_years = tes_forecast_plan_years(years) or [int(year) for year in years]
    for sheet in sheets:
        if not is_tes_forecast_sheet(sheet):
            continue
        slug = str(sheet.get("slug") or "")
        if not slug:
            continue
        stored_by_year = load_tes_forecast_stored_years(slug, tab_years)
        sheet_map = merged.setdefault(slug, {})
        for year in tab_years:
            year_int = int(year)
            stored = stored_by_year.get(year_int) or {}
            try:
                entities = load_tes_forecast_entities(sheet, year_int)
            except Exception:
                _logger.exception("ee balance tes forecast: entities for overlay failed")
                continue
            annual_consumption = _to_decimal(
                (sheet_map.get(CONSUMPTION_ROW_KEY) or {}).get(year_int)
            )
            rows = compute_tes_forecast_year(
                year=year_int,
                stored=stored,
                annual_consumption=annual_consumption,
                ges_stations=entities.get("ges_stations"),
                tes_stations=entities.get("tes_stations"),
                aes_stations=entities.get("aes_stations"),
                aes_capacity=entities.get("aes_capacity"),
                ges_capacity=entities.get("ges_capacity"),
                ges_pivr_scope=_tes_forecast_ges_pivr_scope(sheet),
            )
            for source_key, target_key in _EE_OVERLAY_YEAR_FIELDS:
                if (
                    target_key == CONSUMPTION_ROW_KEY
                    and is_tites_sibir_tes_forecast_sheet(sheet)
                    and annual_consumption not in (None, 0)
                ):
                    # Неполные месячные доли не должны уменьшать годовой спрос из сводки.
                    continue
                _put_year_input(
                    sheet_map,
                    target_key,
                    year_int,
                    tes_forecast_year_value(rows, source_key),
                )
    return merged


def _write_month_value(
    *,
    slug: str,
    row_key: str,
    year: int,
    month: int,
    parsed: Decimal | None,
    version_id: int | None,
) -> Decimal | None:
    """Пишет значение месяца и возвращает предыдущее — для журнала «было → стало»."""
    existing = (
        _value_query()
        .filter(
            EeBalanceTesMonthlyValue.sheet_slug == slug,
            EeBalanceTesMonthlyValue.row_key == row_key,
            EeBalanceTesMonthlyValue.year_number == year,
            EeBalanceTesMonthlyValue.month_number == month,
        )
        .one_or_none()
    )
    previous_value = None if existing is None else existing.value_mln_kvtch
    if parsed is None:
        if existing is not None:
            db.session.delete(existing)
        return previous_value
    if existing is None:
        db.session.add(
            EeBalanceTesMonthlyValue(
                sheet_slug=slug,
                row_key=row_key,
                year_number=year,
                month_number=month,
                value_mln_kvtch=parsed,
                database_version_id=version_id,
            )
        )
        return previous_value
    existing.value_mln_kvtch = parsed
    return previous_value


def update_tes_forecast_value(
    sheet: dict[str, Any],
    year: int,
    row_key: str,
    month: int,
    raw_value: Any,
    *,
    rounding_digits: int,
    user: Any = None,
) -> dict[str, Any]:
    slug = str(sheet.get("slug") or "").strip()
    if not slug:
        raise ValueError("Не указан лист баланса")
    if not is_tes_forecast_sheet(sheet):
        raise ValueError("Помесячный расчёт недоступен для этого листа")
    try:
        year_int = int(year)
        month_int = int(month)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверный год или месяц") from exc
    if month_int not in HYDRO_MONTH_ORDER:
        raise ValueError("Неверный месяц")
    _fact, plan_years = classify_ee_balance_generation_years([year_int])
    if year_int not in set(plan_years):
        raise ValueError("Редактирование доступно только для плановых годов")
    key = str(row_key or "").strip()
    entities = load_tes_forecast_entities(sheet, year_int)
    if key == ROW_CONSUMPTION:
        stored = load_tes_forecast_stored(slug, year_int)
        share = _to_decimal(
            (stored.get(ROW_CONSUMPTION_SHARE) or {}).get(month_int)
        )
        annual = load_tes_forecast_annual_consumption(sheet, year_int)
        if share is not None and annual not in (None, 0):
            raise ValueError("Ячейка рассчитана по формуле и недоступна для редактирования")
    if not is_tes_forecast_editable_key(key):
        raise ValueError("Эта ячейка считается по формуле")
    try:
        parsed = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверное число") from exc

    _ensure_tables()
    version_id = _version_id()
    write_kw = {
        "slug": slug,
        "year": year_int,
        "month": month_int,
        "version_id": version_id,
    }
    previous_value = _write_month_value(row_key=key, parsed=parsed, **write_kw)
    if key == ROW_CONSUMPTION_SHARE and parsed is not None:
        annual = load_tes_forecast_annual_consumption(sheet, year_int)
        if annual is not None and annual != 0:
            # Старая ручная запись не должна перекрывать расчёт по новой доле.
            _write_month_value(row_key=ROW_CONSUMPTION, parsed=None, **write_kw)
    station_to_machines, machine_to_station = _tes_generation_key_links(
        entities.get("tes_stations") or []
    )
    if key in station_to_machines:
        for mkey in station_to_machines[key]:
            _write_month_value(row_key=mkey, parsed=None, **write_kw)
    elif key in machine_to_station:
        _write_month_value(row_key=machine_to_station[key], parsed=None, **write_kw)
    _commit_with_retry()
    _log_tes_forecast_change(
        user,
        str(sheet.get("sheet_name") or slug),
        key,
        year_int,
        month_int,
        previous_value,
        parsed,
    )

    payload = build_tes_forecast_year_payload(
        sheet,
        year_int,
        rounding_digits=rounding_digits,
        entities=entities,
    )
    consumption_row = next(
        (row for row in payload["rows"] if row.get("key") == ROW_CONSUMPTION),
        {},
    )
    return {
        "year": year_int,
        "row_key": key,
        "month": month_int,
        "value": parsed,
        "cells": cells_payload(payload["rows"]),
        "formula_cells": {ROW_CONSUMPTION: consumption_row.get("formula_months") or []},
        "tes_total": payload["tes_total"],
    }


def _log_tes_forecast_change(
    user: Any,
    sheet_label: str,
    row_key: str,
    year: int,
    month: int,
    old_value: Any,
    new_value: Any,
) -> None:
    from app.energy_balance.services.change_log_services import log_cell_change

    log_cell_change(
        user,
        "Изменения в балансе ЭЭ, помесячный расчёт выработки ТЭС",
        f"Строка «{row_key}», {year} г., месяц {month}",
        old_value,
        new_value,
        context=f"Лист: {sheet_label}",
    )
