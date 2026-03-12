#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Удаление EquipmentGroup (gs_fue.gs_fue_equipment_groups), не имеющих связей в EquipmentGroupSet.

Находит группы без записей в gs_fue_equipment_group_sets, удаляет связанные
EquipmentGroupFuelParam и EquipmentGroupExtraFuelParam, затем сами группы.
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, select

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Удаление EquipmentGroup без связей в EquipmentGroupSet."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать, что будет сделано, без изменений",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Без подтверждения",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        eg_table = EquipmentGroup.__table__
        set_table = EquipmentGroupSet.__table__
        fuel_param_table = EquipmentGroupFuelParam.__table__
        extra_param_table = EquipmentGroupExtraFuelParam.__table__

        # ID групп, которые есть в EquipmentGroupSet
        linked_ids_subq = select(set_table.c.equipment_group_id).distinct()

        # EquipmentGroup без связей в EquipmentGroupSet
        orphan_stmt = select(eg_table.c.id).where(
            ~eg_table.c.id.in_(linked_ids_subq)
        )
        orphan_ids = [r[0] for r in db.session.execute(orphan_stmt).all()]

        if not orphan_ids:
            print("Групп EquipmentGroup без связей в EquipmentGroupSet не найдено.")
            return

        print("=" * 80)
        print("Удаление EquipmentGroup без связей в EquipmentGroupSet")
        print("=" * 80)
        print(f"Старт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Найдено групп для удаления: {len(orphan_ids)}")
        print(f"ID: {orphan_ids[:50]}{'...' if len(orphan_ids) > 50 else ''}")
        if args.dry_run:
            print("[DRY-RUN] Изменения не применяются")
        print()

        if not args.dry_run and not args.yes:
            confirm = input("Продолжить удаление? [y/N]: ")
            if confirm.lower() != "y":
                print("Отменено.")
                return

        total_fuel_deleted = 0
        total_extra_deleted = 0

        for eg_id in orphan_ids:
            if args.dry_run:
                fp_count = db.session.execute(
                    select(func.count()).select_from(fuel_param_table).where(
                        fuel_param_table.c.equipment_group_id == eg_id
                    )
                ).scalar() or 0
                ep_count = db.session.execute(
                    select(func.count()).select_from(extra_param_table).where(
                        extra_param_table.c.equipment_group_id == eg_id
                    )
                ).scalar() or 0
                print(f"  id={eg_id}: fuel_params={fp_count}, extra_params={ep_count}")
                continue

            # 1) Удаляем EquipmentGroupFuelParam
            res = db.session.execute(
                delete(fuel_param_table).where(
                    fuel_param_table.c.equipment_group_id == eg_id
                )
            )
            total_fuel_deleted += res.rowcount or 0

            # 2) Удаляем EquipmentGroupExtraFuelParam
            res = db.session.execute(
                delete(extra_param_table).where(
                    extra_param_table.c.equipment_group_id == eg_id
                )
            )
            total_extra_deleted += res.rowcount or 0

            # 3) Удаляем EquipmentGroup
            db.session.execute(delete(eg_table).where(eg_table.c.id == eg_id))

        if args.dry_run:
            print()
            print(f"[DRY-RUN] Будет удалено групп: {len(orphan_ids)}")
            return

        db.session.commit()
        print()
        print(f"Удалено групп EquipmentGroup: {len(orphan_ids)}")
        print(f"Удалено EquipmentGroupFuelParam: {total_fuel_deleted}")
        print(f"Удалено EquipmentGroupExtraFuelParam: {total_extra_deleted}")
        print(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
