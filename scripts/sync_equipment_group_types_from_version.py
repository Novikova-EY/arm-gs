#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Synchronize EquipmentGroupType records from a base DB version to all other DB versions.

Goals:
- use version 20 as the canonical source by default;
- ensure the same ref_uuid set exists in every target version;
- update target rows to match canonical fields;
- prune extra target rows that do not exist in the base version;
- safely merge extra rows into a canonical row when names match;
- never delete a referenced extra row unless it can be merged safely.

Usage:
    python scripts/sync_equipment_group_types_from_version.py --dry-run
    python scripts/sync_equipment_group_types_from_version.py --apply --yes
    python scripts/sync_equipment_group_types_from_version.py --base-version 20 --apply --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import (
    TechnologyAvailability,
)
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import (
    TechnologyType,
)
from app.refdata.services.refdata_for_stations.technologies.equipment_group_services import (
    _merge_equipment_group_type_into_canonical,
)
from app.generation.models.machine.machine_model import Machine
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation


BASE_COPY_FIELDS = (
    "name",
    "display_order",
)


@dataclass
class SyncStats:
    created: int = 0
    updated: int = 0
    merged: int = 0
    deleted_unused: int = 0
    skipped_delete_used: int = 0
    missing_technology_type: int = 0
    missing_technology_availability: int = 0
    blocked_extras: list[str] = field(default_factory=list)


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


def _resolve_related_id_by_ref_uuid(
    *,
    model,
    source_id: int | None,
    target_version_id: int,
    cache: dict[tuple[int, int], int | None],
) -> int | None:
    if source_id is None:
        return None

    cache_key = (source_id, target_version_id)
    if cache_key in cache:
        return cache[cache_key]

    source_obj = db.session.get(model, source_id)
    if source_obj is None:
        cache[cache_key] = None
        return None

    ref_uuid = getattr(source_obj, "ref_uuid", None)
    if not ref_uuid:
        cache[cache_key] = None
        return None

    target_obj = (
        model.query.filter(
            model.ref_uuid == ref_uuid,
            model.database_version_id == target_version_id,
        )
        .order_by(model.id.asc())
        .first()
    )
    cache[cache_key] = getattr(target_obj, "id", None)
    return cache[cache_key]


def _collect_usage_counts(equipment_group_type_id: int) -> tuple[int, int]:
    machine_count = (
        db.session.query(func.count(Machine.id))
        .filter(Machine.id_equipment_group == equipment_group_type_id)
        .scalar()
        or 0
    )
    station_link_count = (
        db.session.query(func.count(EquipmentGroupSetStation.id))
        .filter(EquipmentGroupSetStation.equipment_group_type_id == equipment_group_type_id)
        .scalar()
        or 0
    )
    return machine_count, station_link_count


def _delete_equipment_group_type_row(equipment_group_type_id: int) -> None:
    deleted_rows = (
        db.session.query(EquipmentGroupType)
        .filter(EquipmentGroupType.id == equipment_group_type_id)
        .delete(synchronize_session=False)
    )
    if deleted_rows != 1:
        raise ValueError(
            f"Expected to delete one EquipmentGroupType row id={equipment_group_type_id}, "
            f"deleted {deleted_rows}."
        )
    db.session.flush()


