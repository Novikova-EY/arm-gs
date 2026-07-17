# -*- coding: utf-8 -*-
"""Данные для страницы проверки external_code по версиям БД."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import re
from typing import Any, Optional

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station
from app.refdata.models.territories.regional_district_model import RegionalDistrict


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


def dedupe_station_ids_from_rows(
    rows: list[tuple],
    preferred_version_id: Optional[int] = None,
    machine_counts: Optional[dict[int, int]] = None,
) -> list[int]:
    """Оставляет по одной станции на external_code, сохраняя порядок первых вхождений."""
    if not rows:
        return []

    machine_counts = machine_counts or {}

    def version_rank(version_id: Optional[int]) -> tuple[int, int]:
        if preferred_version_id is not None and version_id == preferred_version_id:
            return (0, version_id or 0)
        if version_id is not None:
            return (1, version_id)
        return (2, 0)

    def territory_rank(id_regional_district, id_regional_energy_system) -> tuple[int, int]:
        if id_regional_district or id_regional_energy_system:
            return (0, id_regional_district or id_regional_energy_system or 0)
        return (1, 0)

    def machines_rank(station_id: int) -> tuple[int, int]:
        count = machine_counts.get(station_id, 0)
        if count > 0:
            return (0, -count)
        return (1, 0)

    chosen_by_code: dict[str, tuple[int, tuple]] = {}
    no_code_ids: list[int] = []
    seen_no_code: set[int] = set()
    rank_by_station_id: dict[int, tuple] = {}

    for row in rows:
        station_id = row[0]
        external_code = row[1] if len(row) > 1 else None
        version_id = row[2] if len(row) > 2 else None
        id_regional_district = row[3] if len(row) > 3 else None
        id_regional_energy_system = row[4] if len(row) > 4 else None

        rank = (
            version_rank(version_id),
            territory_rank(id_regional_district, id_regional_energy_system),
            machines_rank(station_id),
            station_id,
        )
        prev_rank = rank_by_station_id.get(station_id)
        if prev_rank is None or rank < prev_rank:
            rank_by_station_id[station_id] = rank

        code = (external_code or "").strip()
        if not code:
            if station_id not in seen_no_code:
                no_code_ids.append(station_id)
                seen_no_code.add(station_id)
            continue

        prev = chosen_by_code.get(code)
        if prev is None or rank < prev[1]:
            chosen_by_code[code] = (station_id, rank)

    deduped_set = {item[0] for item in chosen_by_code.values()} | set(no_code_ids)
    result: list[int] = []
    seen: set[int] = set()
    for row in rows:
        station_id = row[0]
        if station_id in deduped_set and station_id not in seen:
            result.append(station_id)
            seen.add(station_id)

    if len(result) < 2:
        return result

    parent = {station_id: station_id for station_id in result}

    def find(station_id: int) -> int:
        while parent[station_id] != station_id:
            parent[station_id] = parent[parent[station_id]]
            station_id = parent[station_id]
        return station_id

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    token_owner: dict[tuple[str, object], int] = {}
    family_map = _station_families_for_dedupe_batch(result)
    for station_id in result:
        tokens: set[tuple[str, object]] = set()
        for family_station in family_map.get(station_id, []):
            family_id = getattr(family_station, "id", None)
            if family_id is not None:
                tokens.add(("id", family_id))
            family_code = (getattr(family_station, "external_code", None) or "").strip()
            if family_code:
                tokens.add(("code", family_code))

        for token in tokens:
            owner = token_owner.get(token)
            if owner is None:
                token_owner[token] = station_id
            else:
                union(station_id, owner)

    components: dict[int, list[int]] = defaultdict(list)
    for station_id in result:
        components[find(station_id)].append(station_id)

    collapsed: list[int] = []
    seen_roots: set[int] = set()
    fallback_rank = ((9, 0), (9, 0), (9, 0), 0)
    for station_id in result:
        root = find(station_id)
        if root in seen_roots:
            continue
        seen_roots.add(root)
        collapsed.append(
            min(
                components[root],
                key=lambda item: rank_by_station_id.get(item, fallback_rank),
            )
        )

    return collapsed


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


UNASSIGNED_EST_ID = 0
UNASSIGNED_UES_ID = 0
UNASSIGNED_RES_ID = 0


def _is_current_or_common(entity) -> bool:
    """Строгая проверка версии справочника, без учета all_db_versions_context."""
    from app.common.services.database_version_filter import get_current_db_version_id

    if entity is None:
        return False
    if not hasattr(entity, "database_version_id"):
        return True

    current_version_id = get_current_db_version_id()
    return entity.database_version_id is None or entity.database_version_id == current_version_id


def _canonical_refdata_entity(model_class, name: str | None):
    """Находит одноименный справочник текущей версии, чтобы legacy-id не дробили группы."""
    from sqlalchemy import or_

    from app.common.services.database_version_filter import get_current_db_version_id

    normalized_name = (name or "").strip()
    if not normalized_name:
        return None

    current_version_id = get_current_db_version_id()
    query = db.session.query(model_class).filter(model_class.name == normalized_name)
    if hasattr(model_class, "database_version_id"):
        query = query.filter(
            or_(
                model_class.database_version_id == current_version_id,
                model_class.database_version_id.is_(None),
            )
        ).order_by(model_class.database_version_id.is_(None), model_class.id.asc())
    else:
        query = query.order_by(model_class.id.asc())

    return query.first()


def _resolve_station_hierarchy(station: Station):
    """Определяет est/ues/res/rd для станции (как build_hierarchy_structure, с fallback)."""
    from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    rd_id = station.id_regional_district or 0
    res = None

    if getattr(station, "id_regional_energy_system", None):
        direct_res = getattr(station, "regional_energy_system_obj", None)
        if direct_res:
            res = direct_res

    if res is None and station.regional_district:
        rd_res_list = [
            r for r in (station.regional_district.regional_energy_systems or [])
            if r is not None
        ]
        for r in rd_res_list:
            u = getattr(r, "union_energy_system", None)
            if u:
                res = r
                break
        if res is None and rd_res_list:
            res = rd_res_list[0]

    if res is None:
        return None

    if not _is_current_or_common(res):
        res = _canonical_refdata_entity(RegionalEnergySystem, getattr(res, "name", None)) or res

    ues = getattr(res, "union_energy_system", None)
    if not ues:
        return None

    if not _is_current_or_common(ues):
        ues = _canonical_refdata_entity(UnionEnergySystem, getattr(ues, "name", None)) or ues

    est = getattr(ues, "energy_system_type", None)
    if est is not None and not _is_current_or_common(est):
        est = _canonical_refdata_entity(EnergySystemType, getattr(est, "name", None)) or est

    if station.regional_district and not _is_current_or_common(station.regional_district):
        canonical_rd = _canonical_refdata_entity(
            RegionalDistrict,
            getattr(station.regional_district, "name", None),
        )
        if canonical_rd is not None:
            rd_id = canonical_rd.id

    est_id = getattr(est, "id", None) or getattr(ues, "id_energy_system_type", None) or 0
    return est_id, ues.id, res.id, rd_id


def build_external_code_check_hierarchy(stations: list[Station], include_names: bool = False) -> dict:
    """
    Иерархия для страницы проверки external_code:
    тип ЕЭС → ОЭС → РЭС → субъект → [станции] (без энергоузла).
    """
    from collections import defaultdict

    grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    est_names: dict[int, str] = {}
    ues_names: dict[int, str] = {}
    res_names: dict[int, str] = {}
    rd_names: dict[int, str] = {}
    added_stations: set[tuple] = set()
    grouped_station_ids: set[int] = set()
    skipped = 0

    def _append_station(est_id, ues_id, res_id, rd_id, station):
        station_key = (station.id, est_id, ues_id, res_id, rd_id)
        if station_key in added_stations:
            return
        added_stations.add(station_key)
        grouped_data[est_id][ues_id][res_id][rd_id].append(station)
        grouped_station_ids.add(station.id)

    for station in stations:
        resolved = _resolve_station_hierarchy(station)
        if resolved is None:
            skipped += 1
            _append_station(
                UNASSIGNED_EST_ID,
                UNASSIGNED_UES_ID,
                UNASSIGNED_RES_ID,
                station.id_regional_district or 0,
                station,
            )
            if include_names:
                est_names.setdefault(UNASSIGNED_EST_ID, "Без типа энергосистемы")
                ues_names.setdefault(UNASSIGNED_UES_ID, "—")
                res_names.setdefault(UNASSIGNED_RES_ID, "—")
                if station.regional_district:
                    rd_names[station.id_regional_district or 0] = station.regional_district.name
                elif not station.id_regional_district:
                    rd_names[0] = "не указано"
            continue

        est_id, ues_id, res_id, rd_id = resolved
        _append_station(est_id, ues_id, res_id, rd_id, station)

        if include_names:
            if station.regional_energy_system_obj and station.regional_energy_system_obj.union_energy_system:
                ues = station.regional_energy_system_obj.union_energy_system
                if ues.energy_system_type:
                    est_names[est_id] = ues.energy_system_type.name
                ues_names[ues_id] = ues.name
            elif station.regional_district and station.regional_district.regional_energy_systems:
                res = station.regional_district.regional_energy_systems[0]
                if res and res.union_energy_system:
                    ues = res.union_energy_system
                    if ues.energy_system_type:
                        est_names[est_id] = ues.energy_system_type.name
                    ues_names[ues_id] = ues.name

            if station.regional_energy_system_obj:
                res_names[res_id] = station.regional_energy_system_obj.name
            elif station.regional_district and station.regional_district.regional_energy_systems:
                res_obj = next(
                    (r for r in station.regional_district.regional_energy_systems if r.id == res_id),
                    station.regional_district.regional_energy_systems[0],
                )
                if res_obj:
                    res_names[res_id] = res_obj.name

            if station.regional_district:
                rd_names[rd_id] = station.regional_district.name
            elif rd_id == 0:
                rd_names[rd_id] = "не указано"

    station_order = {station.id: idx for idx, station in enumerate(stations)}
    for est_group in grouped_data.values():
        for ues_group in est_group.values():
            for res_group in ues_group.values():
                for rd_id in res_group:
                    res_group[rd_id].sort(
                        key=lambda st: (station_order.get(st.id, 10**9), st.id)
                    )

    result: dict = {"grouped_stations": grouped_data, "stations": stations, "skipped_count": skipped}
    if include_names:
        result.update(
            {
                "energy_system_type_name": est_names,
                "union_energy_system_name": ues_names,
                "regional_energy_system_name": res_names,
                "regional_district_name": rd_names,
            }
        )
    return result


def build_external_code_check_display_order(
    grouped_stations,
    ues_order_index: dict[int, int],
    res_names: dict,
    rd_names: dict,
) -> dict:
    """Упорядоченные ключи уровней иерархии для шаблона."""
    order: dict = {}
    for est_id, est_group in grouped_stations.items():
        order[est_id] = {}
        ues_ids = sorted(
            est_group.keys(),
            key=lambda u: (ues_order_index.get(u, 10**9), u),
        )
        for ues_id in ues_ids:
            ues_group = est_group[ues_id]
            res_ids = sorted(
                ues_group.keys(),
                key=lambda r: (str(res_names.get(r, "") or "").lower(), r),
            )
            order[est_id][ues_id] = {}
            for res_id in res_ids:
                res_group = ues_group[res_id]
                rd_ids = sorted(
                    res_group.keys(),
                    key=lambda rd: (str(rd_names.get(rd, "") or "").lower(), rd),
                )
                order[est_id][ues_id][res_id] = rd_ids
    return order


def _station_hierarchy_ids(station: Station) -> tuple[int | None, ...]:
    resolved = _resolve_station_hierarchy(station)
    if resolved is None:
        return None, None, None, None
    est_id, ues_id, res_id, rd_id = resolved
    return est_id, ues_id, res_id, rd_id


def station_to_hierarchy_info(station: Station) -> dict:
    """Ключи иерархии для пагинации заголовков (без энергоузла)."""
    resolved = _resolve_station_hierarchy(station)
    if resolved is None:
        return {
            "energy_system_type_id": None,
            "union_energy_system_id": None,
            "regional_energy_system_id": None,
            "regional_district_id": station.id_regional_district,
        }
    est_id, ues_id, res_id, rd_id = resolved
    return {
        "energy_system_type_id": est_id,
        "union_energy_system_id": ues_id,
        "regional_energy_system_id": res_id,
        "regional_district_id": rd_id,
    }


def determine_external_code_check_headers(
    stations_on_page: list[Station],
    prev_page_last_station_info=None,
    regional_districts_count_per_res: dict | None = None,
) -> dict:
    """Заголовки иерархии: субъект показывается только если в РЭС > 2 субъектов."""
    regional_districts_count_per_res = regional_districts_count_per_res or {}

    if not stations_on_page:
        return {}

    show_headers = {
        "energy_system_types": set(),
        "union_energy_systems": set(),
        "regional_energy_systems": set(),
        "regional_districts": set(),
        "energy_units": set(),
    }

    def should_show_rd(res_id: int | None) -> bool:
        if res_id is None:
            return False
        return regional_districts_count_per_res.get(res_id, 0) > 2

    def add_headers(est_id, ues_id, res_id, rd_id, force_all: bool = False):
        if est_id is not None:
            show_headers["energy_system_types"].add(est_id)
        if ues_id is not None:
            show_headers["union_energy_systems"].add(ues_id)
        if res_id is not None:
            show_headers["regional_energy_systems"].add(res_id)
        if rd_id is not None and should_show_rd(res_id):
            show_headers["regional_districts"].add(rd_id)

    first = _station_hierarchy_ids(stations_on_page[0])
    if prev_page_last_station_info is None:
        add_headers(*first, force_all=True)
    else:
        prev_est = prev_page_last_station_info.get("energy_system_type_id")
        prev_ues = prev_page_last_station_info.get("union_energy_system_id")
        prev_res = prev_page_last_station_info.get("regional_energy_system_id")
        prev_rd = prev_page_last_station_info.get("regional_district_id")

        est_id, ues_id, res_id, rd_id = first
        if est_id != prev_est:
            add_headers(est_id, ues_id, res_id, rd_id)
        elif ues_id != prev_ues:
            show_headers["union_energy_systems"].add(ues_id)
            show_headers["regional_energy_systems"].add(res_id)
            if should_show_rd(res_id):
                show_headers["regional_districts"].add(rd_id)
        elif res_id != prev_res:
            show_headers["regional_energy_systems"].add(res_id)
            if should_show_rd(res_id):
                show_headers["regional_districts"].add(rd_id)
        elif rd_id != prev_rd and should_show_rd(res_id):
            show_headers["regional_districts"].add(rd_id)

    prev = first
    for station in stations_on_page[1:]:
        curr = _station_hierarchy_ids(station)
        if curr[0] != prev[0]:
            add_headers(*curr)
        elif curr[1] != prev[1]:
            show_headers["union_energy_systems"].add(curr[1])
            show_headers["regional_energy_systems"].add(curr[2])
            if should_show_rd(curr[2]):
                show_headers["regional_districts"].add(curr[3])
        elif curr[2] != prev[2]:
            show_headers["regional_energy_systems"].add(curr[2])
            if should_show_rd(curr[2]):
                show_headers["regional_districts"].add(curr[3])
        elif curr[3] != prev[3] and should_show_rd(curr[2]):
            show_headers["regional_districts"].add(curr[3])
        prev = curr

    return show_headers


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


def attach_machines_for_external_code_check(stations: list[Station]) -> dict[int, dict]:
    """Лёгкая привязка агрегатов для страницы проверки external_code (все версии БД)."""
    from collections import defaultdict
    import re

    station_totals: dict[int, dict] = {}
    if not stations:
        return station_totals

    page_station_ids = [station.id for station in stations]
    page_station_id_set = set(page_station_ids)

    if not page_station_ids:
        return station_totals

    machines = (
        db.session.query(
            Machine.id,
            Machine.external_code,
            Machine.machine_number,
            Machine.machine_name,
            Machine.machine_group,
            Machine.id_station,
            Machine.database_version_id,
        )
        .filter(Machine.id_station.in_(page_station_ids))
        .all()
    )

    machine_rows = [
        {
            "id": row.id,
            "external_code": row.external_code,
            "machine_number": row.machine_number,
            "machine_name": row.machine_name,
            "machine_group": row.machine_group,
            "id_station": row.id_station,
            "database_version_id": row.database_version_id,
        }
        for row in machines
    ]

    station_machines_map: dict[int, list] = defaultdict(list)

    def machine_number_key(value):
        s = str(value).strip() if value is not None else ""
        match = re.match(r"(\d+)", s)
        if match:
            return (0, int(match.group(1)), s[match.end() :].lower())
        return (1, float("inf"), s.lower())

    # Не схлопываем агрегаты по external_code: дубли кода между разными агрегатами
    # должны быть видны на странице проверки.
    for row in machine_rows:
        station_id = row["id_station"]
        if station_id not in page_station_id_set:
            continue
        machine_obj = type("ExternalCodeMachine", (), {})()
        machine_obj.id = row["id"]
        machine_obj.external_code = row["external_code"]
        machine_obj.machine_number = row["machine_number"]
        machine_obj.machine_name = row["machine_name"]
        machine_obj.display_name = row["machine_name"]
        machine_obj.machine_group = row["machine_group"]
        machine_obj.id_station = station_id
        machine_obj.database_version_id = row["database_version_id"]
        machine_obj.pgu_machines = []
        machine_obj.total_rows = 1
        machine_obj.base_rows = 1
        machine_obj.group_rowspan = 0
        machine_obj.group_base_rows = 1
        machine_obj.group_machine_count = 0
        station_machines_map[station_id].append(machine_obj)

    for station in stations:
        machine_list = station_machines_map.get(station.id, [])
        machine_list.sort(
            key=lambda m: (
                machine_number_key(getattr(m, "machine_number", None)),
                (getattr(m, "machine_name", None) or "").strip().lower(),
                getattr(m, "id", 0) or 0,
            )
        )

        current_group = None
        group_size = 0
        group_start_idx = 0
        for idx, machine in enumerate(machine_list):
            group_value = (getattr(machine, "machine_group", None) or "").strip()
            if not group_value or group_value.lower() == "не указано":
                if group_size > 0:
                    machine_list[group_start_idx].group_rowspan = group_size
                current_group = None
                group_size = 0
                continue

            if group_value != current_group:
                if group_size > 0:
                    machine_list[group_start_idx].group_rowspan = group_size
                current_group = group_value
                group_start_idx = idx
                group_size = 1
            else:
                group_size += 1

        if group_size > 0:
            machine_list[group_start_idx].group_rowspan = group_size

        from sqlalchemy.orm.attributes import set_committed_value

        set_committed_value(station, "machines", machine_list)
        machine_count = len(machine_list)
        station.total_rows = 1 + machine_count
        station.machine_count = machine_count
        station.total_pgu_count = 0
        station_totals[station.id] = {
            "total_rows": station.total_rows,
            "machine_count": machine_count,
            "total_pgu_count": 0,
            "summary_rows": 1,
        }

    return station_totals


def _codes_and_ids_by_version(
    family: list,
    version_ids: list[int],
) -> tuple[dict[int, str], dict[int, Optional[int]]]:
    """Строит словари external_code и id записи по database_version_id."""
    codes: dict[int, str] = {}
    record_ids: dict[int, Optional[int]] = {}
    for version_id in version_ids:
        matched = next(
            (item for item in family if getattr(item, "database_version_id", None) == version_id),
            None,
        )
        if matched is not None:
            codes[version_id] = (getattr(matched, "external_code", None) or "").strip()
            record_ids[version_id] = getattr(matched, "id", None)
        else:
            codes[version_id] = ""
            record_ids[version_id] = None
    return codes, record_ids


def _normalize_check_key(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _normalize_machine_number(value: Any) -> str:
    normalized = " ".join(str(value or "").split()).strip()
    if normalized.isdigit():
        return str(int(normalized))
    return normalized


def _normalize_machine_signature_text(value: Any) -> str:
    normalized = _normalize_check_key(value)
    return (
        normalized.replace("«", '"')
        .replace("»", '"')
        .replace("“", '"')
        .replace("”", '"')
        .replace("'", '"')
    )


def _machine_name_and_group_keys(machine: Machine) -> tuple[str, str]:
    name = " ".join(str(getattr(machine, "machine_name", None) or "").split()).strip()
    group = " ".join(str(getattr(machine, "machine_group", None) or "").split()).strip()

    name_group = ""
    match = re.match(r"^(?P<base>.+?)\s+[–-]\s+(?P<group>котельная\s+.+)$", name, re.IGNORECASE)
    if match:
        name = match.group("base").strip()
        name_group = match.group("group").strip()

    return (
        _normalize_machine_signature_text(name),
        _normalize_machine_signature_text(group or name_group),
    )


def _machine_signature_matches(left: Machine, right: Machine) -> bool:
    left_name, left_group = _machine_name_and_group_keys(left)
    right_name, right_group = _machine_name_and_group_keys(right)
    if not left_name or left_name != right_name:
        return False
    if left_group and right_group:
        return left_group == right_group
    return True


def _regional_district_matches(
    left: RegionalDistrict | None,
    right: RegionalDistrict | None,
) -> bool:
    if left is None or right is None:
        return True
    left_ref_uuid = _normalize_check_key(getattr(left, "ref_uuid", None))
    right_ref_uuid = _normalize_check_key(getattr(right, "ref_uuid", None))
    if left_ref_uuid and right_ref_uuid:
        return left_ref_uuid == right_ref_uuid
    left_region_number = _normalize_check_key(getattr(left, "region_number", None))
    right_region_number = _normalize_check_key(getattr(right, "region_number", None))
    if left_region_number and right_region_number:
        return left_region_number == right_region_number
    left_name = _normalize_check_key(getattr(left, "name", None)) or _normalize_check_key(
        getattr(left, "name_full", None)
    )
    right_name = _normalize_check_key(getattr(right, "name", None)) or _normalize_check_key(
        getattr(right, "name_full", None)
    )
    if left_name and right_name:
        return left_name == right_name
    return True


def _merge_family_by_id(*families) -> list:
    result = []
    seen_ids = set()
    for family in families:
        for item in family or []:
            item_id = getattr(item, "id", None)
            if item_id is None or item_id in seen_ids:
                continue
            result.append(item)
            seen_ids.add(item_id)
    return result


def _station_signature_family(
    db_station: Station,
    signature_candidates: list[Station],
) -> list[Station]:
    name_key = _normalize_check_key(getattr(db_station, "name", None))
    name_so_key = _normalize_check_key(getattr(db_station, "name_so", None))
    name_combined_key = _normalize_check_key(getattr(db_station, "name_combined", None))
    if not name_key and not name_so_key and not name_combined_key:
        return []

    regional_district = getattr(db_station, "regional_district", None)
    signature_family: list[Station] = []
    for candidate in signature_candidates:
        if not _regional_district_matches(
            regional_district,
            getattr(candidate, "regional_district", None),
        ):
            continue
        candidate_name_key = _normalize_check_key(getattr(candidate, "name", None))
        candidate_so_key = _normalize_check_key(getattr(candidate, "name_so", None))
        candidate_combined_key = _normalize_check_key(
            getattr(candidate, "name_combined", None)
        )
        if (
            (name_key and candidate_name_key == name_key)
            or (name_so_key and candidate_so_key == name_so_key)
            or (name_combined_key and candidate_combined_key == name_combined_key)
        ):
            signature_family.append(candidate)
    return signature_family


def _station_families_for_dedupe_batch(station_ids: list[int]) -> dict[int, list[Station]]:
    """Пакетно строит семейства станций для union-find на странице проверки external_code."""
    if not station_ids:
        return {}

    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload

    stations = (
        db.session.query(Station)
        .options(joinedload(Station.regional_district))
        .filter(Station.id.in_(station_ids))
        .all()
    )
    if not stations:
        return {}

    stations_by_id = {station.id: station for station in stations}

    external_codes: set[str] = set()
    name_keys: set[str] = set()
    name_so_keys: set[str] = set()
    name_combined_keys: set[str] = set()
    for station in stations:
        code = (getattr(station, "external_code", None) or "").strip()
        if code:
            external_codes.add(code)
        name_key = _normalize_check_key(getattr(station, "name", None))
        if name_key:
            name_keys.add(name_key)
        name_so_key = _normalize_check_key(getattr(station, "name_so", None))
        if name_so_key:
            name_so_keys.add(name_so_key)
        name_combined_key = _normalize_check_key(getattr(station, "name_combined", None))
        if name_combined_key:
            name_combined_keys.add(name_combined_key)

    code_family_by_code: dict[str, list[Station]] = defaultdict(list)
    if external_codes:
        code_rows = (
            db.session.query(Station)
            .options(joinedload(Station.regional_district))
            .filter(db.func.trim(Station.external_code).in_(external_codes))
            .order_by(Station.database_version_id.asc().nullsfirst(), Station.id.asc())
            .all()
        )
        for row in code_rows:
            code = (getattr(row, "external_code", None) or "").strip()
            if code:
                code_family_by_code[code].append(row)

    signature_filters = []
    if name_keys:
        signature_filters.append(db.func.lower(db.func.trim(Station.name)).in_(name_keys))
    if name_so_keys:
        signature_filters.append(db.func.lower(db.func.trim(Station.name_so)).in_(name_so_keys))
    if name_combined_keys:
        signature_filters.append(
            db.func.lower(db.func.trim(Station.name_combined)).in_(name_combined_keys)
        )

    signature_candidates: list[Station] = []
    if signature_filters:
        signature_candidates = (
            db.session.query(Station)
            .options(joinedload(Station.regional_district))
            .filter(or_(*signature_filters))
            .order_by(Station.database_version_id.asc().nullsfirst(), Station.id.asc())
            .all()
        )

    candidates_by_name: dict[str, list[Station]] = defaultdict(list)
    candidates_by_name_so: dict[str, list[Station]] = defaultdict(list)
    candidates_by_name_combined: dict[str, list[Station]] = defaultdict(list)
    for candidate in signature_candidates:
        candidate_name_key = _normalize_check_key(getattr(candidate, "name", None))
        if candidate_name_key:
            candidates_by_name[candidate_name_key].append(candidate)
        candidate_so_key = _normalize_check_key(getattr(candidate, "name_so", None))
        if candidate_so_key:
            candidates_by_name_so[candidate_so_key].append(candidate)
        candidate_combined_key = _normalize_check_key(getattr(candidate, "name_combined", None))
        if candidate_combined_key:
            candidates_by_name_combined[candidate_combined_key].append(candidate)

    family_map: dict[int, list[Station]] = {}
    for station_id, db_station in stations_by_id.items():
        external_code = (getattr(db_station, "external_code", None) or "").strip()
        name_key = _normalize_check_key(getattr(db_station, "name", None))
        name_so_key = _normalize_check_key(getattr(db_station, "name_so", None))
        name_combined_key = _normalize_check_key(getattr(db_station, "name_combined", None))

        signature_family: list[Station] = []
        if name_key or name_so_key or name_combined_key:
            regional_district = getattr(db_station, "regional_district", None)
            seen_candidate_ids: set[int] = set()
            candidate_lists = []
            if name_key:
                candidate_lists.append(candidates_by_name.get(name_key, []))
            if name_so_key:
                candidate_lists.append(candidates_by_name_so.get(name_so_key, []))
            if name_combined_key:
                candidate_lists.append(candidates_by_name_combined.get(name_combined_key, []))
            for candidates in candidate_lists:
                for candidate in candidates:
                    candidate_id = getattr(candidate, "id", None)
                    if candidate_id is None or candidate_id in seen_candidate_ids:
                        continue
                    if not _regional_district_matches(
                        regional_district,
                        getattr(candidate, "regional_district", None),
                    ):
                        continue
                    seen_candidate_ids.add(candidate_id)
                    signature_family.append(candidate)

        code_family = code_family_by_code.get(external_code, []) if external_code else []
        family_map[station_id] = (
            _merge_family_by_id(signature_family, code_family, [db_station]) or [db_station]
        )

    return family_map


def _station_family_for_check(station: Station) -> list[Station]:
    from sqlalchemy import or_
    from sqlalchemy.orm import joinedload

    db_station = (
        db.session.query(Station)
        .options(joinedload(Station.regional_district))
        .filter(Station.id == station.id)
        .first()
    )
    if not db_station:
        return [station]

    external_code = (getattr(db_station, "external_code", None) or "").strip()
    name_key = _normalize_check_key(getattr(db_station, "name", None))
    name_so_key = _normalize_check_key(getattr(db_station, "name_so", None))
    name_combined_key = _normalize_check_key(getattr(db_station, "name_combined", None))
    regional_district = getattr(db_station, "regional_district", None)

    signature_filters = []
    if name_key:
        signature_filters.append(db.func.lower(db.func.trim(Station.name)) == name_key)
    if name_so_key:
        signature_filters.append(db.func.lower(db.func.trim(Station.name_so)) == name_so_key)
    if name_combined_key:
        signature_filters.append(
            db.func.lower(db.func.trim(Station.name_combined)) == name_combined_key
        )

    signature_family = []
    if signature_filters:
        candidates = (
            db.session.query(Station)
            .options(joinedload(Station.regional_district))
            .filter(or_(*signature_filters))
            .order_by(Station.database_version_id.asc().nullsfirst(), Station.id.asc())
            .all()
        )
        for candidate in candidates:
            if not _regional_district_matches(
                regional_district,
                getattr(candidate, "regional_district", None),
            ):
                continue
            candidate_name_key = _normalize_check_key(getattr(candidate, "name", None))
            candidate_so_key = _normalize_check_key(getattr(candidate, "name_so", None))
            candidate_combined_key = _normalize_check_key(
                getattr(candidate, "name_combined", None)
            )
            if (
                (name_key and candidate_name_key == name_key)
                or (name_so_key and candidate_so_key == name_so_key)
                or (name_combined_key and candidate_combined_key == name_combined_key)
            ):
                signature_family.append(candidate)

    code_family = []
    if external_code:
        code_family = (
            db.session.query(Station)
            .options(joinedload(Station.regional_district))
            .filter(db.func.trim(Station.external_code) == external_code)
            .order_by(Station.database_version_id.asc().nullsfirst(), Station.id.asc())
            .all()
        )

    return _merge_family_by_id(signature_family, code_family, [db_station]) or [db_station]


def _machine_family_for_check(machine: Machine) -> list[Machine]:
    from sqlalchemy.orm import joinedload

    db_machine = (
        db.session.query(Machine)
        .options(joinedload(Machine.machine_station).joinedload(Station.regional_district))
        .filter(Machine.id == machine.id)
        .first()
    )
    if not db_machine:
        return [machine]

    external_code = (getattr(db_machine, "external_code", None) or "").strip()
    machine_number_key = _normalize_machine_number(getattr(db_machine, "machine_number", None))
    machine_name_key = _normalize_check_key(getattr(db_machine, "machine_name", None))
    date_exploitation = getattr(db_machine, "date_exploitation", None)

    signature_family = []
    station = getattr(db_machine, "machine_station", None)
    if station is not None and machine_number_key and machine_name_key:
        station_ids = [
            station_item.id
            for station_item in _station_family_for_check(station)
            if getattr(station_item, "id", None) is not None
        ]
        if station_ids:
            signature_query = (
                db.session.query(Machine)
                .filter(Machine.id_station.in_(station_ids))
            )
            if date_exploitation is None:
                signature_query = signature_query.filter(Machine.date_exploitation.is_(None))
            else:
                signature_query = signature_query.filter(
                    Machine.date_exploitation == date_exploitation
                )
            signature_candidates = signature_query.order_by(
                Machine.database_version_id.asc().nullsfirst(),
                Machine.id.asc(),
            ).all()
            signature_family = [
                candidate
                for candidate in signature_candidates
                if _normalize_machine_number(getattr(candidate, "machine_number", None))
                == machine_number_key
                and _machine_signature_matches(db_machine, candidate)
            ]

    id_ti_family = []
    id_ti = getattr(db_machine, "id_ti", None)
    if id_ti is not None:
        id_ti_family = (
            db.session.query(Machine)
            .filter(Machine.id_ti == id_ti)
            .order_by(Machine.database_version_id.asc().nullsfirst(), Machine.id.asc())
            .all()
        )

    code_family = []
    if external_code:
        code_family = (
            db.session.query(Machine)
            .filter(db.func.trim(Machine.external_code) == external_code)
            .order_by(Machine.database_version_id.asc().nullsfirst(), Machine.id.asc())
            .all()
        )

    return _merge_family_by_id(signature_family, id_ti_family, code_family, [db_machine]) or [
        db_machine
    ]


def attach_external_codes_by_version(
    stations: list[Station],
    database_versions: list[dict[str, Any]],
) -> tuple[dict[str, dict[Optional[int], str]], dict[str, dict[Optional[int], str]]]:
    """Заполняет у станций и агрегатов словарь external_code и id записей по версиям БД."""
    version_ids = [version["id"] for version in database_versions]
    station_codes, machine_codes = _collect_anchor_codes(stations)
    station_map = _build_codes_map(Station, station_codes)
    machine_map = _build_codes_map(Machine, machine_codes)

    with all_db_versions_context():
        for station in stations:
            anchor = (getattr(station, "external_code", None) or "").strip()
            station_family = _station_family_for_check(station)
            family_codes, family_record_ids = _codes_and_ids_by_version(station_family, version_ids)

            station.external_codes_by_version = family_codes
            station.external_code_record_ids_by_version = family_record_ids
            station.external_code_mismatch = _has_mismatch(anchor, station.external_codes_by_version)

            for machine in station.machines or []:
                machine_anchor = (getattr(machine, "external_code", None) or "").strip()
                machine_family = _machine_family_for_check(machine)
                machine_family_codes, machine_record_ids = _codes_and_ids_by_version(
                    machine_family, version_ids
                )

                machine.external_codes_by_version = machine_family_codes
                machine.external_code_record_ids_by_version = machine_record_ids
                machine.external_code_mismatch = _has_mismatch(
                    machine_anchor, machine.external_codes_by_version
                )

    return station_map, machine_map


def _normalize_external_code_value(value: Any) -> str:
    return (value or "").strip()


def _check_external_code_conflict(
    model_class,
    record_id: int,
    version_id: Optional[int],
    new_code: str,
) -> Optional[int]:
    """Возвращает id конфликтующей записи в той же версии, если код уже занят."""
    query = db.session.query(model_class.id).filter(
        model_class.external_code == new_code,
        model_class.id != record_id,
    )
    if version_id is None:
        query = query.filter(model_class.database_version_id.is_(None))
    else:
        query = query.filter(model_class.database_version_id == version_id)
    row = query.first()
    return row[0] if row else None


def update_external_codes_from_check_page(updates: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Обновляет external_code по id записи (станция или агрегат).
    Каждый элемент updates: entity_type ('station'|'machine'), record_id, new_external_code.
    """
    if not updates:
        return {"ok": True, "updated": 0, "skipped": 0, "errors": []}

    model_by_type = {
        "station": Station,
        "machine": Machine,
    }
    updated = 0
    skipped = 0
    errors: list[str] = []

    with all_db_versions_context():
        for item in updates:
            entity_type = (item.get("entity_type") or "").strip().lower()
            record_id = item.get("record_id")
            new_code = _normalize_external_code_value(item.get("new_external_code"))

            if entity_type not in model_by_type:
                errors.append(f"Неизвестный тип сущности: {entity_type!r}")
                continue
            if not record_id:
                errors.append("Не указан record_id")
                continue
            if not new_code:
                errors.append(f"Пустой external_code для {entity_type} id={record_id}")
                continue
            if len(new_code) > 36:
                errors.append(
                    f"external_code слишком длинный для {entity_type} id={record_id} "
                    f"(максимум 36 символов)"
                )
                continue

            model_class = model_by_type[entity_type]
            entity = db.session.get(model_class, int(record_id))
            if entity is None:
                errors.append(f"{entity_type} id={record_id} не найден")
                continue

            current_code = _normalize_external_code_value(getattr(entity, "external_code", None))
            if current_code == new_code:
                skipped += 1
                continue

            conflict_id = _check_external_code_conflict(
                model_class,
                entity.id,
                getattr(entity, "database_version_id", None),
                new_code,
            )
            if conflict_id is not None:
                errors.append(
                    f"Код {new_code!r} уже используется {entity_type} id={conflict_id} "
                    f"в версии БД {getattr(entity, 'database_version_id', None)}"
                )
                continue

            entity.external_code = new_code
            updated += 1

        if errors:
            db.session.rollback()
            return {"ok": False, "updated": 0, "skipped": skipped, "errors": errors}

        db.session.commit()

    return {"ok": True, "updated": updated, "skipped": skipped, "errors": []}
