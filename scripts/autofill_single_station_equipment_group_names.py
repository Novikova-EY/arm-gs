#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Массовое заполнение названий групп оборудования:

  «Название станции (тип группы оборудования)»

только для групп с ровно одной привязанной станцией и единым типом.
Группы с несколькими станциями или без типа не меняются.
Суффикс « (нов)» сохраняется.

Запуск:
  python scripts/autofill_single_station_equipment_group_names.py --dry-run
  python scripts/autofill_single_station_equipment_group_names.py --yes
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.equipment_group_set_services import (
    apply_auto_equipment_group_name,
    suggested_equipment_group_name,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Автозаполнение name групп оборудования: "
            "«станция (тип)» при одной привязанной станции."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать изменения, без записи в БД",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Применить без подтверждения",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Ограничить число обновляемых групп (0 = без лимита)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        groups = EquipmentGroup.query.order_by(EquipmentGroup.id.asc()).all()
        planned: list[tuple[EquipmentGroup, str, str]] = []
        skipped_multi = 0
        skipped_same = 0
        for group in groups:
            old_name = (group.name or "").strip()
            suggested = suggested_equipment_group_name(
                group.id, current_name=old_name
            )
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
            print(
                f"  id={group.id} numb={group.numb}: "
                f"{old_name!r} -> {suggested!r}"
            )
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
        for group, old_name, _suggested in planned:
            applied = apply_auto_equipment_group_name(group, force=True, old_name=old_name)
            if applied:
                updated += 1
        db.session.commit()
        print(f"Обновлено: {updated}")


if __name__ == "__main__":
    main()
