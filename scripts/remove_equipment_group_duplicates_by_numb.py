#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Удаление дублей EquipmentGroup (gs_fue.gs_fue_equipment_groups) по (numb, database_version_id).

Для каждой группы дублей оставляет запись с минимальным id, переназначает ссылки
(EquipmentGroupSet, EquipmentGroupFuelParam, EquipmentGroupExtraFuelParam) на нее,
удаляет дубликаты.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, select, update

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam
from config import SCHEMA_FUEL


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Удаление дублей EquipmentGroup по (numb, database_version_id)."
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

        # Находим дубли по (numb, database_version_id), где numb не NULL
        dup_stmt = (
            select(
                eg_table.c.numb,
                eg_table.c.database_version_id,
                func.array_agg(eg_table.c.id).label("ids"),
            )
            .where(eg_table.c.numb.isnot(None))
            .group_by(eg_table.c.numb, eg_table.c.database_version_id)
            .having(func.count() > 1)
        )
        duplicates = db.session.execute(dup_stmt).all()

        if not duplicates:
            print("Дублей по (numb, database_version_id) не найдено.")
            return

        print("=" * 80)
        print("Удаление дублей EquipmentGroup по (numb, database_version_id)")
        print("=" * 80)
        print(f"Старт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Найдено групп дублей: {len(duplicates)}")
        if args.dry_run:
            print("[DRY-RUN] Изменения не применяются")
        print()

        total_to_delete = 0
        total_sets_updated = 0
        total_fuel_params_deleted = 0
        total_fuel_params_updated = 0
        total_extra_params_deleted = 0
        total_extra_params_updated = 0

        for numb, db_version_id, ids in duplicates:
            ids_list = list(ids)
            keep_id = min(ids_list)
            drop_ids = [i for i in ids_list if i != keep_id]
            total_to_delete += len(drop_ids)

            print(f"  numb={numb} db_version={db_version_id}: оставляем id={keep_id}, удаляем {drop_ids}")

            if args.dry_run:
                for dup_id in drop_ids:
                    sets_count = db.session.execute(
                        select(func.count()).select_from(set_table).where(
                            set_table.c.equipment_group_id == dup_id
                        )
                    ).scalar() or 0
                    fp_count = db.session.execute(
                        select(func.count()).select_from(fuel_param_table).where(
                            fuel_param_table.c.equipment_group_id == dup_id
                        )
                    ).scalar() or 0
                    ep_count = db.session.execute(
                        select(func.count()).select_from(extra_param_table).where(
                            extra_param_table.c.equipment_group_id == dup_id
                        )
                    ).scalar() or 0
                    print(f"    id={dup_id}: sets={sets_count}, fuel_params={fp_count}, extra_params={ep_count}")
                continue

            for dup_id in drop_ids:
                # 1) EquipmentGroupSet — переназначаем на keep_id
                res = db.session.execute(
                    update(set_table)
                    .where(set_table.c.equipment_group_id == dup_id)
                    .values(equipment_group_id=keep_id)
                )
                total_sets_updated += res.rowcount or 0

                # 2) EquipmentGroupFuelParam — конфликт по (equipment_group_id, year_number)
                #    Сначала удаляем записи дубликата, для которых у keep уже есть запись на тот же год
                fp_dup = db.session.execute(
                    select(fuel_param_table.c.id, fuel_param_table.c.year_number)
                    .where(fuel_param_table.c.equipment_group_id == dup_id)
                ).all()
                keep_years = {
                    row[0]
                    for row in db.session.execute(
                        select(fuel_param_table.c.year_number).where(
                            fuel_param_table.c.equipment_group_id == keep_id
                        )
                    ).all()
                }
                for fp_id, year in fp_dup:
                    if year in keep_years:
                        db.session.execute(delete(fuel_param_table).where(fuel_param_table.c.id == fp_id))
                        total_fuel_params_deleted += 1
                    else:
                        db.session.execute(
                            update(fuel_param_table)
                            .where(fuel_param_table.c.id == fp_id)
                            .values(equipment_group_id=keep_id)
                        )
                        total_fuel_params_updated += 1
                        keep_years.add(year)

                # 3) EquipmentGroupExtraFuelParam — аналогично
                ep_dup = db.session.execute(
                    select(extra_param_table.c.id, extra_param_table.c.year_number)
                    .where(extra_param_table.c.equipment_group_id == dup_id)
                ).all()
                keep_ep_years = {
                    row[0]
                    for row in db.session.execute(
                        select(extra_param_table.c.year_number).where(
                            extra_param_table.c.equipment_group_id == keep_id
                        )
                    ).all()
                }
                for ep_id, year in ep_dup:
                    if year in keep_ep_years:
                        db.session.execute(delete(extra_param_table).where(extra_param_table.c.id == ep_id))
                        total_extra_params_deleted += 1
                    else:
                        db.session.execute(
                            update(extra_param_table)
                            .where(extra_param_table.c.id == ep_id)
                            .values(equipment_group_id=keep_id)
                        )
                        total_extra_params_updated += 1
                        keep_ep_years.add(year)

                # 4) Удаляем EquipmentGroup-дубликат
                db.session.execute(delete(eg_table).where(eg_table.c.id == dup_id))

        if args.dry_run:
            print()
            print(f"[DRY-RUN] Будет удалено групп: {total_to_delete}")
            return

        db.session.commit()
        print()
        print(f"Удалено дублей EquipmentGroup: {total_to_delete}")
        print(f"Переназначено EquipmentGroupSet: {total_sets_updated}")
        print(f"EquipmentGroupFuelParam: обновлено {total_fuel_params_updated}, удалено конфликтов {total_fuel_params_deleted}")
        print(f"EquipmentGroupExtraFuelParam: обновлено {total_extra_params_updated}, удалено конфликтов {total_extra_params_deleted}")
        print(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
