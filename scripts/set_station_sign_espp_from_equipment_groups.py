#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Для каждой версии БД: если у электростанции есть хотя бы одна связанная группа
оборудования (как на /fuel/stations_equipment_groups) с vedomstvo = 2
(«пром. предприятие»), проставить Station.station_sign = «ЭСПП».

Связь: EquipmentGroupSetStation -> EquipmentGroupSet -> EquipmentGroup.
Учитывается database_version_id связей и групп (как build_station_equipment_groups_v2).

Запуск из корня репозитория:

  python scripts/set_station_sign_espp_from_equipment_groups.py --dry-run
  python scripts/set_station_sign_espp_from_equipment_groups.py --apply --yes
  python scripts/set_station_sign_espp_from_equipment_groups.py --apply --yes --version-id 20

Опции:
  --version-id ID  обработать только одну версию
  --limit N        вывести не более N примеров станций на версию (dry-run)
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

from sqlalchemy import and_, exists, or_, select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.generation.models.station.station_constants import STATION_SIGN_ESPP
from app.generation.models.station.station_model import Station

# Код ведомства «пром. предприятие» (см. equipment_group_edit_services / stations_equipment_groups.html)
VEDOMSTVO_PROM_ENTERPRISE = 2


def _version_ids_to_process(explicit_version_id: int | None) -> list[int | None]:
    if explicit_version_id is not None:
        return [explicit_version_id]
    ids = [
        row[0]
        for row in db.session.query(DatabaseVersion.id).order_by(DatabaseVersion.id).all()
    ]
    legacy_null = (
        db.session.query(Station.id)
        .filter(Station.database_version_id.is_(None))
        .limit(1)
        .first()
    )
    if legacy_null:
        return [None, *ids]
    return ids


def _station_has_prom_enterprise_group_exists(version_id: int | None):
    """EXISTS: у станции есть группа оборудования с vedomstvo = пром. предприятие."""
    if version_id is None:
        link_version_clause = EquipmentGroupSetStation.database_version_id.is_(None)
        group_version_clause = EquipmentGroup.database_version_id.is_(None)
        station_version_clause = Station.database_version_id.is_(None)
    else:
        link_version_clause = EquipmentGroupSetStation.database_version_id == version_id
        group_version_clause = EquipmentGroup.database_version_id == version_id
        station_version_clause = Station.database_version_id == version_id

    return exists(
        select(1)
        .select_from(EquipmentGroupSet)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .join(EquipmentGroup, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .where(
            EquipmentGroupSetStation.station_id == Station.id,
            EquipmentGroupSetStation.station_id.isnot(None),
            EquipmentGroup.vedomstvo == VEDOMSTVO_PROM_ENTERPRISE,
            link_version_clause,
            group_version_clause,
            station_version_clause,
        )
    )


def process_version(
    version_id: int | None,
    apply: bool,
    sample_limit: int,
) -> dict[str, int | list[tuple[int, str | None]]]:
    station_version_filter = (
        Station.database_version_id.is_(None)
        if version_id is None
        else Station.database_version_id == version_id
    )

    candidates_q = (
        Station.query.filter(
            station_version_filter,
            _station_has_prom_enterprise_group_exists(version_id),
        )
        .order_by(Station.id)
    )
    candidates = candidates_q.all()

    to_update = [s for s in candidates if s.station_sign != STATION_SIGN_ESPP]
    already_ok = len(candidates) - len(to_update)

    samples: list[tuple[int, str | None]] = []
    for station in to_update[:sample_limit]:
        samples.append((station.id, station.name))

    if apply and to_update:
        for station in to_update:
            station.station_sign = STATION_SIGN_ESPP

    return {
        "candidates": len(candidates),
        "updated": len(to_update) if apply else 0,
        "would_update": len(to_update),
        "already_espp": already_ok,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Проставить Station.station_sign = «ЭСПП» по vedomstvo групп оборудования "
            "(пром. предприятие) для всех версий БД."
        )
    )
    parser.add_argument(
        "--version-id",
        type=int,
        default=None,
        help="Обработать только эту database_version_id.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Сколько примеров станций показать на версию (по умолчанию 15).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="План без изменений (режим по умолчанию, если нет --apply).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить обновления и commit.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="С --apply: не спрашивать подтверждение в консоли.",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    if not apply_changes:
        args.dry_run = True

    app = create_app()
    with app.app_context():
        version_ids = _version_ids_to_process(args.version_id)
        if args.version_id is not None:
            exists_row = DatabaseVersion.query.get(args.version_id)
            if exists_row is None:
                print(f"Версия database_version_id={args.version_id} не найдена.")
                sys.exit(1)

        if apply_changes and not args.yes:
            answer = input("Применить изменения station_sign? [y/N]: ").strip().lower()
            if answer not in ("y", "yes", "д", "да"):
                print("Отменено.")
                sys.exit(0)

        mode = "APPLY" if apply_changes else "DRY-RUN"
        print(f"Режим: {mode}")
        print(f"Версий к обработке: {len(version_ids)}")
        print(f"Критерий: vedomstvo = {VEDOMSTVO_PROM_ENTERPRISE} (пром. предприятие)")
        print()

        totals = defaultdict(int)
        for version_id in version_ids:
            label = "NULL (legacy)" if version_id is None else str(version_id)
            stats = process_version(version_id, apply_changes, args.limit)
            totals["candidates"] += stats["candidates"]
            totals["already_espp"] += stats["already_espp"]
            if apply_changes:
                totals["updated"] += stats["updated"]
            else:
                totals["would_update"] += stats["would_update"]

            print(f"--- database_version_id = {label} ---")
            print(f"  станций с пром. предприятием в группах: {stats['candidates']}")
            print(f"  уже station_sign = ЭСПП: {stats['already_espp']}")
            if apply_changes:
                print(f"  обновлено: {stats['updated']}")
            else:
                print(f"  будет обновлено: {stats['would_update']}")
            if stats["samples"]:
                print("  примеры (id, name):")
                for sid, sname in stats["samples"]:
                    print(f"    {sid}: {sname or '—'}")
            print()

        print("=== Итого ===")
        print(f"  кандидатов: {totals['candidates']}")
        print(f"  уже ЭСПП: {totals['already_espp']}")
        if apply_changes:
            print(f"  обновлено: {totals['updated']}")
            if totals["updated"]:
                db.session.commit()
                print("Commit выполнен.")
            else:
                print("Изменений нет, commit не требуется.")
        else:
            print(f"  будет обновлено: {totals['would_update']}")


if __name__ == "__main__":
    main()
