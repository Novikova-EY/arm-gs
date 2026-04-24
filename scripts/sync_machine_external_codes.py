#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Normalize Machine.external_code by machine families across DB versions.

Principles:
- external_code is treated as a persistent identity key of a logical machine;
- we do NOT recompute it from mutable business fields;
- if a family already has one dominant external_code, we keep it;
- only outliers are rewritten;
- ambiguous families are skipped and reported for manual review.

Usage:
    python scripts/sync_machine_external_codes.py
    python scripts/sync_machine_external_codes.py --apply --yes
    python scripts/sync_machine_external_codes.py --apply --yes --versions 20
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.fuel.services.fuel_imports.import_fuel_db_equipment_groups_services import (
    _get_machine_family_for_import,
)
from app.generation.models.machine.machine_model import Machine


@dataclass
class MachineCodePlanRow:
    machine_id: int
    database_version_id: int | None
    station_id: int | None
    machine_number: str | None
    machine_name: str | None
    current_external_code: str
    target_external_code: str
    family_machine_ids: list[int]
    reason: str


@dataclass
class SyncStats:
    scanned_families: int = 0
    scanned_machines: int = 0
    planned_updates: int = 0
    updated: int = 0
    unresolved_families: int = 0
    unresolved_rows: list[dict] = field(default_factory=list)
    by_version_planned: dict[int | None, int] = field(default_factory=lambda: defaultdict(int))
    by_version_updated: dict[int | None, int] = field(default_factory=lambda: defaultdict(int))


def _machine_iteration_order(machine: Machine) -> tuple[int, int, int]:
    version_id = getattr(machine, "database_version_id", None)
    return (0 if version_id == 20 else 1, -1 if version_id is None else version_id, machine.id)


def _iter_anchor_machines() -> list[Machine]:
    return sorted(Machine.query.all(), key=_machine_iteration_order)


def _normalize_code(value: str | None) -> str:
    return (value or "").strip()


def _new_family_external_code() -> str:
    return str(uuid.uuid4())


def _pick_family_external_code(family: list[Machine]) -> tuple[str | None, str]:
    version_buckets: dict[int | None, list[int]] = defaultdict(list)
    for item in family:
        version_buckets[getattr(item, "database_version_id", None)].append(item.id)
    duplicate_versions = {
        version_id: ids for version_id, ids in version_buckets.items() if len(ids) > 1
    }
    if duplicate_versions:
        return None, "duplicate_versions_in_family"

    codes = [_normalize_code(getattr(item, "external_code", None)) for item in family]
    codes = [code for code in codes if code]
    if not codes:
        return _new_family_external_code(), "generated_for_empty_family"

    code_counts = Counter(codes)
    top_count = max(code_counts.values())
    top_codes = sorted(code for code, count in code_counts.items() if count == top_count)
    if len(top_codes) != 1:
        return None, "tied_family_codes"

    return top_codes[0], "majority_existing_family_code"


def _family_has_target_versions(family: list[Machine], version_ids: set[int] | None) -> bool:
    if not version_ids:
        return True
    return any(getattr(item, "database_version_id", None) in version_ids for item in family)


def _deduplicate_family_members(family: list[Machine]) -> list[Machine]:
    seen_ids: set[int] = set()
    deduplicated: list[Machine] = []
    for item in family:
        item_id = getattr(item, "id", None)
        if item_id is None or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        deduplicated.append(item)
    return deduplicated


