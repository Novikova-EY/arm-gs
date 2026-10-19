# -*- coding: utf-8 -*-
"""Страница СЭС/ВЭС: мощность, выработка и ЧЧИУМ по станции."""
from __future__ import annotations

import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)
from decimal import Decimal
from math import isfinite
from types import SimpleNamespace
from typing import Any, Callable

from flask_login import current_user
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, selectinload

from app.energy_balance.services.access_services import can_edit_energy_balance

from app.common.services.database_version_filter import (
    filter_by_db_version,
    filter_by_explicit_db_version,
    get_current_db_version_id,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
)
from app.common.services.get_services.stations.station_type_get_services import (
    get_station_type_list_full,
)
from app.common.services.help_services import (
    format_decimal_for_display,
    format_decimal_trim_for_display,
)
from app.energy_balance.models.station_energy_generation_model import (
    STATION_ENERGY_GENERATION_PERIOD_YEAR,
    StationEnergyGeneration,
)
from app.energy_balance.services.ee_balance_hydro_own_needs_services import (
    load_hydro_own_needs_coefficients,
)
from app.energy_balance.services.ee_balance_page_services import (
    CHIIM_HOURS_SCALE,
    CHIIM_ROUNDING_DIGITS,
    get_ee_balance_filter_year_list,
    get_ee_balance_year_columns,
    get_ee_balance_year_features,
    resolve_ee_balance_rounding_digits,
)

VES_SES_HISTORY_YEARS = 7
VES_SES_PLAN_YEARS = 6
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.generation.models.station.station_gaes_charge_consumption_model import (
    StationGaesChargeConsumption,
)
from app.generation.models.station.station_owner_energy_generation_model import (
    StationOwnerEnergyGeneration,
)
from app.generation.services.station_services.groupped_services import build_hierarchy_structure
from app.generation.services.station_services.station_power_aggregation import (
    machine_not_archived_clause,
)
from app.generation.services.station_services.station_type_flags import (
    is_aes_station,
    is_gaes_station,
    is_ges_station,
    is_snee_station,
    is_ves_or_ses_station,
)
from app.generation.services.station_services.ves_ses_plan_generation_services import (
    classify_ves_ses_generation_years,
    compute_ves_ses_plan_generation,
    load_station_commission_years,
    load_station_exploitation_dates,
    seven_year_sample_window,
    ves_ses_type_key,
)
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict

METRIC_CAPACITY = "capacity"
METRIC_ENERGY = "energy"
METRIC_CHIIM = "chiim"

DATA_LABEL_CAPACITY = "Установленная мощность агрегатов, МВт"
DATA_LABEL_CAPACITY_VES = "Установленная мощность агрегатов, МВт"
DATA_LABEL_CAPACITY_SES = "Установленная мощность агрегатов, МВт"
DATA_LABEL_ENERGY = "Выработка электроэнергии, млн.кВт·ч"
DATA_LABEL_GAES_CHARGE = "Потребление электрической энергии ГАЭС на заряд, млн кВтч"
DATA_LABEL_CHIIM = "ЧЧИУМ, ч"
VES_SES_RUSSIA_TOTAL_NAME = "ВЭС и СЭС ЕЭС России"
AES_RUSSIA_TOTAL_NAME = "АЭС России"
GES_RUSSIA_TOTAL_NAME = "ГЭС России"
GAES_RUSSIA_TOTAL_NAME = "ГАЭС России"
SNEE_RUSSIA_TOTAL_NAME = "СНЭЭ России"
CHIIM_FORMULA_TOOLTIP = (
    "ЧЧИУМ = Выработка электрической энергии (млн.кВт·ч) × 1000 "
    "/ Установленная мощность (МВт)"
)


def ves_ses_station_types() -> list[Any]:
    return [
        station_type
        for station_type in (get_station_type_list_full() or [])
        if is_ves_or_ses_station(SimpleNamespace(station_type=station_type))
    ]


def parse_ves_ses_station_type_filter(raw_values: Any) -> list[int]:
    allowed = set(ves_ses_station_type_ids())
    selected: list[int] = []
    if raw_values is None:
        return selected
    if isinstance(raw_values, (str, int)):
        raw_values = [raw_values]
    for item in raw_values:
        try:
            type_id = int(item)
        except (TypeError, ValueError):
            continue
        if type_id in allowed and type_id not in selected:
            selected.append(type_id)
    return selected


def ves_ses_station_type_ids() -> list[int]:
    ids: list[int] = []
    for station_type in ves_ses_station_types():
        type_id = getattr(station_type, "id", None)
        if type_id is not None:
            ids.append(int(type_id))
    return ids


def station_type_ids_for(predicate: Callable[[Any], bool]) -> list[int]:
    return [
        int(station_type.id)
        for station_type in (get_station_type_list_full() or [])
        if getattr(station_type, "id", None) is not None
        and predicate(SimpleNamespace(station_type=station_type))
    ]


def aes_station_type_ids() -> list[int]:
    return station_type_ids_for(is_aes_station)


def ges_station_type_ids() -> list[int]:
    return station_type_ids_for(is_ges_station)


def gaes_station_type_ids() -> list[int]:
    return station_type_ids_for(is_gaes_station)


def snee_station_type_ids() -> list[int]:
    return station_type_ids_for(is_snee_station)


def _station_type_key(name: Any) -> str:
    return ves_ses_type_key(name)


# Внутри района: сначала ВЭС, затем СЭС; внутри типа — по алфавиту.
_VES_SES_TYPE_SORT_RANK = {"ves": 0, "ses": 1}


def _ves_ses_station_row_sort_key(row: dict[str, Any]) -> tuple:
    type_key = str(row.get("type_key") or "")
    return (
        _VES_SES_TYPE_SORT_RANK.get(type_key, 2),
        str(row.get("name") or "").casefold(),
        int(row.get("id") or 0),
    )


def _can_edit_ves_ses_energy() -> bool:
    return can_edit_energy_balance(current_user)


def _empty_year_map(years: list[int]) -> dict[int, Decimal | None]:
    return {int(year): None for year in years}


def _add_year_maps(target: dict[int, Decimal | None], source: dict[int, Any] | None) -> None:
    for year, raw in (source or {}).items():
        if raw is None:
            continue
        value = raw if isinstance(raw, Decimal) else Decimal(str(raw))
        current = target.get(int(year))
        target[int(year)] = value if current is None else current + value


def _add_min_value(current: Decimal | None, incoming: Decimal | None) -> Decimal | None:
    if incoming is None:
        return current
    if current is None:
        return incoming
    return current + incoming


def _load_gaes_charge_maps(
    station_ids: list[int], start_year: int, end_year: int, version_id: int | None
) -> dict[int, dict[int, Any]]:
    if not station_ids:
        return {}
    query = StationGaesChargeConsumption.query.filter(
        StationGaesChargeConsumption.id_station.in_(station_ids),
        StationGaesChargeConsumption.year_number >= start_year,
        StationGaesChargeConsumption.year_number <= end_year,
    )
    query = filter_by_explicit_db_version(query, StationGaesChargeConsumption, version_id)
    result: dict[int, dict[int, Any]] = defaultdict(dict)
    for row in query.all():
        result[int(row.id_station)][int(row.year_number)] = row.charge_consumption
    return result


