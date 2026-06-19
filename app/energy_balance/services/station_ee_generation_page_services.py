# -*- coding: utf-8 -*-
"""Страница «Выработка ЭЭ» — список электростанций с помесячной выработкой."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from flask import request

from app.common.services.database_version_filter import filter_by_db_version
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
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_districts_map,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_start_year,
    get_year_list_full,
)
from app.energy_balance.services.energy_balance_year_filter_services import (
    get_ee_default_end_year,
    get_ee_default_start_year,
)
from app.common.services.help_services import format_decimal_for_display
from app.energy_balance.models.espp_energy_generation_model import ESPPEnergyGeneration
from app.energy_balance.models.regional_energy_system_energy_generation_model import (
    RES_ENERGY_GENERATION_PERIOD_YEAR,
    RegionalEnergySystemEnergyGeneration,
)
from app.energy_balance.models.station_energy_generation_model import (
    STATION_ENERGY_GENERATION_PERIOD_YEAR,
    StationEnergyGeneration,
)
from app.energy_balance.services.energy_balance_cache import cached_load
from app.generation.models.station.station_constants import (
    STATION_SIGN_ESPP,
    STATION_SIGN_UNSPECIFIED,
)
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.refdata.models.fuels.fuel_model import Fuel
from app.generation.services.station_services.groupped_services import is_current_version
from app.generation.services.station_services.station_services import (
    determine_totals_to_show,
    get_next_station_info,
    get_regional_districts_count_per_res,
    get_regional_districts_with_stations_per_res,
    get_station_ids_for_aggregation,
    get_stations_list,
)
from sqlalchemy.orm import joinedload, selectinload

EE_PERIOD_MODE_YEARS = "years"
EE_PERIOD_MODE_MONTHS = "months"


MONTH_COLUMNS: list[tuple[int, str]] = [
    (1, "янв"),
    (2, "фев"),
    (3, "мар"),
    (4, "апр"),
    (5, "май"),
    (6, "июн"),
    (7, "июл"),
    (8, "авг"),
    (9, "сен"),
    (10, "окт"),
    (11, "ноя"),
    (12, "дек"),
]


STATION_ATTRIBUTE_COLUMN_COUNT = 5

STATION_SIGN_GROUP_ORDER = (STATION_SIGN_UNSPECIFIED, STATION_SIGN_ESPP)


def _station_name_sort_key(row: dict[str, Any]) -> tuple:
    return ((row.get("station_name") or "").lower(), row.get("station_id") or 0)


def _unspecified_station_sort_key(row: dict[str, Any]) -> tuple:
    """Порядок как в справочнике station_type: display_order (NULLS LAST), затем название."""
    display_order = row.get("station_type_display_order")
    return (
        display_order is None,
        display_order if display_order is not None else 0,
        (row.get("station_name") or "").lower(),
        row.get("station_id") or 0,
    )


def _resolve_station_sign(station: Station) -> str:
    if getattr(station, "station_sign", None) == STATION_SIGN_ESPP:
        return STATION_SIGN_ESPP
    return STATION_SIGN_UNSPECIFIED


def _build_sign_groups_for_stations(
    station_rows: list[dict[str, Any]],
    res_id: int,
    espp_by_res: dict[int, dict[int, Decimal | None]],
    period_columns: list[tuple[int, str]],
) -> list[dict[str, Any]]:
    """Группы станций по признаку: сначала «не указано», затем «ЭСПП»."""
    by_sign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in station_rows or []:
        sign = row.get("station_sign") or STATION_SIGN_UNSPECIFIED
        by_sign[sign].append(row)

    groups: list[dict[str, Any]] = []
    espp_periods = espp_by_res.get(res_id, {})
    for sign in STATION_SIGN_GROUP_ORDER:
        rows = by_sign.get(sign) or []
        if not rows:
            continue
        if sign == STATION_SIGN_ESPP:
            rows = sorted(rows, key=_station_name_sort_key)
        else:
            rows = sorted(rows, key=_unspecified_station_sort_key)
        periods = None
        if sign == STATION_SIGN_ESPP:
            periods = {
                period_key: espp_periods.get(period_key)
                for period_key, _label in period_columns
            }
        groups.append(
            {
                "sign": sign,
                "stations": rows,
                "rowspan": len(rows),
                "periods": periods,
                "merge_station_names": sign == STATION_SIGN_ESPP,
            }
        )
    return groups


def _join_unique(values: list[str]) -> str:
    return ", ".join(values) if values else "—"


def ensure_stations_machines_for_display(stations: list[Station]) -> None:
    """Подгружает связи агрегатов, нужные для колонок типа ТЭС/топлива."""
    machine_ids = [m.id for station in stations or [] for m in (station.machines or []) if m.id]
    if not machine_ids:
        return

    enriched = {
        machine.id: machine
        for machine in Machine.query.options(
            joinedload(Machine.tes_machine_type),
            selectinload(Machine.machine_fuels).selectinload(MachineFuel.fuel).selectinload(Fuel.fuel_type),
            selectinload(Machine.machine_powers),
            selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
        )
        .filter(Machine.id.in_(machine_ids))
        .all()
    }
    for station in stations or []:
        station.machines = [
            enriched[m.id] for m in (station.machines or []) if m.id in enriched
        ]


def format_station_machine_attributes(station: Station) -> dict[str, str]:
    """Агрегированные значения колонок по агрегатам электростанции (как на station_list)."""
    station_type_name = "—"
    if station.station_type and station.station_type.name:
        station_type_name = station.station_type.name

    tes_type_parts: list[str] = []
    tes_machine_parts: list[str] = []
    fuel_parts: list[str] = []
    fuel_so_parts: list[str] = []
    seen_tes: set[str] = set()
    seen_tm: set[str] = set()
    seen_fuel: set[str] = set()
    seen_fuel_so: set[str] = set()

    for machine in station.machines or []:
        if machine.tes_types:
            for part in [p.strip() for p in str(machine.tes_types).split(",") if p.strip()]:
                if part not in seen_tes:
                    seen_tes.add(part)
                    tes_type_parts.append(part)

        tm = getattr(machine, "tes_machine_type", None)
        if tm and getattr(tm, "id", None) not in (None, 0):
            tm_name = getattr(tm, "name", None)
            if tm_name and tm_name.lower() != "не указано" and tm_name not in seen_tm:
                seen_tm.add(tm_name)
                tes_machine_parts.append(tm_name)

        primary_fuel = machine.primary_fuel_type
        if primary_fuel:
            fuel_label = (
                primary_fuel
                if isinstance(primary_fuel, str)
                else str(primary_fuel)
            )
            if fuel_label.lower() != "не указано" and fuel_label not in seen_fuel:
                seen_fuel.add(fuel_label)
                fuel_parts.append(fuel_label)

        fuel_so = (machine.fuel_so or "").strip()
        if fuel_so and fuel_so.lower() != "не указано" and fuel_so not in seen_fuel_so:
            seen_fuel_so.add(fuel_so)
            fuel_so_parts.append(fuel_so)

    return {
        "station_type_name": station_type_name,
        "tes_types": _join_unique(tes_type_parts),
        "tes_machine_type": _join_unique(tes_machine_parts),
        "primary_fuel": _join_unique(fuel_parts),
        "fuel_so": _join_unique(fuel_so_parts),
    }


def resolve_single_year_filter(request_args=None) -> tuple[int, list[int]]:
    """Выбранный год и список доступных годов (как на страницах топливных параметров)."""
    args = request_args if request_args is not None else request.args
    fallback_year = get_filter_start_year()
    available_years = sorted(
        {
            int(year.number)
            for year in get_year_list_full()
            if getattr(year, "number", None) is not None
        }
    )

    requested_year = args.get("year", type=int)

    if requested_year in available_years:
        selected_year = requested_year
    elif fallback_year in available_years:
        selected_year = fallback_year
    elif available_years:
        selected_year = available_years[0]
    else:
        selected_year = fallback_year
        available_years = [fallback_year]

    return selected_year, available_years


def _resolve_station_placement(station: Station) -> tuple[int, int, int, int, int]:
    """Возвращает (est_id, ues_id, res_id, rd_id, eu_id) для иерархии и агрегатов."""
    rd_id = station.id_regional_district if station.id_regional_district is not None else -1
    eu_id = station.id_energy_unit if station.id_energy_unit is not None else 0

    if not station.regional_district:
        return -1, -1, -1, rd_id, eu_id

    res = None
    if getattr(station, "id_regional_energy_system", None):
        direct_res = getattr(station, "regional_energy_system_obj", None)
        if direct_res and is_current_version(direct_res):
            res = direct_res

    if res is None:
        rd_res_list = [
            r for r in (station.regional_district.regional_energy_systems or [])
            if is_current_version(r)
        ]
        if not rd_res_list:
            return -1, -1, -1, rd_id, eu_id
        for candidate in rd_res_list:
            u = getattr(candidate, "union_energy_system", None)
            if u and is_current_version(u):
                res = candidate
                break
        if res is None:
            res = rd_res_list[0]

    ues = getattr(res, "union_energy_system", None)
    if not ues or not is_current_version(ues):
        return -1, -1, res.id, rd_id, eu_id

    est_id = ues.id_energy_system_type if ues.id_energy_system_type is not None else -1
    return est_id, ues.id, res.id, rd_id, eu_id


def _add_period_sum(target: dict[int, Decimal], period_key: int, value) -> None:
    if value is None:
        return
    target[period_key] = target.get(period_key, Decimal(0)) + Decimal(str(value))


def build_generation_aggregates(
    stations: list[Station],
    values_by_station: dict[int, dict[int, Decimal | None]],
    espp_by_res: dict[int, dict[int, Decimal | None]] | None = None,
    res_placement: dict[int, tuple[int, int]] | None = None,
) -> dict[str, dict]:
    """Суммы выработки ЭЭ по уровням иерархии (станции + свод ЭСПП по РЭС)."""
    aggregates: dict[str, Any] = {
        "energy_units": defaultdict(dict),
        "regional_districts": defaultdict(dict),
        "regional_energy_systems": defaultdict(dict),
        "union_energy_systems": defaultdict(dict),
        "total": {},
    }

    for station in stations or []:
        if getattr(station, "station_sign", None) == STATION_SIGN_ESPP:
            continue
        periods = values_by_station.get(station.id, {})
        est_id, ues_id, res_id, rd_id, eu_id = _resolve_station_placement(station)

        for period_key, value in periods.items():
            _add_period_sum(aggregates["total"], period_key, value)
            if eu_id:
                _add_period_sum(aggregates["energy_units"][eu_id], period_key, value)
            if rd_id != -1:
                _add_period_sum(aggregates["regional_districts"][rd_id], period_key, value)
            if res_id != -1:
                _add_period_sum(aggregates["regional_energy_systems"][res_id], period_key, value)
            if ues_id != -1:
                _add_period_sum(aggregates["union_energy_systems"][ues_id], period_key, value)

    for res_id, periods in (espp_by_res or {}).items():
        est_id, ues_id = (res_placement or {}).get(res_id, (-1, -1))
        for period_key, value in periods.items():
            _add_period_sum(aggregates["total"], period_key, value)
            if res_id != -1:
                _add_period_sum(aggregates["regional_energy_systems"][res_id], period_key, value)
            if ues_id != -1:
                _add_period_sum(aggregates["union_energy_systems"][ues_id], period_key, value)

    return {
        "energy_units": dict(aggregates["energy_units"]),
        "regional_districts": dict(aggregates["regional_districts"]),
        "regional_energy_systems": dict(aggregates["regional_energy_systems"]),
        "union_energy_systems": dict(aggregates["union_energy_systems"]),
        "total": aggregates["total"],
    }


def build_stations_sum_by_res(
    stations: list[Station],
    values_by_station: dict[int, dict[int, Decimal | None]],
) -> dict[int, dict[int, Decimal | None]]:
    """Сумма выработки по станциям (без ЭСПП) в разрезе РЭС."""
    result: dict[int, dict[int, Decimal | None]] = defaultdict(dict)
    for station in stations or []:
        if getattr(station, "station_sign", None) == STATION_SIGN_ESPP:
            continue
        _est_id, _ues_id, res_id, _rd_id, _eu_id = _resolve_station_placement(station)
        if res_id in (None, -1):
            continue
        for period_key, value in (values_by_station.get(station.id) or {}).items():
            _add_period_sum(result[res_id], period_key, value)
    return {res_id: dict(periods) for res_id, periods in result.items()}


def build_res_verification_by_res(
    res_control_by_res: dict[int, dict[int, Decimal | None]],
    stations_by_res: dict[int, dict[int, Decimal | None]],
    espp_by_res: dict[int, dict[int, Decimal | None]],
    period_columns: list[tuple[int, str]],
) -> dict[int, dict[int, Decimal | None]]:
    """Проверка РЭС = (сумма по станциям + выработка ЭСПП) − контрольный итог."""
    result: dict[int, dict[int, Decimal | None]] = {}
    res_ids = set(res_control_by_res) | set(stations_by_res) | set(espp_by_res)
    for res_id in res_ids:
        period_values: dict[int, Decimal | None] = {}
        for period_key, _label in period_columns:
            control = (res_control_by_res.get(res_id) or {}).get(period_key)
            stations_sum = (stations_by_res.get(res_id) or {}).get(period_key)
            espp_sum = (espp_by_res.get(res_id) or {}).get(period_key)
            if control is None and stations_sum is None and espp_sum is None:
                period_values[period_key] = None
                continue
            period_values[period_key] = (
                Decimal(str(stations_sum or 0))
                + Decimal(str(espp_sum or 0))
                - Decimal(str(control or 0))
            )
        result[res_id] = period_values
    return result


def is_verification_nonzero(value) -> bool:
    if value is None:
        return False
    try:
        return Decimal(str(value)) != 0
    except Exception:
        return False


def build_year_columns(start_year: int, end_year: int) -> list[tuple[int, str]]:
    return [(year, str(year)) for year in range(start_year, end_year + 1)]


def build_res_show_rd_level_map(filters: dict | None = None) -> dict[int, bool]:
    """Показывать уровень субъекта РФ только если в РЭС более одного субъекта (как station_list)."""
    res_to_rd_count = get_regional_districts_count_per_res()
    res_to_rd_with_stations = get_regional_districts_with_stations_per_res(filters)
    result: dict[int, bool] = {}
    for res_id in set(res_to_rd_count) | set(res_to_rd_with_stations):
        result[res_id] = (
            res_to_rd_count.get(res_id, 0) > 1
            and res_to_rd_with_stations.get(res_id, 0) > 1
        )
    return result


def load_monthly_generation_by_station(
    station_ids: list[int],
    year: int,
) -> dict[int, dict[int, Decimal | None]]:
    """station_id -> {month_number: electricity_generation}."""
    if not station_ids:
        return {}

    full_map = cached_load(
        "gen_station_monthly",
        (year,),
        lambda: _load_monthly_generation_all_stations_uncached(year),
    )
    return _slice_generation_map(full_map, station_ids)


def _load_monthly_espp_generation_all_res_uncached(
    year: int,
) -> dict[int, dict[int, Decimal | None]]:
    q = ESPPEnergyGeneration.query.filter(
        ESPPEnergyGeneration.year_number == year,
        ESPPEnergyGeneration.month_number.between(1, 12),
    )
    q = filter_by_db_version(q, ESPPEnergyGeneration)

    result: dict[int, dict[int, Decimal | None]] = defaultdict(dict)
    for row in q.all():
        if row.id_regional_energy_system is None:
            continue
        result[row.id_regional_energy_system][row.month_number] = row.electricity_generation
    return dict(result)


def load_monthly_espp_generation_by_res(
    res_ids: list[int],
    year: int,
) -> dict[int, dict[int, Decimal | None]]:
    """res_id -> {month_number: electricity_generation}."""
    if not res_ids:
        return {}

    full_map = cached_load(
        "gen_espp_monthly",
        (year,),
        lambda: _load_monthly_espp_generation_all_res_uncached(year),
    )
    return _slice_generation_map(full_map, res_ids)


def _load_annual_espp_generation_all_res_uncached(
    start_year: int,
    end_year: int,
) -> dict[int, dict[int, Decimal | None]]:
    q = ESPPEnergyGeneration.query.filter(
        ESPPEnergyGeneration.year_number >= start_year,
        ESPPEnergyGeneration.year_number <= end_year,
        ESPPEnergyGeneration.month_number == STATION_ENERGY_GENERATION_PERIOD_YEAR,
    )
    q = filter_by_db_version(q, ESPPEnergyGeneration)

    result: dict[int, dict[int, Decimal | None]] = defaultdict(dict)
    for row in q.all():
        if row.id_regional_energy_system is None or row.year_number is None:
            continue
        result[row.id_regional_energy_system][row.year_number] = row.electricity_generation
    return dict(result)


def load_annual_espp_generation_by_res(
    res_ids: list[int],
    start_year: int,
    end_year: int,
) -> dict[int, dict[int, Decimal | None]]:
    """res_id -> {year_number: electricity_generation} (month_number = 0)."""
    if not res_ids:
        return {}

    full_map = cached_load(
        "gen_espp_annual",
        (start_year, end_year),
        lambda: _load_annual_espp_generation_all_res_uncached(start_year, end_year),
    )
    return _slice_generation_map(full_map, res_ids)


def _load_monthly_res_control_generation_all_res_uncached(
    year: int,
) -> dict[int, dict[int, Decimal | None]]:
    q = RegionalEnergySystemEnergyGeneration.query.filter(
        RegionalEnergySystemEnergyGeneration.year_number == year,
        RegionalEnergySystemEnergyGeneration.month_number.between(1, 12),
    )
    q = filter_by_db_version(q, RegionalEnergySystemEnergyGeneration)

    result: dict[int, dict[int, Decimal | None]] = defaultdict(dict)
    for row in q.all():
        if row.id_regional_energy_system is None:
            continue
        result[row.id_regional_energy_system][row.month_number] = row.electricity_generation
    return dict(result)


def load_monthly_res_control_generation_by_res(
    res_ids: list[int],
    year: int,
) -> dict[int, dict[int, Decimal | None]]:
    """res_id -> {month_number: electricity_generation} (контрольная выработка РЭС)."""
    if not res_ids:
        return {}

    full_map = cached_load(
        "gen_res_control_monthly",
        (year,),
        lambda: _load_monthly_res_control_generation_all_res_uncached(year),
    )
    return _slice_generation_map(full_map, res_ids)


def _load_annual_res_control_generation_all_res_uncached(
    start_year: int,
    end_year: int,
) -> dict[int, dict[int, Decimal | None]]:
    q = RegionalEnergySystemEnergyGeneration.query.filter(
        RegionalEnergySystemEnergyGeneration.year_number >= start_year,
        RegionalEnergySystemEnergyGeneration.year_number <= end_year,
        RegionalEnergySystemEnergyGeneration.month_number == RES_ENERGY_GENERATION_PERIOD_YEAR,
    )
    q = filter_by_db_version(q, RegionalEnergySystemEnergyGeneration)

    result: dict[int, dict[int, Decimal | None]] = defaultdict(dict)
    for row in q.all():
        if row.id_regional_energy_system is None or row.year_number is None:
            continue
        result[row.id_regional_energy_system][row.year_number] = row.electricity_generation
    return dict(result)


def load_annual_res_control_generation_by_res(
    res_ids: list[int],
    start_year: int,
    end_year: int,
) -> dict[int, dict[int, Decimal | None]]:
    """res_id -> {year_number: electricity_generation} (month_number = 0)."""
    if not res_ids:
        return {}

    full_map = cached_load(
        "gen_res_control_annual",
        (start_year, end_year),
        lambda: _load_annual_res_control_generation_all_res_uncached(start_year, end_year),
    )
    return _slice_generation_map(full_map, res_ids)


def collect_res_ids_from_hierarchy(hierarchy: list[dict[str, Any]]) -> list[int]:
    res_ids: set[int] = set()
    for est_block in hierarchy or []:
        for ues_block in est_block.get("ues_list") or []:
            for res_block in ues_block.get("res_list") or []:
                res_id = res_block.get("res_id")
                if res_id not in (None, -1):
                    res_ids.add(res_id)
    return sorted(res_ids)


def build_res_placement_map(stations: list[Station]) -> dict[int, tuple[int, int]]:
    placement: dict[int, tuple[int, int]] = {}
    for station in stations or []:
        est_id, ues_id, res_id, _rd_id, _eu_id = _resolve_station_placement(station)
        if res_id not in (None, -1) and res_id not in placement:
            placement[res_id] = (est_id, ues_id)
    return placement


def _load_annual_generation_all_stations_uncached(
    start_year: int,
    end_year: int,
) -> dict[int, dict[int, Decimal | None]]:
    q = StationEnergyGeneration.query.filter(
        StationEnergyGeneration.year_number >= start_year,
        StationEnergyGeneration.year_number <= end_year,
        StationEnergyGeneration.month_number == STATION_ENERGY_GENERATION_PERIOD_YEAR,
    )
    q = filter_by_db_version(q, StationEnergyGeneration)

    result: dict[int, dict[int, Decimal | None]] = defaultdict(dict)
    for row in q.all():
        if row.id_station is None or row.year_number is None:
            continue
        result[row.id_station][row.year_number] = row.electricity_generation

    monthly_q = StationEnergyGeneration.query.filter(
        StationEnergyGeneration.year_number >= start_year,
        StationEnergyGeneration.year_number <= end_year,
        StationEnergyGeneration.month_number.between(1, 12),
    )
    monthly_q = filter_by_db_version(monthly_q, StationEnergyGeneration)
    monthly_totals: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal(0))
    for row in monthly_q.all():
        if row.id_station is None or row.year_number is None or row.electricity_generation is None:
            continue
        monthly_totals[(row.id_station, row.year_number)] += row.electricity_generation

    for (station_id, year_number), total in monthly_totals.items():
        if year_number not in result.get(station_id, {}):
            result[station_id][year_number] = total

    return dict(result)


def _load_monthly_generation_all_stations_uncached(
    year: int,
) -> dict[int, dict[int, Decimal | None]]:
    q = StationEnergyGeneration.query.filter(
        StationEnergyGeneration.year_number == year,
        StationEnergyGeneration.month_number.between(1, 12),
    )
    q = filter_by_db_version(q, StationEnergyGeneration)

    result: dict[int, dict[int, Decimal | None]] = defaultdict(dict)
    for row in q.all():
        if row.id_station is None:
            continue
        result[row.id_station][row.month_number] = row.electricity_generation
    return dict(result)


def _slice_generation_map(
    full_map: dict[int, dict[int, Decimal | None]],
    entity_ids: list[int],
) -> dict[int, dict[int, Decimal | None]]:
    if not entity_ids:
        return {}
    wanted = set(entity_ids)
    return {entity_id: periods for entity_id, periods in full_map.items() if entity_id in wanted}


def load_annual_generation_by_station(
    station_ids: list[int],
    start_year: int,
    end_year: int,
) -> dict[int, dict[int, Decimal | None]]:
    """station_id -> {year_number: electricity_generation} (month_number = 0)."""
    if not station_ids:
        return {}

    full_map = cached_load(
        "gen_station_annual",
        (start_year, end_year),
        lambda: _load_annual_generation_all_stations_uncached(start_year, end_year),
    )
    return _slice_generation_map(full_map, station_ids)


def build_station_ee_generation_hierarchy(
    stations: list[Station],
    values_by_station: dict[int, dict[int, Decimal | None]],
    period_columns: list[tuple[int, str]],
    espp_by_res: dict[int, dict[int, Decimal | None]] | None = None,
) -> list[dict[str, Any]]:
    """Иерархия ЕЭС → ОЭС → РЭС → субъект РФ → энергоузел → строки электростанций."""
    est_names = dict(get_energy_system_type_map())
    ues_names = dict(get_union_energy_systems_map())
    ues_display_orders = get_union_energy_system_display_order_map()
    res_names = dict(get_regional_energy_systems_name_map())
    rd_names = dict(get_regional_districts_map())
    est_names[-1] = "Не указано"
    ues_names[-1] = "Не указано"
    res_names[-1] = "Не указано"
    rd_names[-1] = "Не указано"

    hierarchy = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )
    eu_names: dict[int, str] = {}

    for station in stations or []:
        est_id, ues_id, res_id, rd_id, eu_id = _resolve_station_placement(station)

        periods = {
            period_key: values_by_station.get(station.id, {}).get(period_key)
            for period_key, _label in period_columns
        }
        attrs = format_station_machine_attributes(station)
        if eu_id and station.energy_unit and station.energy_unit.name:
            eu_names[eu_id] = station.energy_unit.name

        station_type_display_order = None
        if station.station_type is not None:
            station_type_display_order = station.station_type.display_order

        hierarchy[est_id][ues_id][res_id][rd_id][eu_id].append(
            {
                "station_id": station.id,
                "station_name": station.name or "—",
                "station_sign": _resolve_station_sign(station),
                "station_type_display_order": station_type_display_order,
                "periods": periods,
                **attrs,
            }
        )

    def _sort_key_est(eid):
        return (1 if eid == -1 else 0, est_names.get(eid, ""))

    def _sort_key_ues(uid):
        return union_energy_system_hierarchy_sort_key(uid, ues_names, ues_display_orders)

    def _sort_key_res(rid):
        return (1 if rid == -1 else 0, res_names.get(rid, ""))

    def _sort_key_rd(rid):
        return (1 if rid == -1 else 0, rd_names.get(rid, ""))

    def _sort_key_eu(euid):
        return (1 if not euid else 0, euid or 0)

    result: list[dict[str, Any]] = []
    for est_id in sorted(hierarchy.keys(), key=_sort_key_est):
        ues_list: list[dict[str, Any]] = []
        for ues_id in sorted(hierarchy[est_id].keys(), key=_sort_key_ues):
            res_list: list[dict[str, Any]] = []
            for res_id in sorted(hierarchy[est_id][ues_id].keys(), key=_sort_key_res):
                rd_list: list[dict[str, Any]] = []
                for rd_id in sorted(hierarchy[est_id][ues_id][res_id].keys(), key=_sort_key_rd):
                    eu_list: list[dict[str, Any]] = []
                    for eu_id in sorted(
                        hierarchy[est_id][ues_id][res_id][rd_id].keys(),
                        key=_sort_key_eu,
                    ):
                        station_rows = hierarchy[est_id][ues_id][res_id][rd_id][eu_id]
                        sign_groups = _build_sign_groups_for_stations(
                            station_rows,
                            res_id,
                            espp_by_res or {},
                            period_columns,
                        )
                        eu_list.append(
                            {
                                "eu_id": eu_id,
                                "eu_name": eu_names.get(eu_id, f"id={eu_id}") if eu_id else "—",
                                "sign_groups": sign_groups,
                            }
                        )
                    rd_list.append(
                        {
                            "rd_id": rd_id,
                            "rd_name": rd_names.get(rd_id, f"id={rd_id}"),
                            "eu_list": eu_list,
                        }
                    )
                res_list.append(
                    {
                        "res_id": res_id,
                        "res_name": res_names.get(res_id, f"id={res_id}"),
                        "rd_list": rd_list,
                    }
                )
            ues_list.append(
                {
                    "ues_id": ues_id,
                    "ues_name": ues_names.get(ues_id, f"id={ues_id}"),
                    "res_list": res_list,
                }
            )
        result.append(
            {
                "est_id": est_id,
                "est_name": est_names.get(est_id, f"id={est_id}"),
                "ues_list": ues_list,
            }
        )
    return result


def format_generation_cell(value, rounding_digits: int, *, show_zero: bool = False) -> str:
    if value is None:
        return "—"
    try:
        if Decimal(str(value)) == 0:
            return "0" if show_zero else "—"
    except Exception:
        pass
    return format_decimal_for_display(value, digits=rounding_digits)


def get_station_ee_generation_page_data(
    filters: dict,
    page: int,
    rounding_digits: int,
    period_mode: str = EE_PERIOD_MODE_YEARS,
    selected_year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    per_page: int | str = 10,
    show_totals: bool = False,
) -> dict[str, Any]:
    show_all = isinstance(per_page, str) and str(per_page).lower() == "all"
    list_filters = dict(filters or {})
    for key in ("start_year", "end_year", "year", "page", "ee_period_mode"):
        list_filters.pop(key, None)

    if period_mode == EE_PERIOD_MODE_MONTHS:
        if selected_year is None:
            selected_year, _ = resolve_single_year_filter()
        list_start_year = selected_year
        list_end_year = selected_year
        period_columns = MONTH_COLUMNS
    else:
        if start_year is None or end_year is None:
            start_year = get_ee_default_start_year()
            end_year = get_ee_default_end_year()
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        list_start_year = start_year
        list_end_year = end_year
        period_columns = build_year_columns(start_year, end_year)

    try:
        per_page_int = int(per_page)
    except (TypeError, ValueError):
        per_page_int = 10
    if per_page_int <= 0:
        per_page_int = 10

    need_all_stations = show_all or show_totals
    all_stations: list[Station] = []

    if need_all_stations:
        station_data = get_stations_list(
            page=1,
            per_page="all",
            start_year=list_start_year,
            end_year=list_end_year,
            **list_filters,
        )
        all_stations = station_data.get("stations") or []
        total_count = len(all_stations)

        if show_all:
            page_stations = all_stations
            total_pages = 1
            current_page = 1
        else:
            total_pages = max(1, (total_count + per_page_int - 1) // per_page_int) if total_count else 1
            current_page = min(max(page, 1), total_pages)
            start_idx = (current_page - 1) * per_page_int
            page_stations = all_stations[start_idx : start_idx + per_page_int]
    else:
        station_data = get_stations_list(
            page=page,
            per_page=per_page_int,
            start_year=list_start_year,
            end_year=list_end_year,
            **list_filters,
        )
        page_stations = station_data.get("stations") or []
        total_count = station_data.get("total_count", 0)
        total_pages = max(1, (total_count + per_page_int - 1) // per_page_int) if total_count else 1
        current_page = min(max(page, 1), total_pages)

    ensure_stations_machines_for_display(page_stations)
    station_ids = [s.id for s in page_stations]
    page_res_ids = sorted(
        {
            placement[2]
            for station in page_stations
            for placement in [_resolve_station_placement(station)]
            if placement[2] not in (None, -1)
        }
    )
    if period_mode == EE_PERIOD_MODE_MONTHS:
        values_by_station = load_monthly_generation_by_station(station_ids, selected_year)
        res_control_by_res = load_monthly_res_control_generation_by_res(
            page_res_ids,
            selected_year,
        )
        espp_values_by_res = load_monthly_espp_generation_by_res(page_res_ids, selected_year)
    else:
        values_by_station = load_annual_generation_by_station(
            station_ids,
            start_year,
            end_year,
        )
        res_control_by_res = load_annual_res_control_generation_by_res(
            page_res_ids,
            start_year,
            end_year,
        )
        espp_values_by_res = load_annual_espp_generation_by_res(
            page_res_ids,
            start_year,
            end_year,
        )
    hierarchy = build_station_ee_generation_hierarchy(
        page_stations,
        values_by_station,
        period_columns,
        espp_by_res=espp_values_by_res,
    )
    visible_res_ids = collect_res_ids_from_hierarchy(hierarchy)

    should_show_totals = {
        "energy_units": {},
        "regional_districts": {},
        "regional_energy_systems": {},
        "union_energy_systems": {},
        "energy_system_types": {},
        "total": False,
    }
    generation_aggregates: dict[str, dict] = {}
    res_verification_by_res: dict[int, dict[int, Decimal | None]] = {}

    if show_totals or show_all:
        per_page_for_totals = None if show_all else per_page_int
        next_station_info = None
        if not show_all and per_page_int:
            next_station_info = get_next_station_info(current_page, per_page_int, list_filters)

        should_show_totals = determine_totals_to_show(
            page_stations,
            total_count,
            current_page,
            per_page_for_totals,
            list_filters,
            next_station_info,
            force_full_aggregates=show_totals,
        )

        aggregation_station_ids = get_station_ids_for_aggregation(
            page_stations,
            should_show_totals,
            list_filters,
        )
        if aggregation_station_ids:
            if period_mode == EE_PERIOD_MODE_MONTHS:
                agg_values_by_station = load_monthly_generation_by_station(
                    aggregation_station_ids,
                    selected_year,
                )
            else:
                agg_values_by_station = load_annual_generation_by_station(
                    aggregation_station_ids,
                    start_year,
                    end_year,
                )
            agg_station_map = {s.id: s for s in all_stations if s.id in set(aggregation_station_ids)}
            agg_res_ids = sorted(
                {
                    placement[2]
                    for station in agg_station_map.values()
                    for placement in [_resolve_station_placement(station)]
                    if placement[2] not in (None, -1)
                }
            )
            if period_mode == EE_PERIOD_MODE_MONTHS:
                agg_espp_for_hierarchy = load_monthly_espp_generation_by_res(
                    agg_res_ids,
                    selected_year,
                )
            else:
                agg_espp_for_hierarchy = load_annual_espp_generation_by_res(
                    agg_res_ids,
                    start_year,
                    end_year,
                )
            agg_res_ids = collect_res_ids_from_hierarchy(
                build_station_ee_generation_hierarchy(
                    list(agg_station_map.values()),
                    agg_values_by_station,
                    period_columns,
                    espp_by_res=agg_espp_for_hierarchy,
                )
            )
            if period_mode == EE_PERIOD_MODE_MONTHS:
                agg_espp_values = load_monthly_espp_generation_by_res(agg_res_ids, selected_year)
                agg_res_control = load_monthly_res_control_generation_by_res(
                    agg_res_ids,
                    selected_year,
                )
            else:
                agg_espp_values = load_annual_espp_generation_by_res(
                    agg_res_ids,
                    start_year,
                    end_year,
                )
                agg_res_control = load_annual_res_control_generation_by_res(
                    agg_res_ids,
                    start_year,
                    end_year,
                )
            generation_aggregates = build_generation_aggregates(
                list(agg_station_map.values()),
                agg_values_by_station,
                espp_by_res=agg_espp_values,
                res_placement=build_res_placement_map(all_stations),
            )
            res_control_by_res = agg_res_control
            stations_sum_by_res = build_stations_sum_by_res(
                list(agg_station_map.values()),
                agg_values_by_station,
            )
            res_verification_by_res = build_res_verification_by_res(
                agg_res_control,
                stations_sum_by_res,
                agg_espp_values,
                period_columns,
            )

    return {
        "stations": page_stations,
        "station_ids": station_ids,
        "total_count": total_count,
        "total_pages": total_pages,
        "page": current_page,
        "per_page": per_page,
        "hierarchy": hierarchy,
        "period_columns": period_columns,
        "period_mode": period_mode,
        "rounding_digits": rounding_digits,
        "selected_year": selected_year,
        "start_year": list_start_year,
        "end_year": list_end_year,
        "should_show_totals": should_show_totals,
        "generation_aggregates": generation_aggregates,
        "res_show_rd_level_map": build_res_show_rd_level_map(list_filters),
        "res_control_by_res": res_control_by_res,
        "res_verification_by_res": res_verification_by_res,
    }
