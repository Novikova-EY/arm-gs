# -*- coding: utf-8 -*-
"""Агрегация мощностей электростанции из MachinePower (без таблицы station_powers)."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable, Mapping, Optional

from sqlalchemy import func

from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.common.services.database_version_filter import (
    filter_by_db_version,
    filter_by_explicit_db_version,
)


_POWER_KEYS = ("p_ust", "p_ogr", "p_rasp")


def is_machine_archived(machine: Any) -> bool:
    """Архивный агрегат не участвует в агрегационных суммах мощностей."""
    return bool(getattr(machine, "is_archived", False))


def machine_not_archived_clause():
    """SQL-условие: только неархивные агрегаты (NULL/False считаем активными)."""
    return Machine.is_archived.isnot(True)


def partition_machines_archived_last(machines: Iterable[Any]) -> list[Any]:
    """Активные агрегаты сначала, архивные — в конце списка (порядок внутри групп сохраняется)."""
    active: list[Any] = []
    archived: list[Any] = []
    for machine in machines or []:
        if is_machine_archived(machine):
            archived.append(machine)
        else:
            active.append(machine)
    return active + archived


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _empty_power_row() -> dict[str, Decimal]:
    return {key: Decimal("0") for key in _POWER_KEYS}


def aggregate_powers_from_year_maps(
    machine_year_maps: Iterable[Mapping[int, Mapping[str, Any]]],
    *,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> dict[int, dict[str, Decimal]]:
    """
    Суммирует мощности станции из готовых maps machine.powers_by_year.

    Каждый элемент machine_year_maps: {year: {p_ust, p_ogr, p_rasp}}.
    """
    totals: dict[int, dict[str, Decimal]] = defaultdict(_empty_power_row)

    for year_map in machine_year_maps:
        if not year_map:
            continue
        for year, values in year_map.items():
            if start_year is not None and year < start_year:
                continue
            if end_year is not None and year > end_year:
                continue
            if not isinstance(values, Mapping):
                continue
            row = totals[year]
            for key in _POWER_KEYS:
                raw = values.get(key)
                if raw is not None:
                    row[key] += _to_decimal(raw)

    return {year: dict(values) for year, values in totals.items()}


def aggregate_powers_from_machine_power_rows(
    rows: Iterable[Any],
    *,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> dict[int, dict[str, Decimal]]:
    """
    Суммирует мощности из объектов/строк MachinePower (или совместимых).

    При нескольких записях на один (machine, year) берётся запись с максимальным id
    (как в assign_machine_powers_by_year), затем суммы по станции.
    """
    best_by_machine_year: dict[tuple[Any, int], Any] = {}

    for row in rows or []:
        year = getattr(row, "year_number", None)
        if year is None:
            continue
        if start_year is not None and year < start_year:
            continue
        if end_year is not None and year > end_year:
            continue
        machine_id = getattr(row, "id_machine", None)
        key = (machine_id, year)
        prev = best_by_machine_year.get(key)
        row_id = getattr(row, "id", 0) or 0
        prev_id = getattr(prev, "id", 0) or 0 if prev is not None else -1
        if prev is None or row_id >= prev_id:
            best_by_machine_year[key] = row

    totals: dict[int, dict[str, Decimal]] = defaultdict(_empty_power_row)
    for row in best_by_machine_year.values():
        year = row.year_number
        agg = totals[year]
        for key in _POWER_KEYS:
            raw = getattr(row, key, None)
            if raw is not None:
                agg[key] += _to_decimal(raw)

    return {year: dict(values) for year, values in totals.items()}


def assign_station_powers_from_filtered_machines(
    stations: Iterable[Any],
    start_year: int,
    end_year: int,
) -> None:
    """Заполняет station.powers_by_year суммой machine.powers_by_year (in-memory).

    Архивные агрегаты в сумму не входят.
    """
    for station in stations:
        year_maps = []
        for machine in getattr(station, "machines", None) or []:
            if is_machine_archived(machine):
                continue
            year_maps.append(getattr(machine, "powers_by_year", None) or {})
        station.powers_by_year = aggregate_powers_from_year_maps(
            year_maps,
            start_year=start_year,
            end_year=end_year,
        )


def load_station_powers_by_year(
    station_id: int,
    start_year: int,
    end_year: int,
    version_id: Optional[int] = None,
) -> dict[int, dict[str, Decimal]]:
    """
    Загружает суммарные мощности станции из MachinePower через SQL SUM.

    При version_id is None используется текущая версия БД (filter_by_db_version).
    """
    query = (
        db.session.query(
            MachinePower.year_number,
            func.coalesce(func.sum(MachinePower.p_ust), 0).label("p_ust"),
            func.coalesce(func.sum(MachinePower.p_ogr), 0).label("p_ogr"),
            func.coalesce(func.sum(MachinePower.p_rasp), 0).label("p_rasp"),
        )
        .join(Machine, MachinePower.id_machine == Machine.id)
        .filter(Machine.id_station == station_id)
        .filter(machine_not_archived_clause())
        .filter(MachinePower.year_number.between(start_year, end_year))
        .group_by(MachinePower.year_number)
    )

    if version_id is None:
        query = filter_by_db_version(query, MachinePower)
        query = filter_by_db_version(query, Machine)
    else:
        query = filter_by_explicit_db_version(query, MachinePower, version_id)
        query = filter_by_explicit_db_version(query, Machine, version_id)

    result: dict[int, dict[str, Decimal]] = {}
    for row in query.all():
        result[row.year_number] = {
            "p_ust": _to_decimal(row.p_ust),
            "p_ogr": _to_decimal(row.p_ogr),
            "p_rasp": _to_decimal(row.p_rasp),
        }
    return result


def load_stations_powers_by_year(
    station_ids: Iterable[int],
    years: Iterable[int],
    version_id: Optional[int] = None,
) -> dict[int, dict[int, dict[str, Decimal]]]:
    """
    Пакетная загрузка сумм мощностей для множества станций.

    Архивные агрегаты в суммы не входят.
    Returns: {station_id: {year: {p_ust, p_ogr, p_rasp}}}
    """
    station_id_list = [int(sid) for sid in station_ids if sid is not None]
    year_list = sorted({int(y) for y in years})
    if not station_id_list or not year_list:
        return {}

    query = (
        db.session.query(
            Machine.id_station,
            MachinePower.year_number,
            func.coalesce(func.sum(MachinePower.p_ust), 0).label("p_ust"),
            func.coalesce(func.sum(MachinePower.p_ogr), 0).label("p_ogr"),
            func.coalesce(func.sum(MachinePower.p_rasp), 0).label("p_rasp"),
        )
        .join(Machine, MachinePower.id_machine == Machine.id)
        .filter(Machine.id_station.in_(station_id_list))
        .filter(machine_not_archived_clause())
        .filter(MachinePower.year_number.in_(year_list))
        .group_by(Machine.id_station, MachinePower.year_number)
    )

    if version_id is None:
        query = filter_by_db_version(query, MachinePower)
        query = filter_by_db_version(query, Machine)
    else:
        query = filter_by_explicit_db_version(query, MachinePower, version_id)
        query = filter_by_explicit_db_version(query, Machine, version_id)

    result: dict[int, dict[int, dict[str, Decimal]]] = defaultdict(dict)
    for row in query.all():
        result[row.id_station][row.year_number] = {
            "p_ust": _to_decimal(row.p_ust),
            "p_ogr": _to_decimal(row.p_ogr),
            "p_rasp": _to_decimal(row.p_rasp),
        }
    return dict(result)