def _build_plan(version_ids: set[int] | None) -> tuple[list[MachineCodePlanRow], SyncStats]:
    stats = SyncStats()
    plan_rows: list[MachineCodePlanRow] = []
    seen_machine_ids: set[int] = set()
    unresolved_family_keys: set[tuple[int, ...]] = set()
    planned_machine_ids: set[int] = set()
    raw_family_cache: dict[int, list[Machine]] = {}

    def _get_raw_family(anchor_machine: Machine) -> list[Machine]:
        anchor_id = getattr(anchor_machine, "id", None)
        if anchor_id is None:
            return []
        cached = raw_family_cache.get(anchor_id)
        if cached is not None:
            return cached
        family = _get_machine_family_for_import(
            anchor_machine,
            anchor_station_id=getattr(anchor_machine, "id_station", None),
            use_external_code_hints=False,
        )
        if not family:
            family = [anchor_machine]
        family = _deduplicate_family_members(family)
        raw_family_cache[anchor_id] = family
        return family

    for anchor_machine in _iter_anchor_machines():
        anchor_id = getattr(anchor_machine, "id", None)
        if anchor_id is None or anchor_id in seen_machine_ids:
            continue

        raw_family = _get_raw_family(anchor_machine)
        mutual_family: list[Machine] = []
        for item in raw_family:
            item_id = getattr(item, "id", None)
            if item_id is None:
                continue
            reciprocal_family_ids = {
                getattr(member, "id", None)
                for member in _get_raw_family(item)
                if getattr(member, "id", None) is not None
            }
            if anchor_id in reciprocal_family_ids:
                mutual_family.append(item)
        family = _deduplicate_family_members(mutual_family or [anchor_machine])

        family_ids = sorted(item.id for item in family if getattr(item, "id", None) is not None)
        for machine_id in family_ids:
            seen_machine_ids.add(machine_id)

        if not _family_has_target_versions(family, version_ids):
            continue

        stats.scanned_families += 1
        stats.scanned_machines += len(family_ids)
        target_external_code, reason = _pick_family_external_code(family)
        if not target_external_code:
            family_key = tuple(family_ids)
            if family_key not in unresolved_family_keys:
                unresolved_family_keys.add(family_key)
                stats.unresolved_families += 1
            if len(stats.unresolved_rows) < 30 and family_key not in {
                tuple(item["family_machine_ids"]) for item in stats.unresolved_rows
            }:
                stats.unresolved_rows.append(
                    {
                        "reason": reason,
                        "family_machine_ids": family_ids,
                        "versions": sorted(
                            {getattr(item, "database_version_id", None) for item in family},
                            key=lambda value: (-1 if value is None else value),
                        ),
                        "codes": sorted(
                            {
                                _normalize_code(getattr(item, "external_code", None))
                                for item in family
                                if _normalize_code(getattr(item, "external_code", None))
                            }
                        ),
                    }
                )
            continue

        for item in family:
            version_id = getattr(item, "database_version_id", None)
            if version_ids and version_id not in version_ids:
                continue
            if item.id in planned_machine_ids:
                continue
            current_external_code = _normalize_code(getattr(item, "external_code", None))
            if current_external_code == target_external_code:
                continue
            plan_rows.append(
                MachineCodePlanRow(
                    machine_id=item.id,
                    database_version_id=version_id,
                    station_id=getattr(item, "id_station", None),
                    machine_number=getattr(item, "machine_number", None),
                    machine_name=getattr(item, "machine_name", None),
                    current_external_code=current_external_code,
                    target_external_code=target_external_code,
                    family_machine_ids=family_ids,
                    reason=reason,
                )
            )
            stats.planned_updates += 1
            stats.by_version_planned[version_id] += 1
            planned_machine_ids.add(item.id)

    return plan_rows, stats


def _print_report(plan_rows: list[MachineCodePlanRow], stats: SyncStats, apply_mode: bool) -> None:
    print("=" * 88)
    print("Machine external_code family synchronization")
    print("=" * 88)
    print(f"Started: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Mode: {'APPLY' if apply_mode else 'DRY-RUN'}")
    print(f"Scanned families: {stats.scanned_families}")
    print(f"Scanned machines in families: {stats.scanned_machines}")
    print(f"Planned updates: {stats.planned_updates}")
    print(f"Unresolved families: {stats.unresolved_families}")
    print()

    if stats.by_version_planned:
        print("Planned updates by version:")
        for version_id in sorted(stats.by_version_planned, key=lambda v: (-1 if v is None else v)):
            print(f"  version {version_id}: {stats.by_version_planned[version_id]}")
        print()

    if stats.unresolved_rows:
        print("Unresolved families (first 10):")
        for item in stats.unresolved_rows[:10]:
            print(
                f"  reason={item['reason']} versions={item['versions']} "
                f"codes={item['codes']} family_machine_ids={item['family_machine_ids']}"
            )
        print()

    if plan_rows:
        print("Sample planned updates (first 15):")
        for row in plan_rows[:15]:
            print(
                f"  machine_id={row.machine_id} version={row.database_version_id} "
                f"station_id={row.station_id} num={row.machine_number!r} "
                f"name={row.machine_name!r} current={row.current_external_code!r} "
                f"target={row.target_external_code!r} reason={row.reason}"
            )
        print()


def _apply_plan(plan_rows: list[MachineCodePlanRow], stats: SyncStats) -> None:
    if not plan_rows:
        return

    machine_ids = [row.machine_id for row in plan_rows]
    machines = Machine.query.filter(Machine.id.in_(machine_ids)).all()
    machines_by_id = {machine.id: machine for machine in machines}

    for row in plan_rows:
        machine = machines_by_id.get(row.machine_id)
        if machine is None:
            continue
        current_external_code = _normalize_code(getattr(machine, "external_code", None))
        if current_external_code == row.target_external_code:
            continue
        machine.external_code = row.target_external_code
        db.session.add(machine)
        stats.updated += 1
        stats.by_version_updated[row.database_version_id] += 1

    db.session.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize Machine.external_code by machine families."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates to the database. Without this flag the script runs in dry-run mode.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required together with --apply to confirm write operations.",
    )
    parser.add_argument(
        "--versions",
        nargs="*",
        type=int,
        help="Optional list of database_version_id values to limit updated rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and not args.yes:
        print("Refusing to write without --yes. Re-run with: --apply --yes")
        return 2

    version_ids = set(args.versions or [])
    app = create_app()
    with app.app_context():
        plan_rows, stats = _build_plan(version_ids or None)
        _print_report(plan_rows, stats, apply_mode=args.apply)

        if args.apply:
            _apply_plan(plan_rows, stats)
            print("Applied updates:")
            print(f"  updated machines: {stats.updated}")
            if stats.by_version_updated:
                for version_id in sorted(stats.by_version_updated, key=lambda v: (-1 if v is None else v)):
                    print(f"  version {version_id}: {stats.by_version_updated[version_id]}")
        else:
            print("Dry-run only, database was not modified.")

        print(f"Finished: {datetime.now():%Y-%m-%d %H:%M:%S}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