def _load_energy_maps(
    station_ids: list[int],
    start_year: int,
    end_year: int,
    version_id: int | None,
    model,
    value_attr: str,
) -> dict[int, dict[int, Any]]:
    if not station_ids:
        return {}
    query = model.query.filter(
        model.id_station.in_(station_ids),
        model.year_number >= start_year,
        model.year_number <= end_year,
    )
    if model is StationEnergyGeneration:
        query = query.filter(model.month_number == STATION_ENERGY_GENERATION_PERIOD_YEAR)
    from app.common.services.database_version_filter import filter_by_explicit_db_version

    query = filter_by_explicit_db_version(query, model, version_id)
    result: dict[int, dict[int, Any]] = defaultdict(dict)
    for row in query.all():
        result[int(row.id_station)][int(row.year_number)] = getattr(row, value_attr)
    return result


def _format_cell(value: Any, digits: int) -> str:
    if value is None:
        return ""
    cleaned = _as_metric_decimal(value)
    if cleaned is None:
        return ""
    text = format_decimal_for_display(cleaned, digits=digits)
    if text in {"", "—"}:
        return ""
    compact = (
        str(text)
        .replace("\xa0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace("−", "-")
        .replace(",", ".")
    )
    try:
        if Decimal(compact) == 0:
            return ""
    except Exception:
        _logger.exception("ee balance ves/ses: zero display parse failed")
        return text
    return text


def _capacity_data_label(type_key: str) -> str:
    if type_key == "ves":
        return DATA_LABEL_CAPACITY_VES
    if type_key == "ses":
        return DATA_LABEL_CAPACITY_SES
    return DATA_LABEL_CAPACITY


def _as_metric_decimal(value: Any) -> Decimal | None:
    """Приведение к Decimal; float очищается от двоичного хвоста (9,843585999999998 → 9,843586)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not isfinite(value):
            return None
        return Decimal(format(value, ".12f")).normalize()
    try:
        text = str(value).strip().replace(",", ".")
        if not text or text in {"—", "-", "–"}:
            return None
        return Decimal(text)
    except Exception:
        _logger.exception("ee balance ves/ses: metric decimal parse failed")
        return None


def _chiim_hours(energy: Any, capacity: Any) -> Decimal | None:
    energy_value = _as_metric_decimal(energy)
    capacity_value = _as_metric_decimal(capacity)
    if energy_value is None or capacity_value is None:
        return None
    if capacity_value == 0:
        return None
    return (energy_value * Decimal(CHIIM_HOURS_SCALE)) / capacity_value


def _raw_title(value: Any) -> str:
    """Полное значение из БД/расчёта для title ячейки (без округления UI)."""
    metric = _as_metric_decimal(value)
    if metric is None:
        return ""
    text = format_decimal_trim_for_display(metric, digits=0)
    return "" if text in {"", "—"} else text


def _raw_title_map(value_map: dict[int, Any] | None, years: list[int]) -> dict[int, str]:
    value_map = value_map or {}
    return {year: _raw_title(value_map.get(year)) for year in years}


def _chiim_display_map(
    energy_map: dict[int, Any] | None,
    capacity_map: dict[int, Any] | None,
    years: list[int],
) -> dict[int, str]:
    """ЧЧИУМ по сырым выработке и мощности из БД (не по округлённому отображению)."""
    energy_map = energy_map or {}
    capacity_map = capacity_map or {}
    return {
        year: _format_cell(
            _chiim_hours(energy_map.get(year), capacity_map.get(year)),
            CHIIM_ROUNDING_DIGITS,
        )
        for year in years
    }


def _chiim_raw_title_map(
    energy_map: dict[int, Any] | None,
    capacity_map: dict[int, Any] | None,
    years: list[int],
) -> dict[int, str]:
    energy_map = energy_map or {}
    capacity_map = capacity_map or {}
    return {
        year: _raw_title(_chiim_hours(energy_map.get(year), capacity_map.get(year)))
        for year in years
    }


def _load_stations_p_ust(
    station_ids: list[int],
    years: list[int],
    version_id: int | None,
) -> dict[int, dict[int, Decimal]]:
    """Сумма Руст по станциям: версия MachinePower или NULL, как в сводке станций."""
    station_id_list = [int(sid) for sid in station_ids if sid is not None]
    year_list = sorted({int(year) for year in years})
    if not station_id_list or not year_list:
        return {}

    query = (
        db.session.query(
            Machine.id_station,
            MachinePower.year_number,
            func.coalesce(func.sum(MachinePower.p_ust), 0).label("p_ust"),
        )
        .join(Machine, MachinePower.id_machine == Machine.id)
        .filter(Machine.id_station.in_(station_id_list))
        .filter(machine_not_archived_clause())
        .filter(MachinePower.year_number.in_(year_list))
        .group_by(Machine.id_station, MachinePower.year_number)
    )
    query = filter_by_explicit_db_version(query, Machine, version_id)
    if version_id is None:
        query = query.filter(MachinePower.database_version_id.is_(None))
    else:
        query = query.filter(
            or_(
                MachinePower.database_version_id == version_id,
                MachinePower.database_version_id.is_(None),
            )
        )

    result: dict[int, dict[int, Decimal]] = defaultdict(dict)
    for row in query.all():
        result[int(row.id_station)][int(row.year_number)] = Decimal(str(row.p_ust or 0))
    return dict(result)


def _owner_energy_json(owner_full: dict[int, Any], years: list[int]) -> dict[str, str]:
    year_set = {int(year) for year in years}
    out: dict[str, str] = {}
    for year, value in (owner_full or {}).items():
        if value is None or int(year) not in year_set:
            continue
        out[str(int(year))] = str(value)
    return out


def _agg_key(kind: str, extra: dict[str, Any]) -> str:
    return "|".join(
        [
            str(kind or ""),
            str(extra.get("type_key") or ""),
            str(extra.get("est_id") or ""),
            str(extra.get("ues_id") or ""),
            str(extra.get("res_id") or ""),
            str(extra.get("rd_id") or ""),
        ]
    )


def _aes_own_needs_percent(capacity: Any, energy: Any) -> Decimal | None:
    capacity_value = _as_metric_decimal(capacity)
    energy_value = _as_metric_decimal(energy)
    if capacity_value is None or energy_value in (None, Decimal(0)):
        return None
    return capacity_value / energy_value * Decimal(100)


def _aes_delivery_energy(capacity: Any, energy: Any) -> Decimal | None:
    own_needs = _aes_own_needs_percent(capacity, energy)
    energy_value = _as_metric_decimal(energy)
    if own_needs is None or energy_value in (None, Decimal(0)):
        return None
    return energy_value - (own_needs / energy_value * Decimal(100))


def _hydro_metric_maps(
    coefficient: Any, energy_map: dict[int, Any], years: list[int], digits: int
) -> dict[str, Any]:
    coefficient_value = _as_metric_decimal(coefficient)
    energy_values = {
        year: _as_metric_decimal(energy_map.get(year)) for year in years
    }
    own_needs = {
        year: coefficient_value * energy_values[year]
        if coefficient_value is not None and energy_values[year] is not None
        else None
        for year in years
    }
    delivery = {
        year: energy_values[year] - own_needs[year]
        if energy_values[year] is not None and own_needs[year] is not None
        else None
        for year in years
    }
    return {
        "own_needs": own_needs,
        "delivery": delivery,
        "own_needs_display": {year: _format_cell(own_needs[year], digits) for year in years},
        "own_needs_raw": _raw_title_map(own_needs, years),
        "delivery_display": {year: _format_cell(delivery[year], digits) for year in years},
        "delivery_raw": _raw_title_map(delivery, years),
        "own_needs_coefficient": coefficient_value,
        "own_needs_coefficient_display": (
            format_decimal_trim_for_display(coefficient_value, digits=0)
            if coefficient_value is not None
            else ""
        ),
        "own_needs_coefficient_raw": _raw_title(coefficient_value),
        "coefficient_metrics_enabled": True,
    }


def _aes_metric_maps(
    capacity_map: dict[int, Any], energy_map: dict[int, Any], years: list[int], digits: int
) -> dict[str, dict[int, str]]:
    own_needs = {
        year: _aes_own_needs_percent(capacity_map.get(year), energy_map.get(year))
        for year in years
    }
    delivery = {
        year: _aes_delivery_energy(capacity_map.get(year), energy_map.get(year))
        for year in years
    }
    return {
        "own_needs_display": {year: _format_cell(own_needs[year], digits) for year in years},
        "own_needs_raw": _raw_title_map(own_needs, years),
        "delivery_display": {year: _format_cell(delivery[year], digits) for year in years},
        "delivery_raw": _raw_title_map(delivery, years),
    }


def _station_payload(
    station: Station,
    years: list[int],
    energy_full: dict[int, Any],
    owner_full: dict[int, Any],
    capacity_map: dict[int, Decimal | None],
    min_sample: Decimal | None,
    plan_calc: dict[int, Decimal],
    plan_rules: dict[int, str],
    plan_years: list[int],
    digits: int,
    *,
    commission_year: int | None,
    current_year: int | None,
    exploitation_date_expected: str | None = None,
) -> dict[str, Any]:
    type_name = ""
    if getattr(station, "station_type", None) is not None:
        type_name = str(station.station_type.name or "").strip()
    type_key = _station_type_key(type_name)
    energy_display: dict[int, Any] = {}
    energy_stored: dict[int, bool] = {}
    energy_is_calc: dict[int, bool] = {}
    energy_plan_rule: dict[int, str] = {}
    owner_display: dict[int, Any] = {}
    for year in years:
        stored = energy_full.get(year)
        calc = plan_calc.get(year)
        energy_stored[year] = stored is not None
        energy_display[year] = stored if stored is not None else calc
        energy_is_calc[year] = calc is not None and (
            stored is None or stored == calc
        )
        if energy_is_calc[year]:
            energy_plan_rule[year] = plan_rules.get(year) or ""
        owner_display[year] = owner_full.get(year)
    return {
        "id": station.id,
        "name": station.name,
        "type_name": type_name or "—",
        "type_key": type_key,
        "capacity": capacity_map,
        "capacity_display": {year: _format_cell(capacity_map.get(year), digits) for year in years},
        "capacity_raw": _raw_title_map(capacity_map, years),
        "capacity_label": _capacity_data_label(type_key),
        "energy_label": DATA_LABEL_ENERGY,
        "chiim_label": DATA_LABEL_CHIIM,
        "energy": energy_display,
        "energy_stored": energy_stored,
        "energy_is_calc": energy_is_calc,
        "energy_plan_rule": energy_plan_rule,
        "energy_display": {year: _format_cell(energy_display.get(year), digits) for year in years},
        "energy_raw": _raw_title_map(energy_display, years),
        "chiim_display": _chiim_display_map(energy_display, capacity_map, years),
        "chiim_raw": _chiim_raw_title_map(energy_display, capacity_map, years),
        **_aes_metric_maps(capacity_map, energy_display, years, digits),
        "owner": owner_display,
        "owner_display": {year: _format_cell(owner_display.get(year), digits) for year in years},
        "owner_raw": _raw_title_map(owner_display, years),
        "owner_energy": _owner_energy_json(owner_full, years),
        "min_value": min_sample,
        "min_display": _format_cell(min_sample, digits),
        "min_raw": _raw_title(min_sample),
        "exploitation_date_expected": exploitation_date_expected or "",
        "plan_calc": plan_calc,
        "plan_years": plan_years,
        "commission_year": commission_year,
        "sample_energy": _sample_energy_json(energy_full, current_year),
    }


def _sample_energy_json(energy_full: dict[int, Any], current_year: int | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if current_year is None:
        return out
    window_start, window_end = seven_year_sample_window(current_year)
    for year in range(window_start, window_end + 1):
        value = energy_full.get(year)
        if value is None:
            continue
        out[str(int(year))] = str(value)
    return out


def _blank_total(years: list[int]) -> dict[str, Any]:
    return {
        "capacity": _empty_year_map(years),
        "energy": _empty_year_map(years),
        "owner": _empty_year_map(years),
        "own_needs": _empty_year_map(years),
        "delivery": _empty_year_map(years),
        "gaes_charge": _empty_year_map(years),
        "gaes_charge_enabled": False,
        "coefficient_metrics_enabled": False,
        "min_value": None,
    }


def _accumulate_station(total: dict[str, Any], payload: dict[str, Any]) -> None:
    _add_year_maps(total["capacity"], payload.get("capacity"))
    _add_year_maps(total["energy"], payload.get("energy"))
    _add_year_maps(total["owner"], payload.get("owner"))
    if payload.get("gaes_charge_enabled"):
        total["gaes_charge_enabled"] = True
        _add_year_maps(total["gaes_charge"], payload.get("gaes_charge"))
    if payload.get("coefficient_metrics_enabled"):
        total["coefficient_metrics_enabled"] = True
        _add_year_maps(total["own_needs"], payload.get("own_needs"))
        _add_year_maps(total["delivery"], payload.get("delivery"))
    total["min_value"] = _add_min_value(total["min_value"], payload.get("min_value"))


def _finalize_total(
    total: dict[str, Any],
    years: list[int],
    digits: int,
    label: str,
    kind: str,
    *,
    live_locked: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    type_key = extra.pop("type_key", "") or ""
    if kind == "type_total":
        type_name = "ВЭС" if type_key == "ves" else ("СЭС" if type_key == "ses" else "")
        capacity_label = _capacity_data_label(type_key)
    else:
        type_name = extra.pop("type_name", "") or ""
        capacity_label = DATA_LABEL_CAPACITY
    extra.pop("type_name", None)
    if total.get("coefficient_metrics_enabled"):
        metric_maps = {
            "own_needs_display": {
                year: _format_cell(total["own_needs"].get(year), digits)
                for year in years
            },
            "own_needs_raw": _raw_title_map(total["own_needs"], years),
            "delivery_display": {
                year: _format_cell(total["delivery"].get(year), digits)
                for year in years
            },
            "delivery_raw": _raw_title_map(total["delivery"], years),
            "coefficient_metrics_enabled": True,
        }
    else:
        metric_maps = _aes_metric_maps(total["capacity"], total["energy"], years, digits)
    row = {
        "kind": kind,
        "label": label,
        "type_name": type_name,
        "type_key": type_key,
        "agg_key": _agg_key(kind, {**extra, "type_key": type_key}),
        "capacity_label": capacity_label,
        "energy_label": DATA_LABEL_ENERGY,
        "gaes_charge_label": DATA_LABEL_GAES_CHARGE,
        "gaes_charge_display": {
            year: _format_cell((total.get("gaes_charge") or {}).get(year), digits)
            for year in years
        },
        "gaes_charge_raw": _raw_title_map(total.get("gaes_charge") or {}, years),
        "gaes_charge_enabled": bool(total.get("gaes_charge_enabled")),
        "chiim_label": DATA_LABEL_CHIIM,
        "capacity_display": {year: _format_cell(total["capacity"].get(year), digits) for year in years},
        "capacity_raw": _raw_title_map(total["capacity"], years),
        "energy_display": {year: _format_cell(total["energy"].get(year), digits) for year in years},
        "energy_raw": _raw_title_map(total["energy"], years),
        "chiim_display": _chiim_display_map(total["energy"], total["capacity"], years),
        "chiim_raw": _chiim_raw_title_map(total["energy"], total["capacity"], years),
        **metric_maps,
        "owner_display": {year: _format_cell(total["owner"].get(year), digits) for year in years},
        "owner_raw": _raw_title_map(total["owner"], years),
        "min_display": _format_cell(total["min_value"], digits),
        "min_raw": _raw_title(total["min_value"]),
        "live_locked": bool(live_locked),
    }
    row.update(extra)
    return row


def _is_unspecified(name: Any) -> bool:
    return str(name or "").strip().casefold() in {"", "не указано", "не указан", "не указана"}


def _is_ees_russia_name(name: Any) -> bool:
    text = str(name or "").strip().casefold().replace("ё", "е")
    return text == "еэс россии" or text.startswith("еэс россии")


def _total_has_data(total: dict[str, Any]) -> bool:
    if total.get("min_value") is not None:
        return True
    for key in ("capacity", "energy", "owner"):
        if any(value is not None for value in (total.get(key) or {}).values()):
            return True
    return False


VES_SES_DEFAULT_PAGE_SIZE = 2
VES_SES_MAX_PAGE_SIZE = 8
VES_SES_ALL_PAGE_SIZE = 0
VES_SES_PAGE_SIZE_CHOICES = (1, 2, 3, 4, 5, 6, 7, 8, 0)
VES_SES_ALL_LABEL = "Все ОЭС"

# Обратная совместимость со старыми именами в шаблоне/контексте.
VES_SES_DEFAULT_PER_PAGE = VES_SES_DEFAULT_PAGE_SIZE
VES_SES_PER_PAGE_CHOICES = VES_SES_PAGE_SIZE_CHOICES


def resolve_ves_ses_pagination(
    page: Any = None,
    per_page: Any = None,
    *,
    total_sections: int = 0,
    section_titles: list[str] | None = None,
    **_unused: Any,
) -> dict[str, Any]:
    """Пагинация по секциям ОЭС (как на /power_demand/summary/oes/).

    per_page / page_size: число ОЭС на странице; 0 или all — все секции.
    """
    total = max(0, int(total_sections or 0))
    titles = list(section_titles or [])
    raw = per_page if per_page not in (None, "") else VES_SES_DEFAULT_PAGE_SIZE
    show_all = False
    page_size_value: int
    if isinstance(raw, str) and raw.strip().lower() == "all":
        show_all = True
        page_size_value = VES_SES_ALL_PAGE_SIZE
    else:
        try:
            page_size_value = int(raw)
        except (TypeError, ValueError):
            page_size_value = VES_SES_DEFAULT_PAGE_SIZE
        if page_size_value < 0:
            page_size_value = VES_SES_DEFAULT_PAGE_SIZE
        if page_size_value > VES_SES_MAX_PAGE_SIZE:
            page_size_value = VES_SES_MAX_PAGE_SIZE
        if page_size_value == VES_SES_ALL_PAGE_SIZE:
            show_all = True

    if show_all or total == 0:
        return {
            "enabled": False,
            "page": 1,
            "per_page": VES_SES_ALL_PAGE_SIZE if show_all else page_size_value,
            "page_size": VES_SES_ALL_PAGE_SIZE if show_all else page_size_value,
            "per_page_int": total or 1,
            "total_stations": 0,
            "total_sections": total,
            "total_pages": 1,
            "show_all": True,
            "start": 0,
            "end": total,
            "has_prev": False,
            "has_next": False,
            "section_titles": titles,
            "all_label": VES_SES_ALL_LABEL,
        }

    total_pages = max(1, (total + page_size_value - 1) // page_size_value)
    try:
        current_page = int(page or 1)
    except (TypeError, ValueError):
        current_page = 1
    current_page = min(max(current_page, 1), total_pages)
    start = (current_page - 1) * page_size_value
    end = min(start + page_size_value, total)
    page_titles = titles[start:end]
    return {
        "enabled": total_pages > 1,
        "page": current_page,
        "per_page": page_size_value,
        "page_size": page_size_value,
        "per_page_int": page_size_value,
        "total_stations": 0,
        "total_sections": total,
        "total_pages": total_pages,
        "show_all": False,
        "start": start,
        "end": end,
        "has_prev": current_page > 1,
        "has_next": current_page < total_pages,
        "section_titles": page_titles,
        "all_label": VES_SES_ALL_LABEL,
    }


def _iter_ves_ses_ues_sections(
    grouped: dict[Any, Any],
    *,
    est_order: list[Any],
    ues_order: list[Any],
    ues_names: dict[Any, Any],
    rd_names: dict[Any, Any],
) -> list[dict[str, Any]]:
    """Упорядоченные секции ОЭС (единица пагинации, как на summary/oes)."""

    def _iter_est_ids():
        seen = set()
        for est_id in est_order:
            if est_id in grouped:
                seen.add(est_id)
                yield est_id
        for est_id in grouped:
            if est_id not in seen:
                yield est_id

    def _iter_ues_ids(est_group):
        seen = set()
        for ues_id in ues_order:
            if ues_id in est_group:
                seen.add(ues_id)
                yield ues_id
        for ues_id in est_group:
            if ues_id not in seen:
                yield ues_id

    sections: list[dict[str, Any]] = []
    for est_id in _iter_est_ids():
        est_group = grouped.get(est_id) or {}
        for ues_id in _iter_ues_ids(est_group):
            ues_group = est_group.get(ues_id) or {}
            has_stations = False
            for _res_id, res_group in ues_group.items():
                for rd_id, rd_group in res_group.items():
                    if _is_unspecified(rd_names.get(rd_id) or ""):
                        continue
                    for _eu_id, eu_stations in rd_group.items():
                        if eu_stations:
                            has_stations = True
                            break
                    if has_stations:
                        break
                if has_stations:
                    break
            if not has_stations:
                continue
            sections.append(
                {
                    "est_id": est_id,
                    "ues_id": ues_id,
                    "title": str(ues_names.get(ues_id) or "ОЭС").strip() or "ОЭС",
                }
            )
    return sections


def _light_station_metrics(
    years: list[int],
    energy_full: dict[int, Any],
    owner_full: dict[int, Any],
    capacity_map: dict[int, Decimal | None],
    min_sample: Decimal | None,
    plan_calc: dict[int, Decimal],
    type_key: str,
    gaes_charge_map: dict[int, Any] | None = None,
) -> dict[str, Any]:
    energy_display: dict[int, Any] = {}
    for year in years:
        stored = energy_full.get(year)
        calc = plan_calc.get(year)
        energy_display[year] = stored if stored is not None else calc
    return {
        "capacity": capacity_map,
        "energy": energy_display,
        "owner": {int(year): owner_full.get(year) for year in years},
        "gaes_charge": {
            int(year): (gaes_charge_map or {}).get(int(year)) for year in years
        },
        "gaes_charge_enabled": gaes_charge_map is not None,
        "min_value": min_sample,
        "type_key": type_key,
    }


def build_ves_ses_page_rows(
    years: list[int],
    *,
    digits: int,
    year_features: dict[int, str],
    station_type_ids: list[int] | None = None,
    page: Any = None,
    per_page: Any = None,
    list_filters: dict[str, Any] | None = None,
    calculate_plan: bool = True,
    russia_total_name: str = VES_SES_RUSSIA_TOTAL_NAME,
    coefficient_type_key: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    empty_pagination = resolve_ves_ses_pagination(page, per_page, total_sections=0)
    type_ids = (
        [int(type_id) for type_id in station_type_ids]
        if station_type_ids is not None
        else ves_ses_station_type_ids()
    )
    if not type_ids or not years:
        return [], empty_pagination

    version_id = get_current_db_version_id()
    query = (
        Station.query.options(
            joinedload(Station.station_type),
            joinedload(Station.energy_unit),
            joinedload(Station.regional_energy_system_obj)
            .joinedload(RegionalEnergySystem.union_energy_system)
            .joinedload(UnionEnergySystem.energy_system_type),
            selectinload(Station.regional_district)
            .selectinload(RegionalDistrict.regional_energy_systems)
            .joinedload(RegionalEnergySystem.union_energy_system)
            .joinedload(UnionEnergySystem.energy_system_type),
        )
        .filter(Station.id_station_type.in_(type_ids))
    )
    query = filter_by_db_version(query, Station)

    filters = list_filters or {}
    if _has_ves_ses_list_filters(filters):
        try:
            from app.generation.services.station_services.station_services import (
                get_filtered_station_ids,
            )

            # Не дублируем фильтр типа станции — он уже в type_ids.
            filter_payload = {
                **filters,
                "station_type_filter": [],
            }
            allowed_ids = set(get_filtered_station_ids(filter_payload) or [])
        except Exception:
            _logger.exception("ee balance ves/ses: filtered station ids load failed")
            allowed_ids = set()
        if not allowed_ids:
            return [], empty_pagination
        query = query.filter(Station.id.in_(allowed_ids))

    stations = query.all()
    if not stations:
        return [], empty_pagination

    current_year, plan_years = classify_ves_ses_generation_years(year_features)
    load_start = int(years[0])
    load_end = int(years[-1])
    if current_year is not None:
        load_start = min(load_start, seven_year_sample_window(current_year)[0])
        load_end = max(load_end, current_year)

    station_ids = [station.id for station in stations]
    own_needs_coefficients = (
        load_hydro_own_needs_coefficients(station_ids, coefficient_type_key)
        if coefficient_type_key is not None
        else {}
    )
    gaes_charge_by_station = (
        _load_gaes_charge_maps(station_ids, load_start, load_end, version_id)
        if coefficient_type_key == "gaes"
        else None
    )
    energy_by_station = _load_energy_maps(
        station_ids, load_start, load_end, version_id, StationEnergyGeneration, "electricity_generation"
    )
    owner_by_station = _load_energy_maps(
        station_ids, load_start, load_end, version_id, StationOwnerEnergyGeneration, "electricity_generation"
    )
    commission_by_station = load_station_commission_years(station_ids, version_id)
    exploitation_date_by_station = load_station_exploitation_dates(station_ids, version_id)
    p_ust_by_station = _load_stations_p_ust(station_ids, years, version_id)

    hierarchy = build_hierarchy_structure(stations, include_names=True)
    grouped = hierarchy.get("grouped_stations") or {}
    est_names = hierarchy.get("energy_system_type_name") or {}
    ues_names = hierarchy.get("union_energy_system_name") or {}
    res_names = hierarchy.get("regional_energy_system_name") or {}
    rd_names = hierarchy.get("regional_district_name") or {}

    est_order = [item.id for item in (get_energy_system_type_list_full() or [])]
    ues_order = [item.id for item in (get_union_energy_system_list_full() or [])]
    ues_sections = _iter_ves_ses_ues_sections(
        grouped,
        est_order=est_order,
        ues_order=ues_order,
        ues_names=ues_names,
        rd_names=rd_names,
    )
    pagination = resolve_ves_ses_pagination(
        page,
        per_page,
        total_sections=len(ues_sections),
        section_titles=[sec["title"] for sec in ues_sections],
    )
    page_sections = ues_sections[pagination["start"] : pagination["end"]]
    page_ues_ids = {sec["ues_id"] for sec in page_sections}
    show_all = bool(pagination.get("show_all"))
    is_last_page = pagination["end"] >= len(ues_sections)
    russia_live_locked = not show_all

    # Станции только выбранных ОЭС — чтобы не раздувать HTML.
    page_station_ids: set[int] = set()
    for sec in page_sections:
        ues_group = (grouped.get(sec["est_id"]) or {}).get(sec["ues_id"]) or {}
        for _res_id, res_group in ues_group.items():
            for rd_id, rd_group in res_group.items():
                if _is_unspecified(rd_names.get(rd_id) or ""):
                    continue
                for _eu_id, eu_stations in rd_group.items():
                    for station in eu_stations:
                        page_station_ids.add(int(station.id))

    lights: dict[int, dict[str, Any]] = {}
    payloads: dict[int, dict[str, Any]] = {}
    for station in stations:
        energy_full = energy_by_station.get(station.id, {})
        owner_full = owner_by_station.get(station.id, {})
        type_key = _station_type_key(
            getattr(getattr(station, "station_type", None), "name", None)
        )
        if calculate_plan:
            min_sample, plan_calc, plan_rules = compute_ves_ses_plan_generation(
                energy_full,
                owner_full,
                current_year=current_year,
                plan_years=plan_years,
                commission_year=commission_by_station.get(station.id),
                capacity_by_year=p_ust_by_station.get(station.id) or {},
                type_key=type_key,
                exploitation_date_expected=exploitation_date_by_station.get(station.id) or "",
            )
        else:
            min_sample, plan_calc, plan_rules = None, {}, {}
        p_ust_years = p_ust_by_station.get(station.id) or {}
        capacity_map = {int(year): p_ust_years.get(int(year)) for year in years}
        station_charge_map = (
            gaes_charge_by_station.get(int(station.id), {})
            if gaes_charge_by_station is not None
            else None
        )
        light = _light_station_metrics(
            years,
            energy_full,
            owner_full,
            capacity_map,
            min_sample,
            plan_calc,
            type_key,
            station_charge_map,
        )
        if coefficient_type_key is not None:
            light.update(
                _hydro_metric_maps(
                    own_needs_coefficients.get(int(station.id)),
                    light["energy"],
                    years,
                    digits,
                )
            )
        lights[station.id] = light
        if int(station.id) not in page_station_ids:
            continue
        payload = _station_payload(
            station,
            years,
            energy_full,
            owner_full,
            capacity_map,
            min_sample,
            plan_calc,
            plan_rules,
            plan_years,
            digits,
            commission_year=commission_by_station.get(station.id),
            current_year=current_year,
            exploitation_date_expected=exploitation_date_by_station.get(station.id) or "",
        )
        if gaes_charge_by_station is not None:
            charge_map = gaes_charge_by_station.get(int(station.id), {})
            payload["gaes_charge"] = {
                int(year): charge_map.get(int(year)) for year in years
            }
            payload["gaes_charge_display"] = {
                int(year): _format_cell(charge_map.get(int(year)), digits) for year in years
            }
            payload["gaes_charge_raw"] = _raw_title_map(payload["gaes_charge"], years)
            payload["gaes_charge_label"] = DATA_LABEL_GAES_CHARGE
            payload["gaes_charge_enabled"] = True
        if coefficient_type_key is not None:
            payload.update(
                _hydro_metric_maps(
                    own_needs_coefficients.get(int(station.id)),
                    payload["energy"],
                    years,
                    digits,
                )
            )
        payloads[station.id] = payload

    def _including_type_rows(
        by_type: dict[str, dict[str, Any]],
        *,
        live_locked: bool = False,
        **extra: Any,
    ) -> list[dict[str, Any]]:
        incl: list[dict[str, Any]] = []
        if _total_has_data(by_type["ves"]):
            incl.append(
                _finalize_total(
                    by_type["ves"], years, digits, "в т.ч. ВЭС", "type_total",
                    type_key="ves", live_locked=live_locked, **extra,
                )
            )
        if _total_has_data(by_type["ses"]):
            incl.append(
                _finalize_total(
                    by_type["ses"], years, digits, "в т.ч. СЭС", "type_total",
                    type_key="ses", live_locked=live_locked, **extra,
                )
            )
        return incl

    def _iter_est_ids():
        seen = set()
        for est_id in est_order:
            if est_id in grouped:
                seen.add(est_id)
                yield est_id
        for est_id in grouped:
            if est_id not in seen:
                yield est_id

    def _iter_ues_ids(est_group):
        seen = set()
        for ues_id in ues_order:
            if ues_id in est_group:
                seen.add(ues_id)
                yield ues_id
        for ues_id in est_group:
            if ues_id not in seen:
                yield ues_id

    # Какие EST заканчиваются на текущей странице (последняя ОЭС блока на странице).
    est_last_ues: dict[Any, Any] = {}
    for sec in ues_sections:
        est_last_ues[sec["est_id"]] = sec["ues_id"]

    rows: list[dict[str, Any]] = []
    body_rows: list[dict[str, Any]] = []
    station_count = 0
    for est_id in _iter_est_ids():
        est_group = grouped.get(est_id) or {}
        est_total = _blank_total(years)
        est_child_rows: list[dict[str, Any]] = []
        for ues_id in _iter_ues_ids(est_group):
            ues_group = est_group.get(ues_id) or {}
            ues_total = _blank_total(years)
            ues_by_type = {"ses": _blank_total(years), "ves": _blank_total(years)}
            ues_child_rows: list[dict[str, Any]] = []
            ues_on_page = ues_id in page_ues_ids
            for res_id, res_group in ues_group.items():
                res_total = _blank_total(years)
                rd_blocks: list[
                    tuple[Any, str, list[dict[str, Any]], dict[str, Any], list[int]]
                ] = []
                for rd_id, rd_group in res_group.items():
                    rd_name = rd_names.get(rd_id) or ""
                    if _is_unspecified(rd_name):
                        continue
                    rd_total = _blank_total(years)
                    rd_station_rows: list[dict[str, Any]] = []
                    rd_station_ids: list[int] = []
                    for _eu_id, eu_stations in rd_group.items():
                        for station in eu_stations:
                            light = lights.get(station.id)
                            if not light:
                                continue
                            sid = int(station.id)
                            rd_station_ids.append(sid)
                            _accumulate_station(rd_total, light)
                            type_key = light.get("type_key")
                            if type_key in ues_by_type:
                                _accumulate_station(ues_by_type[type_key], light)
                            if not ues_on_page:
                                continue
                            payload = payloads.get(station.id)
                            if not payload:
                                continue
                            station_count += 1
                            rd_station_rows.append(
                                {
                                    "kind": "station",
                                    **payload,
                                    "est_id": est_id,
                                    "ues_id": ues_id,
                                    "res_id": res_id,
                                    "rd_id": rd_id,
                                }
                            )
                    rd_station_rows.sort(key=_ves_ses_station_row_sort_key)
                    if rd_station_ids:
                        rd_blocks.append(
                            (rd_id, rd_name, rd_station_rows, rd_total, rd_station_ids)
                        )
                if not rd_blocks:
                    continue

                res_child_rows: list[dict[str, Any]] = []
                res_has_visible = False
                for rd_id, rd_name, rd_station_rows, rd_total, _rd_ids in rd_blocks:
                    _accumulate_station(res_total, rd_total)
                    if rd_station_rows:
                        res_has_visible = True
                        res_child_rows.extend(rd_station_rows)
                        if len(rd_blocks) > 1:
                            res_child_rows.append(
                                _finalize_total(
                                    rd_total,
                                    years,
                                    digits,
                                    f"{rd_name} — всего",
                                    "rd_total",
                                    est_id=est_id,
                                    ues_id=ues_id,
                                    res_id=res_id,
                                    rd_id=rd_id,
                                )
                            )

                _accumulate_station(ues_total, res_total)
                if not res_has_visible:
                    continue
                ues_child_rows.append(
                    {
                        "kind": "res_header",
                        "label": res_names.get(res_id) or "РЭС",
                    }
                )
                ues_child_rows.extend(res_child_rows)
                ues_child_rows.append(
                    _finalize_total(
                        res_total,
                        years,
                        digits,
                        f"{res_names.get(res_id) or 'РЭС'} — всего",
                        "res_total",
                        est_id=est_id,
                        ues_id=ues_id,
                        res_id=res_id,
                    )
                )

            _accumulate_station(est_total, ues_total)
            if not ues_on_page or not ues_child_rows:
                continue
            est_child_rows.extend(ues_child_rows)
            est_child_rows.append(
                _finalize_total(
                    ues_total,
                    years,
                    digits,
                    f"{ues_names.get(ues_id) or 'ОЭС'} — всего",
                    "ues_total",
                    est_id=est_id,
                    ues_id=ues_id,
                )
            )
            est_child_rows.extend(
                _including_type_rows(ues_by_type, est_id=est_id, ues_id=ues_id)
            )

        if not est_child_rows:
            continue
        est_label = est_names.get(est_id) or "Часть энергосистемы"
        est_ends_here = est_last_ues.get(est_id) in page_ues_ids
        est_fully_on_page = set(
            sec["ues_id"] for sec in ues_sections if sec["est_id"] == est_id
        ).issubset(page_ues_ids)
        if not _is_ees_russia_name(est_label) and est_ends_here:
            body_rows.append(
                _finalize_total(
                    est_total,
                    years,
                    digits,
                    f"{est_label} — всего",
                    "est_total",
                    est_id=est_id,
                    live_locked=not est_fully_on_page,
                )
            )
        body_rows.extend(est_child_rows)

    pagination["total_stations"] = len(stations)

    russia_total = _blank_total(years)
    russia_by_type = {"ses": _blank_total(years), "ves": _blank_total(years)}
    for light in lights.values():
        _accumulate_station(russia_total, light)
        type_key = light.get("type_key")
        if type_key in russia_by_type:
            _accumulate_station(russia_by_type[type_key], light)

    if not body_rows and not (is_last_page and _total_has_data(russia_total)):
        return [], pagination
    rows.extend(body_rows)
    if is_last_page:
        rows.append(
            _finalize_total(
                russia_total,
                years,
                digits,
                f"{russia_total_name} — всего",
                "russia_total",
                live_locked=russia_live_locked,
            )
        )
        rows.extend(
            _including_type_rows(russia_by_type, live_locked=russia_live_locked)
        )
    return rows, pagination


def _parse_ves_ses_year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_ves_ses_year_columns(
    start_year: Any = None,
    end_year: Any = None,
    *,
    year_features: dict[int, str] | None = None,
) -> list[int]:
    """По умолчанию: 7 лет факта до текущего, текущий год и 6 лет плана."""
    features = year_features if year_features is not None else get_ee_balance_year_features()
    current_year, _plan_years = classify_ves_ses_generation_years(features)
    start = _parse_ves_ses_year(start_year)
    end = _parse_ves_ses_year(end_year)
    if current_year is not None:
        default_start = int(current_year) - VES_SES_HISTORY_YEARS
        default_end = int(current_year) + VES_SES_PLAN_YEARS
        if start is None:
            start = default_start
        if end is None:
            end = default_end
    if start is None or end is None:
        return get_ee_balance_year_columns(start, end)
    if start > end:
        start, end = end, start
    bounds = get_ee_balance_filter_year_list()
    if bounds:
        lo, hi = bounds[0], bounds[-1]
        start = max(lo, min(start, hi))
        end = max(lo, min(end, hi))
        if start > end:
            start, end = end, start
    return list(range(start, end + 1))


def _has_ves_ses_list_filters(filters: dict[str, Any] | None) -> bool:
    """Есть ли активные фильтры первой строки (как на station_list)."""
    if not filters:
        return False
    for key in (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    ):
        if filters.get(key):
            return True
    for key in ("station_name_filter", "external_code_filter", "gen_company_filter"):
        if str(filters.get(key) or "").strip():
            return True
    return False


def _ves_ses_list_filter_context(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Списки/маппинги и выбранные значения для station_filters_first_row."""
    from app.generation.services.station_services.filters_services import (
        get_territorial_filter_reference_data,
    )

    selected = filters or {}
    data: dict[str, Any] = {}
    try:
        data.update(get_territorial_filter_reference_data() or {})
    except Exception:
        _logger.exception("ee balance ves/ses: territorial filter reference data failed")
        data = {
            "energy_system_type_list": [],
            "union_energy_system_list": [],
            "regional_energy_system_list": [],
            "federal_district_list": [],
            "regional_district_list": [],
        }
    for key in (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    ):
        data[key] = list(selected.get(key) or [])
    data["station_name_filter"] = str(selected.get("station_name_filter") or "")
    data["external_code_filter"] = str(selected.get("external_code_filter") or "")
    data["gen_company_filter"] = str(selected.get("gen_company_filter") or "")
    data["filters_collapse_open"] = True
    return data


def build_ves_ses_page_context(
    *,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    station_type_filter: Any = None,
    page: Any = None,
    per_page: Any = None,
    list_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    year_features = get_ee_balance_year_features()
    years = resolve_ves_ses_year_columns(start_year, end_year, year_features=year_features)
    digits = resolve_ee_balance_rounding_digits(rounding_digits)
    current_year, _plan_years = classify_ves_ses_generation_years(year_features)
    sample_start = sample_end = None
    min_label = "Минимальное значение выработки"
    if current_year is not None:
        sample_start, sample_end = seven_year_sample_window(current_year)
        min_label = f"Минимальное значение выработки с {sample_start} по {sample_end} год"
    selected_type_ids = parse_ves_ses_station_type_filter(station_type_filter)
    filters = list_filters or {}
    can_edit = _can_edit_ves_ses_energy()
    rows, pagination = build_ves_ses_page_rows(
        years,
        digits=digits,
        year_features=year_features,
        station_type_ids=selected_type_ids or None,
        page=page,
        per_page=per_page,
        list_filters=filters,
    )
    filter_ctx = _ves_ses_list_filter_context(filters)
    has_list_filters = _has_ves_ses_list_filters(filters)
    return {
        "page_title": "Выработка электрической энергии СЭС и ВЭС",
        "browser_title": "Выработка ЭЭ СЭС и ВЭС",
        "years": years,
        "year_features": year_features,
        "start_year": years[0] if years else None,
        "end_year": years[-1] if years else None,
        "filter_year_list": get_ee_balance_filter_year_list(),
        "rounding_digits": digits,
        "chiim_scale": CHIIM_HOURS_SCALE,
        "chiim_digits": CHIIM_ROUNDING_DIGITS,
        "chiim_formula": CHIIM_FORMULA_TOOLTIP,
        "min_label": min_label,
        "exploitation_date_label": "Ожидаемая дата ввода в эксплуатацию",
        "rows": rows,
        "can_edit": can_edit,
        "plan_years": _plan_years_from_features(year_features),
        "owner_years": _visible_owner_years(years, year_features),
        "current_year": current_year,
        "sample_start": sample_start,
        "sample_end": sample_end,
        "station_type_name": ves_ses_station_types(),
        "station_type_filter": selected_type_ids,
        "has_active_filters": bool(selected_type_ids) or has_list_filters,
        "pagination": pagination,
        "current_page": pagination.get("page", 1),
        "total_pages": pagination.get("total_pages", 1),
        "per_page": pagination.get("page_size", VES_SES_DEFAULT_PAGE_SIZE),
        "page_size": pagination.get("page_size", VES_SES_DEFAULT_PAGE_SIZE),
        "total_stations": pagination.get("total_stations", 0),
        "total_sections": pagination.get("total_sections", 0),
        "per_page_choices": VES_SES_PAGE_SIZE_CHOICES,
        "page_size_choices": VES_SES_PAGE_SIZE_CHOICES,
        "pagination_all_label": VES_SES_ALL_LABEL,
        "ves_ses_entity_pagination": pagination,
        "pagination_endpoint": "energy_balance_bp.ee_balance_ves_ses",
        "is_station_focus": False,
        "show_gaes_charge": False,
        "is_snee_focus": False,
        "is_coefficient_focus": False,
        "station_focus_key": None,
        **filter_ctx,
    }


def _build_station_focus_page_context(
    *,
    title: str,
    browser_title: str,
    station_type_ids: Callable[[], list[int]],
    russia_total_name: str,
    endpoint: str,
    coefficient_type_key: str | None = None,
    snee_focus: bool = False,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    page: Any = None,
    per_page: Any = None,
    list_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    year_features = get_ee_balance_year_features()
    years = resolve_ves_ses_year_columns(start_year, end_year, year_features=year_features)
    digits = resolve_ee_balance_rounding_digits(rounding_digits)
    rows, pagination = build_ves_ses_page_rows(
        years,
        digits=digits,
        year_features=year_features,
        station_type_ids=station_type_ids(),
        page=page,
        per_page=per_page,
        list_filters=list_filters,
        calculate_plan=False,
        russia_total_name=russia_total_name,
        coefficient_type_key=coefficient_type_key,
    )
    filters = list_filters or {}
    filter_ctx = _ves_ses_list_filter_context(filters)
    return {
        "page_title": title,
        "browser_title": browser_title,
        "years": years,
        "year_features": year_features,
        "start_year": years[0] if years else None,
        "end_year": years[-1] if years else None,
        "filter_year_list": get_ee_balance_filter_year_list(),
        "rounding_digits": digits,
        "chiim_scale": CHIIM_HOURS_SCALE,
        "chiim_digits": CHIIM_ROUNDING_DIGITS,
        "chiim_formula": CHIIM_FORMULA_TOOLTIP,
        "focus_own_needs_formula": (
            f"СН, млн.кВт·ч = СН, % * {DATA_LABEL_ENERGY}"
            if coefficient_type_key is not None
            else (
                "СН,% = Установленная мощность агрегатов, МВт / "
                f"{DATA_LABEL_ENERGY} * 100"
            )
        ),
        "focus_delivery_formula": (
            f"Отпуск электроэнергии, млн.кВт·ч = {DATA_LABEL_ENERGY} - СН, млн.кВт·ч"
            if coefficient_type_key is not None
            else (
                f"Отпуск электроэнергии, млн.кВт·ч = {DATA_LABEL_ENERGY} - "
                f"(СН,% / {DATA_LABEL_ENERGY} * 100)"
            )
        ),
        "min_label": "Минимальное значение выработки",
        "exploitation_date_label": "Ожидаемая дата ввода в эксплуатацию",
        "rows": rows,
        "can_edit": _can_edit_ves_ses_energy(),
        "plan_years": [],
        "owner_years": [],
        "current_year": None,
        "sample_start": None,
        "sample_end": None,
        "station_type_name": [],
        "station_type_filter": [],
        "has_active_filters": _has_ves_ses_list_filters(filters),
        "pagination": pagination,
        "current_page": pagination.get("page", 1),
        "total_pages": pagination.get("total_pages", 1),
        "per_page": pagination.get("page_size", VES_SES_DEFAULT_PAGE_SIZE),
        "page_size": pagination.get("page_size", VES_SES_DEFAULT_PAGE_SIZE),
        "total_stations": pagination.get("total_stations", 0),
        "total_sections": pagination.get("total_sections", 0),
        "per_page_choices": VES_SES_PAGE_SIZE_CHOICES,
        "page_size_choices": VES_SES_PAGE_SIZE_CHOICES,
        "pagination_all_label": VES_SES_ALL_LABEL,
        "ves_ses_entity_pagination": pagination,
        "pagination_endpoint": endpoint,
        "is_station_focus": True,
        "show_gaes_charge": coefficient_type_key == "gaes",
        "is_snee_focus": snee_focus,
        "is_coefficient_focus": coefficient_type_key is not None,
        "station_focus_key": coefficient_type_key,
        **filter_ctx,
    }


def build_aes_page_context(**kwargs: Any) -> dict[str, Any]:
    return _build_station_focus_page_context(
        title="Выработка электрической энергии АЭС",
        browser_title="Выработка ЭЭ АЭС",
        station_type_ids=aes_station_type_ids,
        russia_total_name=AES_RUSSIA_TOTAL_NAME,
        endpoint="energy_balance_bp.ee_balance_aes",
        **kwargs,
    )


def build_ges_page_context(**kwargs: Any) -> dict[str, Any]:
    return _build_station_focus_page_context(
        title="Выработка электрической энергии ГЭС",
        browser_title="Выработка ЭЭ ГЭС",
        station_type_ids=ges_station_type_ids,
        russia_total_name=GES_RUSSIA_TOTAL_NAME,
        coefficient_type_key="ges",
        endpoint="energy_balance_bp.ee_balance_ges",
        **kwargs,
    )


def build_gaes_page_context(**kwargs: Any) -> dict[str, Any]:
    return _build_station_focus_page_context(
        title="Выработка электрической энергии ГАЭС",
        browser_title="Выработка ЭЭ ГАЭС",
        station_type_ids=gaes_station_type_ids,
        russia_total_name=GAES_RUSSIA_TOTAL_NAME,
        coefficient_type_key="gaes",
        endpoint="energy_balance_bp.ee_balance_gaes",
        **kwargs,
    )


def build_snee_page_context(**kwargs: Any) -> dict[str, Any]:
    return _build_station_focus_page_context(
        title="Выработка электрической энергии СНЭЭ",
        browser_title="Выработка ЭЭ СНЭЭ",
        station_type_ids=snee_station_type_ids,
        russia_total_name=SNEE_RUSSIA_TOTAL_NAME,
        endpoint="energy_balance_bp.ee_balance_snee",
        snee_focus=True,
        **kwargs,
    )


def _plan_years_from_features(year_features: dict[int, str]) -> list[int]:
    _current, plan_years = classify_ves_ses_generation_years(year_features)
    return plan_years


def _visible_owner_years(years: list[int], year_features: dict[int, str]) -> list[int]:
    year_set = {int(year) for year in years}
    current_year, plan_years = classify_ves_ses_generation_years(year_features)
    owner_years: list[int] = []
    if current_year is not None and current_year in year_set:
        owner_years.append(current_year)
    for year in plan_years:
        if year in year_set and year not in owner_years:
            owner_years.append(year)
    return owner_years
