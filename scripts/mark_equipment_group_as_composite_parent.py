#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Помечает группу оборудования родителем составной станции (comp=1, main пусто).

Когда нужно: на /fuel/stations_equipment_groups у станции две строки одной группы –
безверсионная оболочка (comp=1, legacy) и группа текущей версии (main = numb родителя).
Тогда обе подсвечиваются как дубль numb, а строка «станция» и полоска кластера
рисуются по оболочке, карточка которой может не открываться.

Изменение выполняется тем же сервисом, что и карточка группы
(update_equipment_group_from_form), поэтому проверки comp/main штатные:
у родителя main должен быть пустым.

Запуск из корня репозитория (БД берётся из переменных окружения, как у приложения):

  python scripts/mark_equipment_group_as_composite_parent.py --group-id 30555
  python scripts/mark_equipment_group_as_composite_parent.py --group-id 30555 --apply --yes

Опции:
  --group-id ID  id группы оборудования (можно указывать несколько раз)
  --apply        записать изменения и commit (без флага – только план)
  --yes          с --apply: не спрашивать подтверждение в консоли
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.composite_station_semantics import (
    is_composite_parent_group,
    is_main_empty,
)
from app.fuel.services.equipment_groups.equipment_group_edit_services import (
    update_equipment_group_from_form,
)


def _version_label(version_id) -> str:
    return "– (без версии)" if version_id is None else str(version_id)


def _children_of(group) -> list[EquipmentGroup]:
    """Группы той же версии, входящие в составную станцию группы (main = numb)."""
    if group.numb in (None, 0):
        return []
    q = EquipmentGroup.query.filter(EquipmentGroup.main == group.numb)
    if group.database_version_id is None:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))
    else:
        q = q.filter(EquipmentGroup.database_version_id == group.database_version_id)
    return q.order_by(EquipmentGroup.id).all()


def process_group(group_id: int, apply_changes: bool) -> dict[str, int]:
    stats = {"changed": 0, "skipped": 0, "not_found": 0, "failed": 0}

    group = db.session.get(EquipmentGroup, group_id)
    if group is None:
        print(f"--- группа id={group_id}: не найдена")
        stats["not_found"] += 1
        return stats

    print(f"--- группа id={group.id} «{group.name or group.name_ext or '–'}»")
    print(f"    версия БД: {_version_label(group.database_version_id)}")
    print(
        f"    numb: {group.numb if group.numb is not None else '–'}, "
        f"comp: {group.comp if group.comp is not None else '–'}, "
        f"main: {group.main if group.main is not None else '–'}"
    )

    children = _children_of(group)
    print(f"    группы со main={group.numb}: {len(children)}")
    for child in children:
        print(f"      id={child.id} numb={child.numb} «{child.name or child.name_ext or '–'}»")

    if is_composite_parent_group(group):
        print("    уже родитель составной станции (comp=1, main пусто) – изменений не требуется")
        stats["skipped"] += 1
        return stats

    if not apply_changes:
        print("    будет изменено: comp=1, main пусто (плюс main=0 → пусто)")
        stats["changed"] += 1
        return stats

    success, message, change_details, target_id = update_equipment_group_from_form(
        group.id,
        {"name": group.name or "", "comp": "1", "main": ""},
    )
    if not success:
        print(f"    ошибка: {message}")
        stats["failed"] += 1
        return stats

    db.session.expire_all()
    updated = db.session.get(EquipmentGroup, target_id or group.id)
    print(f"    {message}")
    for label, old_value, new_value in change_details:
        print(f"      {label}: {old_value} → {new_value}")
    print(
        f"    стало: comp={updated.comp if updated.comp is not None else '–'}, "
        f"main={updated.main if updated.main is not None else '–'}, "
        f"родитель составной станции: {'да' if is_composite_parent_group(updated) else 'нет'}"
    )
    if is_main_empty(updated.main) and updated.comp == 1:
        stats["changed"] += 1
    else:
        stats["failed"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Пометить группы оборудования родителями составных станций "
            "(comp=1, main пусто) через штатный сервис карточки группы."
        )
    )
    parser.add_argument(
        "--group-id",
        type=int,
        action="append",
        required=True,
        help="id группы оборудования (можно несколько раз).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать изменения и commit (без флага – только план).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="С --apply: не спрашивать подтверждение в консоли.",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)

    app = create_app()
    with app.app_context():
        print(f"Режим: {'APPLY' if apply_changes else 'DRY-RUN'}")
        print(f"БД: {os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
              f"/{os.getenv('DB_NAME', '')}")
        print()

        if apply_changes and not args.yes:
            answer = input("Применить изменения comp/main? [y/N]: ").strip().lower()
            if answer not in ("y", "yes", "д", "да"):
                print("Отменено.")
                sys.exit(0)

        totals = {"changed": 0, "skipped": 0, "not_found": 0, "failed": 0}
        for group_id in args.group_id:
            stats = process_group(group_id, apply_changes)
            for key in totals:
                totals[key] += stats[key]
            print()

        print("=== Итого ===")
        print(f"  {('изменено' if apply_changes else 'к изменению')}: {totals['changed']}")
        print(f"  уже родители: {totals['skipped']}")
        print(f"  не найдено: {totals['not_found']}")
        if totals["failed"]:
            print(f"  ошибок: {totals['failed']}")
        if not apply_changes:
            print("  (план без записи; для записи запустите с --apply)")


if __name__ == "__main__":
    main()
