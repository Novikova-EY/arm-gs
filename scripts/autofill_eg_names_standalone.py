#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Автономный скрипт для сервера (не требует свежего deb с хелперами).
Массовое заполнение name: «Станция (тип)» при ровно одной привязанной станции.

Запуск на сервере из /opt/generation-app/app:
  python /tmp/autofill_eg_names_standalone.py --dry-run
  python /tmp/autofill_eg_names_standalone.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys

# Корень приложения (рядом с пакетом app/)
APP_ROOT = os.environ.get("GENERATION_APP_ROOT") or "/opt/generation-app/app"
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)
from app.generation.models.station.station_model import Station
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)

NEW_SUFFIX = " (нов)"


def _compose(station_name: str, type_name: str, *, is_new: bool) -> str:
    base = f"{station_name} ({type_name})"
    return f"{base}{NEW_SUFFIX}" if is_new else base


def _suggested_for_group(equipment_group_id: int, current_name: str | None) -> str | None:
    set_rows = (
        EquipmentGroupSet.query.filter_by(equipment_group_id=equipment_group_id)
        .order_by(EquipmentGroupSet.id.asc())
        .all()
    )
    stations_by_id: dict[int, Station] = {}
    type_ids: set[int | None] = set()
    type_by_id: dict[int, EquipmentGroupType] = {}
    for set_row in set_rows:
        link = getattr(set_row, "equipment_group_set_station", None)
        if link is None:
            link = EquipmentGroupSetStation.query.get(
                set_row.equipment_group_set_station_id
            )
        if not link:
            continue
        sid = getattr(link, "station_id", None)
        if sid is None:
            continue
        station = getattr(link, "station", None) or Station.query.get(sid)
        if station is not None:
            stations_by_id[int(sid)] = station
        tid = getattr(link, "equipment_group_type_id", None)
        type_ids.add(tid)
        if tid is not None:
            eg_type = getattr(link, "equipment_group_type", None) or EquipmentGroupType.query.get(
                tid
            )
            if eg_type is not None:
                type_by_id[int(tid)] = eg_type

    if len(stations_by_id) != 1 or len(type_ids) != 1:
        return None
    only_type_id = next(iter(type_ids))
    if only_type_id is None:
        return None
    group_type = type_by_id.get(int(only_type_id))
    station = next(iter(stations_by_id.values()))
    if not group_type or not station or not station.name or not group_type.name:
        return None
    is_new = bool(current_name and str(current_name).strip().endswith(NEW_SUFFIX))
    return _compose(station.name, group_type.name, is_new=is_new)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Автозаполнение name групп: «станция (тип)» (standalone)."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        groups = EquipmentGroup.query.order_by(EquipmentGroup.id.asc()).all()
        planned: list[tuple[EquipmentGroup, str, str]] = []
        skipped_multi = 0
        skipped_same = 0
        for group in groups:
            old_name = (group.name or "").strip()
            suggested = _suggested_for_group(group.id, old_name)
            if not suggested:
                skipped_multi += 1
                continue
            if suggested == old_name:
                skipped_same += 1
                continue
            planned.append((group, old_name, suggested))
            if args.limit and len(planned) >= args.limit:
                break

        print(f"Всего групп: {len(groups)}")
        print(f"Уже совпадают с шаблоном: {skipped_same}")
        print(f"Без автоимени (не одна станция/тип): {skipped_multi}")
        print(f"К обновлению: {len(planned)}")
        for group, old_name, suggested in planned[:30]:
            print(f"  id={group.id} numb={group.numb}: {old_name!r} -> {suggested!r}")
        if len(planned) > 30:
            print(f"  ... и ещё {len(planned) - 30}")

        if args.dry_run or not planned:
            if args.dry_run:
                print("Dry-run: изменений нет.")
            return

        if not args.yes:
            answer = input("Применить изменения? [y/N]: ").strip().lower()
            if answer not in ("y", "yes", "д", "да"):
                print("Отменено.")
                return

        updated = 0
        for group, _old, suggested in planned:
            group.name = suggested
            updated += 1
        db.session.commit()
        print(f"Обновлено: {updated}")


if __name__ == "__main__":
    main()
