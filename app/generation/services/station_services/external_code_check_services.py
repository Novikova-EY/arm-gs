# -*- coding: utf-8 -*-
"""Данные для страницы проверки external_code по версиям БД."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Optional

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station


def get_database_versions_for_check() -> list[dict[str, Any]]:
    """Список версий БД для столбцов таблицы (id, version_number)."""
    versions = (
        DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None))
        .order_by(DatabaseVersion.id)
        .all()
    )
    return [
        {"id": version.id, "version_number": version.version_number}
        for version in versions
        if version.id is not None and version.version_number
    ]


def _collect_anchor_codes(stations: list[Station]) -> tuple[set[str], set[str]]:
    station_codes: set[str] = set()
    machine_codes: set[str] = set()
    for station in stations:
        code = (getattr(station, "external_code", None) or "").strip()
        if code:
            station_codes.add(code)
        for machine in station.machines or []:
            machine_code = (getattr(machine, "external_code", None) or "").strip()
            if machine_code:
                machine_codes.add(machine_code)
    return station_codes, machine_codes


def _build_codes_map(
    model_class,
    external_codes: set[str],
) -> dict[str, dict[Optional[int], str]]:
    result: dict[str, dict[Optional[int], str]] = defaultdict(dict)
    if not external_codes:
        return result

    rows = (
        db.session.query(model_class.external_code, model_class.database_version_id)
        .filter(model_class.external_code.in_(external_codes))
        .all()
    )
    for ext_code, version_id in rows:
        key = (ext_code or "").strip()
        if key:
            result[key][version_id] = key
    return result


def _has_mismatch(anchor_code: str, codes_by_version: dict[int, str]) -> bool:
    values = list(codes_by_version.values())
    if not anchor_code:
        return any(values)

    if not all(values):
        return True
    return len(set(values)) > 1 or any(value != anchor_code for value in values)


def dedupe_station_ids_by_external_code(
    station_ids: list[int],
    preferred_version_id: Optional[int] = None,
) -> list[int]:
    """Оставляет по одной станции на каждый external_code (предпочитая текущую версию БД)."""
    if not station_ids:
        return []

    rows = (
        db.session.query(Station.id, Station.external_code, Station.database_version_id)
        .filter(Station.id.in_(station_ids))
        .all()
    )
    if not rows:
        return []

    def version_rank(version_id: Optional[int]) -> tuple[int, int]:
        if preferred_version_id is not None and version_id == preferred_version_id:
            return (0, version_id or 0)
        if version_id is not None:
            return (1, version_id)
        return (2, 0)

    chosen_by_code: dict[str, tuple[int, tuple[int, int]]] = {}
    no_code_ids: list[int] = []

    for station_id, external_code, version_id in rows:
        code = (external_code or "").strip()
        if not code:
            no_code_ids.append(station_id)
            continue

        rank = (version_rank(version_id), station_id)
        prev = chosen_by_code.get(code)
        if prev is None or rank < prev[1]:
            chosen_by_code[code] = (station_id, rank)

    deduped_ids = [item[0] for item in chosen_by_code.values()]
    deduped_ids.extend(no_code_ids)
    deduped_set = set(deduped_ids)
    return [station_id for station_id in station_ids if station_id in deduped_set]


def dedupe_machines_by_external_code(
    machines: list[Machine],
    preferred_version_id: Optional[int] = None,
) -> list[Machine]:
    """Оставляет по одному агрегату на каждый external_code (предпочитая текущую версию БД)."""
    if not machines:
        return []

    def version_rank(version_id: Optional[int]) -> tuple[int, int]:
        if preferred_version_id is not None and version_id == preferred_version_id:
            return (0, version_id or 0)
        if version_id is not None:
            return (1, version_id)
        return (2, 0)

    chosen_by_code: dict[str, tuple[Machine, tuple[int, int]]] = {}
    no_code: list[Machine] = []

    for machine in machines:
        code = (getattr(machine, "external_code", None) or "").strip()
        if not code:
            no_code.append(machine)
            continue

        rank = (version_rank(getattr(machine, "database_version_id", None)), machine.id or 0)
        prev = chosen_by_code.get(code)
        if prev is None or rank < prev[1]:
            chosen_by_code[code] = (machine, rank)

    return [item[0] for item in chosen_by_code.values()] + no_code


def build_representative_station_id_by_external_code(station_ids: list[int]) -> dict[str, int]:
    """external_code станции -> id строки-представителя на странице."""
    if not station_ids:
        return {}

    rows = (
        db.session.query(Station.external_code, Station.id)
        .filter(Station.id.in_(station_ids))
        .all()
    )
    mapping: dict[str, int] = {}
    for external_code, station_id in rows:
        code = (external_code or "").strip()
        if code and code not in mapping:
            mapping[code] = station_id
    return mapping


@contextmanager
def all_db_versions_context():
    """Временно отключает фильтрацию ORM-запросов по текущей версии БД."""
    from flask import g

    previous = getattr(g, "include_all_db_versions", False)
    g.include_all_db_versions = True
    try:
        yield
    finally:
        g.include_all_db_versions = previous


def attach_external_codes_by_version(
    stations: list[Station],
    database_versions: list[dict[str, Any]],
) -> tuple[dict[str, dict[Optional[int], str]], dict[str, dict[Optional[int], str]]]:
    """Заполняет у станций и агрегатов словарь external_code по версиям БД."""
    version_ids = [version["id"] for version in database_versions]
    station_codes, machine_codes = _collect_anchor_codes(stations)
    station_map = _build_codes_map(Station, station_codes)
    machine_map = _build_codes_map(Machine, machine_codes)

    for station in stations:
        anchor = (getattr(station, "external_code", None) or "").strip()
        station.external_codes_by_version = {
            version_id: station_map.get(anchor, {}).get(version_id, "")
            for version_id in version_ids
        }
        station.external_code_mismatch = _has_mismatch(anchor, station.external_codes_by_version)

        for machine in station.machines or []:
            machine_anchor = (getattr(machine, "external_code", None) or "").strip()
            machine.external_codes_by_version = {
                version_id: machine_map.get(machine_anchor, {}).get(version_id, "")
                for version_id in version_ids
            }
            machine.external_code_mismatch = _has_mismatch(
                machine_anchor, machine.external_codes_by_version
            )

    return station_map, machine_map
