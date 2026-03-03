# -*- coding: utf-8 -*-
"""
Удаление дубликатов в gs_fue_equipment_group_sets.

Дубликаты: несколько EquipmentGroupSet с одинаковыми (external_code, id_equipment_group,
database_version_id). Для каждой группы оставляем одну запись (предпочтительно с name в формате
"Станция (тип группы)"), остальные удаляем, перенося связи на оставляемую.
"""

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from config import SCHEMA_FUEL, SCHEMA_GENERATION


def _get_external_codes_for_set(seg: EquipmentGroupSet) -> set[str]:
    """Получить external_code всех станций, связанных с EquipmentGroupSet."""
    codes = set()
    for link in seg.station_links or []:
        st = Station.query.get(link.station_id)
        if st and st.external_code:
            codes.add(st.external_code)
    return codes


def main():
    parser = argparse.ArgumentParser(description="Удаление дубликатов в gs_fue_equipment_group_sets")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет сделано")
    parser.add_argument("--yes", action="store_true", help="Без подтверждения")
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("DEDUPLICATE: gs_fue_equipment_group_sets")
        print("=" * 70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if args.dry_run:
            print("[DRY-RUN] Изменения не применяются")
        print()

        all_sets = EquipmentGroupSet.query.all()
        # Группировка: (external_code, id_equipment_group, database_version_id) -> list[EquipmentGroupSet]
        groups: dict[tuple[str, int, int | None], list[EquipmentGroupSet]] = defaultdict(list)

        for seg in all_sets:
            codes = _get_external_codes_for_set(seg)
            if not codes:
                continue
            for ec in codes:
                key = (ec, seg.id_equipment_group, seg.database_version_id)
                groups[key].append(seg)

        # Оставляем уникальные по id
        dup_groups = {
            k: list({s.id: s for s in v}.values())
            for k, v in groups.items()
            if len({s.id for s in v}) > 1
        }

        if not dup_groups:
            print("Дубликатов не найдено.")
            return

        print(f"Найдено групп с дубликатами: {len(dup_groups)}")
        total_to_delete = 0
        for key, segs in dup_groups.items():
            ec, eg_id, ver = key
            total_to_delete += len(segs) - 1
            print(f"  ({ec[:20]}..., eg={eg_id}, ver={ver}): {len(segs)} записей -> оставим 1")
        print(f"Будет удалено записей: {total_to_delete}")
        print()

        if not args.yes and not args.dry_run:
            reply = input("Продолжить? [y/N]: ").strip().lower()
            if reply != "y":
                print("Отменено.")
                return

        if args.dry_run:
            print("[DRY-RUN] Завершено.")
            return

        deleted = 0
        machines_updated = 0

        # Для каждой группы — кто остаётся (keep)
        keep_per_group: dict[tuple, EquipmentGroupSet] = {}
        for key, segs in dup_groups.items():
            segs_sorted = sorted(
                segs,
                key=lambda s: (
                    0 if (s.name and "(" in s.name and ")" in s.name) else 1,
                    s.id,
                ),
            )
            keep_per_group[key] = segs_sorted[0]

        # 1. Перемещаем связи: для каждой группы переносим у dup только связи
        #    к станциям с ec группы; dup не удаляем сразу
        # Собираем id связей для удаления (избегаем двойного удаления)
        links_to_delete: set[int] = set()

        for key, segs in dup_groups.items():
            ec, eg_id, ver = key
            keep = keep_per_group[key]
            for dup in segs:
                if dup.id == keep.id:
                    continue
                for link in dup.station_links or []:
                    st = db.session.get(Station, link.station_id)
                    if not st or st.external_code != ec:
                        continue
                    links_to_delete.add(link.id)
                    exists = EquipmentGroupSetStation.query.filter(
                        EquipmentGroupSetStation.equipment_group_set_id == keep.id,
                        EquipmentGroupSetStation.station_id == link.station_id,
                    ).first()
                    if not exists:
                        new_link = EquipmentGroupSetStation(
                            equipment_group_set_id=keep.id,
                            station_id=link.station_id,
                            database_version_id=link.database_version_id,
                        )
                        db.session.add(new_link)

        db.session.flush()  # сначала вставляем новые связи
        if links_to_delete:
            db.session.execute(
                delete(EquipmentGroupSetStation).where(
                    EquipmentGroupSetStation.id.in_(links_to_delete)
                )
            )
        db.session.flush()

        # 2. Переносим Machine.equipment_group_set_id с пустых dup на keep
        for key, segs in dup_groups.items():
            keep = keep_per_group[key]
            for dup in segs:
                if dup.id == keep.id:
                    continue
                # dup мог потерять все связи — машинки переводим на keep
                machines = Machine.query.filter(
                    Machine.equipment_group_set_id == dup.id,
                ).all()
                for m in machines:
                    m.equipment_group_set_id = keep.id
                    db.session.add(m)
                    machines_updated += 1

        db.session.flush()

        # 3. Удаляем EquipmentGroupSet без связей (bulk delete, без ORM cascade)
        set_ids_to_check = set()
        for key, segs in dup_groups.items():
            keep = keep_per_group[key]
            for s in segs:
                if s.id != keep.id:
                    set_ids_to_check.add(s.id)

        # Sets с оставшимися связями — через Core, без autoflush
        stmt = (
            select(EquipmentGroupSetStation.equipment_group_set_id)
            .where(EquipmentGroupSetStation.equipment_group_set_id.in_(set_ids_to_check))
            .group_by(EquipmentGroupSetStation.equipment_group_set_id)
        )
        sets_with_links = {
            row[0] for row in db.session.execute(stmt).fetchall()
        }
        sets_to_delete = set_ids_to_check - sets_with_links

        if sets_to_delete:
            db.session.execute(
                delete(EquipmentGroupSet).where(EquipmentGroupSet.id.in_(sets_to_delete))
            )
            deleted = len(sets_to_delete)

        db.session.commit()
        print(f"Удалено EquipmentGroupSet: {deleted}")
        print(f"Обновлено Machine.equipment_group_set_id: {machines_updated}")
        print(f"Done: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
