#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cleanup duplicate EquipmentGroupType records and related EquipmentGroupSet rows.

Steps (per database_version_id):
1) Merge EquipmentGroupType duplicates by ref_uuid within the same version.
   - Pick canonical id by highest usage (machines + group sets), then min id.
   - Repoint Machine.id_equipment_group and EquipmentGroupSet.id_equipment_group.
2) Recompute EquipmentGroupSet.external_code after id_equipment_group changes.
3) Merge EquipmentGroupSet duplicates by external_code within the same version.
   - Move links and machines to the kept set, delete duplicates.
"""

import argparse
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, insert, select, update

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam


def _expected_external_code(
    station_external_code: str,
    equipment_group_id: int | None,
    equipment_group_ref_uuid: str | None,
) -> str:
    equipment_group_key = (
        f"equipment_group_ref_uuid|{equipment_group_ref_uuid}"
        if equipment_group_ref_uuid
        else f"equipment_group_id|{equipment_group_id or 0}"
    )
    key = f"equipment_group_set|station|{station_external_code}|{equipment_group_key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _pick_canonical_id(candidates: list[int], version_id: int | None) -> int:
    machine_table = Machine.__table__
    group_set_table = EquipmentGroupSet.__table__
    scores: list[tuple[int, int]] = []
    for eg_id in candidates:
        m_stmt = select(func.count()).select_from(machine_table).where(
            machine_table.c.id_equipment_group == eg_id
        )
        gs_stmt = select(func.count()).select_from(group_set_table).where(
            group_set_table.c.id_equipment_group == eg_id
        )
        if version_id is None:
            m_stmt = m_stmt.where(machine_table.c.database_version_id.is_(None))
            gs_stmt = gs_stmt.where(group_set_table.c.database_version_id.is_(None))
        else:
            m_stmt = m_stmt.where(machine_table.c.database_version_id == version_id)
            gs_stmt = gs_stmt.where(group_set_table.c.database_version_id == version_id)
        m_count = db.session.execute(m_stmt).scalar() or 0
        gs_count = db.session.execute(gs_stmt).scalar() or 0
        scores.append((m_count + gs_count, eg_id))
    scores.sort(key=lambda x: (-x[0], x[1]))
    return scores[0][1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge duplicate EquipmentGroupType/EquipmentGroupSet by ref_uuid/external_code."
    )
    parser.add_argument(
        "--db-version",
        type=int,
        default=None,
        help="database_version_id для обработки (по умолчанию: текущая активная версия)",
    )
    parser.add_argument(
        "--all-versions",
        action="store_true",
        help="Обработать все версии (включая NULL).",
    )
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help="Удалить EquipmentGroupSet без связей и агрегатов.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет сделано")
    parser.add_argument("--yes", action="store_true", help="Без подтверждения")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Determine versions to process
        if args.all_versions:
            all_versions = DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all()
            version_ids = [None] + sorted({v.id for v in all_versions})
        elif args.db_version is not None:
            version_ids = [args.db_version]
        else:
            from app.common.services.database_version_filter import get_current_db_version_id

            version_ids = [get_current_db_version_id()]

        print("=" * 80)
        print("CLEANUP: duplicate EquipmentGroupType / EquipmentGroupSet")
        print("=" * 80)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Versions: {version_ids}")
        if args.dry_run:
            print("[DRY-RUN] Changes are not applied")
        print()

        total_merged_groups = 0
        total_updated_sets = 0
        total_merged_sets = 0
        total_moved_machines = 0
        total_moved_links = 0
        total_deleted_orphans = 0

        for version_id in version_ids:
            eg_table = EquipmentGroupType.__table__
            gs_table = EquipmentGroupSet.__table__
            link_table = EquipmentGroupSetStation.__table__
            machine_table = Machine.__table__
            extra_table = EquipmentGroupExtraFuelParam.__table__

            # 1) Find duplicate equipment groups by ref_uuid within version
            eg_stmt = select(
                eg_table.c.ref_uuid,
                func.array_agg(eg_table.c.id).label("ids"),
            ).where(eg_table.c.ref_uuid.isnot(None))
            if version_id is None:
                eg_stmt = eg_stmt.where(eg_table.c.database_version_id.is_(None))
            else:
                eg_stmt = eg_stmt.where(eg_table.c.database_version_id == version_id)
            eg_stmt = eg_stmt.group_by(eg_table.c.ref_uuid).having(func.count() > 1)
            duplicates = db.session.execute(eg_stmt).all()
            if not duplicates:
                continue

            for ref_uuid, ids in duplicates:
                candidate_ids = list(ids)
                canonical_id = _pick_canonical_id(candidate_ids, version_id)
                other_ids = [i for i in candidate_ids if i != canonical_id]
                if not other_ids:
                    continue

                if not args.dry_run:
                    # Update machines
                    upd_m = update(machine_table).where(
                        machine_table.c.id_equipment_group.in_(other_ids)
                    )
                    if version_id is None:
                        upd_m = upd_m.where(machine_table.c.database_version_id.is_(None))
                    else:
                        upd_m = upd_m.where(machine_table.c.database_version_id == version_id)
                    res = db.session.execute(upd_m.values(id_equipment_group=canonical_id))
                    total_moved_machines += res.rowcount or 0

                    # Update group sets
                    upd_gs = update(gs_table).where(
                        gs_table.c.id_equipment_group.in_(other_ids)
                    )
                    if version_id is None:
                        upd_gs = upd_gs.where(gs_table.c.database_version_id.is_(None))
                    else:
                        upd_gs = upd_gs.where(gs_table.c.database_version_id == version_id)
                    res = db.session.execute(upd_gs.values(id_equipment_group=canonical_id))
                    total_updated_sets += res.rowcount or 0

                total_merged_groups += len(other_ids)

            # 2) Recompute external_code for affected group sets in this version
            if not args.dry_run:
                gs_stmt = select(
                    gs_table.c.id,
                    gs_table.c.id_equipment_group,
                )
                if version_id is None:
                    gs_stmt = gs_stmt.where(gs_table.c.database_version_id.is_(None))
                else:
                    gs_stmt = gs_stmt.where(gs_table.c.database_version_id == version_id)
                gs_rows = db.session.execute(gs_stmt).all()
                for gs_id, eg_id in gs_rows:
                    # Find a station external_code for this group set
                    st_stmt = (
                        select(Station.external_code)
                        .select_from(link_table.join(Station, link_table.c.station_id == Station.id))
                        .where(link_table.c.equipment_group_set_id == gs_id)
                    )
                    if version_id is None:
                        st_stmt = st_stmt.where(link_table.c.database_version_id.is_(None))
                    else:
                        st_stmt = st_stmt.where(link_table.c.database_version_id == version_id)
                    station_code = db.session.execute(st_stmt).scalar()
                    if not station_code:
                        # Fallback: keep existing external_code if no station links
                        continue
                    eg_ref_uuid = db.session.execute(
                        select(EquipmentGroupType.ref_uuid).where(EquipmentGroupType.id == eg_id)
                    ).scalar()
                    expected = _expected_external_code(station_code, eg_id, eg_ref_uuid)
                    db.session.execute(
                        update(gs_table)
                        .where(gs_table.c.id == gs_id)
                        .values(external_code=expected)
                    )

            # 3) Merge duplicate group sets by external_code within version
            gs_dup_stmt = select(
                gs_table.c.external_code,
                func.array_agg(gs_table.c.id).label("ids"),
            ).where(gs_table.c.external_code.isnot(None))
            if version_id is None:
                gs_dup_stmt = gs_dup_stmt.where(gs_table.c.database_version_id.is_(None))
            else:
                gs_dup_stmt = gs_dup_stmt.where(gs_table.c.database_version_id == version_id)
            gs_dup_stmt = gs_dup_stmt.group_by(gs_table.c.external_code).having(func.count() > 1)
            gs_dups = db.session.execute(gs_dup_stmt).all()
            for external_code, ids in gs_dups:
                keep_id = min(ids)
                drop_ids = [i for i in ids if i != keep_id]
                if not drop_ids:
                    continue
                if not args.dry_run:
                    # Remove duplicate links that already exist on keep
                    keep_link = link_table.alias("keep_link")
                    del_stmt = delete(link_table).where(
                        link_table.c.equipment_group_set_id.in_(drop_ids),
                        select(keep_link.c.id)
                        .where(
                            keep_link.c.equipment_group_set_id == keep_id,
                            keep_link.c.station_id == link_table.c.station_id,
                            keep_link.c.database_version_id == link_table.c.database_version_id,
                        )
                        .exists(),
                    )
                    res = db.session.execute(del_stmt)
                    total_moved_links += res.rowcount or 0

                    # Move remaining links to keep
                    upd_links = update(link_table).where(
                        link_table.c.equipment_group_set_id.in_(drop_ids)
                    ).values(equipment_group_set_id=keep_id)
                    res = db.session.execute(upd_links)
                    total_moved_links += res.rowcount or 0

                    # Move machines to keep
                    upd_m = update(machine_table).where(
                        machine_table.c.equipment_group_set_id.in_(drop_ids)
                    ).values(equipment_group_set_id=keep_id)
                    res = db.session.execute(upd_m)
                    total_moved_machines += res.rowcount or 0

                    # Delete dropped group sets
                    db.session.execute(delete(gs_table).where(gs_table.c.id.in_(drop_ids)))

                total_merged_sets += len(drop_ids)

            # 4) Optionally delete orphan group sets (no links, no machines, no extra params)
            if args.delete_orphans and not args.dry_run:
                orphan_stmt = (
                    select(gs_table.c.id)
                    .select_from(gs_table)
                    .outerjoin(link_table, link_table.c.equipment_group_set_id == gs_table.c.id)
                    .outerjoin(machine_table, machine_table.c.equipment_group_set_id == gs_table.c.id)
                    .outerjoin(extra_table, extra_table.c.id_equipment_group_set == gs_table.c.id)
                )
                if version_id is None:
                    orphan_stmt = orphan_stmt.where(gs_table.c.database_version_id.is_(None))
                else:
                    orphan_stmt = orphan_stmt.where(gs_table.c.database_version_id == version_id)
                orphan_stmt = orphan_stmt.group_by(gs_table.c.id).having(
                    func.count(func.distinct(link_table.c.id)) == 0,
                    func.count(func.distinct(machine_table.c.id)) == 0,
                    func.count(func.distinct(extra_table.c.id)) == 0,
                )
                orphan_ids = [row[0] for row in db.session.execute(orphan_stmt).all()]
                if orphan_ids:
                    res = db.session.execute(delete(gs_table).where(gs_table.c.id.in_(orphan_ids)))
                    total_deleted_orphans += res.rowcount or 0

        if args.dry_run:
            print("[DRY-RUN] Done.")
            return

        db.session.commit()
        print(f"Merged EquipmentGroupType duplicates: {total_merged_groups}")
        print(f"Updated EquipmentGroupSet (id_equipment_group): {total_updated_sets}")
        print(f"Merged EquipmentGroupSet duplicates: {total_merged_sets}")
        print(f"Moved Machine rows: {total_moved_machines}")
        print(f"Moved EquipmentGroupSetStation links: {total_moved_links}")
        if args.delete_orphans:
            print(f"Deleted orphan EquipmentGroupSet: {total_deleted_orphans}")
        print(f"Done: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