def _sync_target_version(
    *,
    base_rows: list[EquipmentGroupType],
    target_version_id: int,
    apply_changes: bool,
    merge_user: str,
    technology_type_cache: dict[tuple[int, int], int | None],
    technology_availability_cache: dict[tuple[int, int], int | None],
) -> SyncStats:
    stats = SyncStats()

    target_rows = (
        EquipmentGroupType.query.filter(
            EquipmentGroupType.database_version_id == target_version_id
        )
        .order_by(EquipmentGroupType.id.asc())
        .all()
    )
    target_by_ref_uuid: dict[str, EquipmentGroupType] = {}
    target_by_name: dict[str, list[EquipmentGroupType]] = defaultdict(list)

    for row in target_rows:
        if getattr(row, "ref_uuid", None):
            target_by_ref_uuid[row.ref_uuid] = row
        target_by_name[_normalize_name(row.name)].append(row)

    matched_target_ids: set[int] = set()
    canonical_target_ids_by_name: dict[str, int] = {}

    for base_row in base_rows:
        canonical_target = target_by_ref_uuid.get(base_row.ref_uuid)

        if canonical_target is None:
            same_name_candidates = [
                row
                for row in target_by_name.get(_normalize_name(base_row.name), [])
                if row.id not in matched_target_ids
            ]
            if same_name_candidates:
                canonical_target = sorted(same_name_candidates, key=lambda row: row.id)[0]

        target_technology_type_id = _resolve_related_id_by_ref_uuid(
            model=TechnologyType,
            source_id=base_row.id_technology_type,
            target_version_id=target_version_id,
            cache=technology_type_cache,
        )
        target_technology_availability_id = _resolve_related_id_by_ref_uuid(
            model=TechnologyAvailability,
            source_id=base_row.id_technology_availability,
            target_version_id=target_version_id,
            cache=technology_availability_cache,
        )

        if base_row.id_technology_type is not None and target_technology_type_id is None:
            stats.missing_technology_type += 1
        if (
            base_row.id_technology_availability is not None
            and target_technology_availability_id is None
        ):
            stats.missing_technology_availability += 1

        if canonical_target is None:
            if apply_changes:
                canonical_target = EquipmentGroupType(
                    database_version_id=target_version_id,
                    ref_uuid=base_row.ref_uuid,
                )
                for field_name in BASE_COPY_FIELDS:
                    setattr(canonical_target, field_name, getattr(base_row, field_name))
                canonical_target.id_technology_type = target_technology_type_id
                canonical_target.id_technology_availability = (
                    target_technology_availability_id
                )
                db.session.add(canonical_target)
                db.session.flush()
            stats.created += 1
            if canonical_target is None:
                continue
            target_by_ref_uuid[canonical_target.ref_uuid] = canonical_target
            target_by_name[_normalize_name(canonical_target.name)].append(canonical_target)

        changed = False
        if canonical_target.database_version_id != target_version_id:
            canonical_target.database_version_id = target_version_id
            changed = True
        if canonical_target.ref_uuid != base_row.ref_uuid:
            canonical_target.ref_uuid = base_row.ref_uuid
            changed = True

        for field_name in BASE_COPY_FIELDS:
            source_value = getattr(base_row, field_name)
            if getattr(canonical_target, field_name) != source_value:
                setattr(canonical_target, field_name, source_value)
                changed = True

        if canonical_target.id_technology_type != target_technology_type_id:
            canonical_target.id_technology_type = target_technology_type_id
            changed = True
        if (
            canonical_target.id_technology_availability
            != target_technology_availability_id
        ):
            canonical_target.id_technology_availability = target_technology_availability_id
            changed = True

        if changed:
            stats.updated += 1
            if apply_changes:
                db.session.add(canonical_target)
                db.session.flush()

        matched_target_ids.add(canonical_target.id)
        canonical_target_ids_by_name[_normalize_name(canonical_target.name)] = (
            canonical_target.id
        )

    extra_rows = [row for row in target_rows if row.id not in matched_target_ids]
    for extra_row in extra_rows:
        normalized_name = _normalize_name(extra_row.name)
        canonical_target_id = canonical_target_ids_by_name.get(normalized_name)

        if canonical_target_id and canonical_target_id != extra_row.id:
            stats.merged += 1
            if apply_changes:
                _merge_equipment_group_type_into_canonical(
                    from_id=extra_row.id,
                    to_id=canonical_target_id,
                    user=merge_user,
                )
            continue

        machine_count, station_link_count = _collect_usage_counts(extra_row.id)
        if machine_count == 0 and station_link_count == 0:
            stats.deleted_unused += 1
            if apply_changes:
                _delete_equipment_group_type_row(extra_row.id)
            continue

        stats.skipped_delete_used += 1
        stats.blocked_extras.append(
            "target_version="
            f"{target_version_id}; id={extra_row.id}; name={extra_row.name!r}; "
            f"machines={machine_count}; station_links={station_link_count}"
        )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync EquipmentGroupType records from a base DB version to all other versions."
    )
    parser.add_argument(
        "--base-version",
        type=int,
        default=20,
        help="Canonical source database_version_id (default: 20).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes only (default behavior if --apply is not used).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the database.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask for confirmation before applying changes.",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    if not apply_changes:
        args.dry_run = True

    app = create_app()
    with app.app_context():
        base_version = db.session.get(DatabaseVersion, args.base_version)
        if base_version is None:
            raise ValueError(f"Base version id={args.base_version} was not found.")

        base_rows = (
            EquipmentGroupType.query.filter(
                EquipmentGroupType.database_version_id == args.base_version
            )
            .order_by(EquipmentGroupType.id.asc())
            .all()
        )
        if not base_rows:
            raise ValueError(
                f"No EquipmentGroupType rows found in base version id={args.base_version}."
            )

        target_versions = (
            DatabaseVersion.query.filter(
                DatabaseVersion.id.isnot(None),
                DatabaseVersion.id != args.base_version,
            )
            .order_by(DatabaseVersion.id.asc())
            .all()
        )
        if not target_versions:
            print("No target versions found. Nothing to do.")
            return

        print("=" * 88)
        print("EquipmentGroupType synchronization from base version")
        print("=" * 88)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Base version: {args.base_version}")
        print(f"Base rows: {len(base_rows)}")
        print(
            "Mode: "
            + ("APPLY (changes will be committed)" if apply_changes else "DRY-RUN")
        )
        print(f"Target versions: {[version.id for version in target_versions]}")
        print()

        if apply_changes and not args.yes:
            confirmation = input(
                "Apply synchronization of EquipmentGroupType to all target versions? [y/N]: "
            ).strip().lower()
            if confirmation not in ("y", "yes"):
                print("Cancelled.")
                return

        technology_type_cache: dict[tuple[int, int], int | None] = {}
        technology_availability_cache: dict[tuple[int, int], int | None] = {}
        aggregate = SyncStats()

        try:
            for target_version in target_versions:
                stats = _sync_target_version(
                    base_rows=base_rows,
                    target_version_id=target_version.id,
                    apply_changes=apply_changes,
                    merge_user="sync_equipment_group_types_from_version",
                    technology_type_cache=technology_type_cache,
                    technology_availability_cache=technology_availability_cache,
                )
                aggregate.created += stats.created
                aggregate.updated += stats.updated
                aggregate.merged += stats.merged
                aggregate.deleted_unused += stats.deleted_unused
                aggregate.skipped_delete_used += stats.skipped_delete_used
                aggregate.missing_technology_type += stats.missing_technology_type
                aggregate.missing_technology_availability += (
                    stats.missing_technology_availability
                )
                aggregate.blocked_extras.extend(stats.blocked_extras)

                print(
                    f"[version {target_version.id}] "
                    f"create={stats.created} update={stats.updated} "
                    f"merge={stats.merged} delete_unused={stats.deleted_unused} "
                    f"skip_used={stats.skipped_delete_used} "
                    f"missing_tech_type={stats.missing_technology_type} "
                    f"missing_tech_availability={stats.missing_technology_availability}"
                )

            if apply_changes:
                db.session.commit()
            else:
                db.session.rollback()
        except Exception:
            db.session.rollback()
            raise

        print()
        print("-" * 88)
        print("Summary")
        print("-" * 88)
        print(f"Created: {aggregate.created}")
        print(f"Updated: {aggregate.updated}")
        print(f"Merged extras into canonical rows: {aggregate.merged}")
        print(f"Deleted unused extras: {aggregate.deleted_unused}")
        print(f"Skipped deleting used extras: {aggregate.skipped_delete_used}")
        print(
            "Missing target TechnologyType refs during sync: "
            f"{aggregate.missing_technology_type}"
        )
        print(
            "Missing target TechnologyAvailability refs during sync: "
            f"{aggregate.missing_technology_availability}"
        )
        if aggregate.blocked_extras:
            print()
            print("Blocked extra rows (referenced, not deleted):")
            for line in aggregate.blocked_extras[:100]:
                print(f"  {line}")
            if len(aggregate.blocked_extras) > 100:
                print(
                    f"  ... and {len(aggregate.blocked_extras) - 100} more blocked rows"
                )

        print()
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
