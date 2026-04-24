#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт синхронизации Machine.machine_name с отображаемым именем на странице machine_details.

Для каждого агрегата вычисляет имя по логике machine_details:
- базовое: MachineName.name за год версии БД, иначе Machine.machine_name;
- при отличии в плановом периоде: "<текущ.> (<план>)".

Если вычисленное имя не совпадает с Machine.machine_name — заменяет Machine.machine_name.

Запуск:
  python scripts/sync_machine_name_with_display_name.py           # выполнить замены
  python scripts/sync_machine_name_with_display_name.py --dry-run # только показать расхождения
"""

import argparse
import sys
import os
from typing import List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.services.station_services.station_services import _apply_machine_display_names


def sync_machine_names(dry_run: bool = False) -> Tuple[int, List[dict]]:
    """
    Синхронизирует Machine.machine_name с отображаемым именем (логика machine_details).

    Returns:
        (количество обновленных, список изменений для вывода)
    """
    machines = Machine.query.options(
        db.joinedload(Machine.machine_station),
    ).all()

    _apply_machine_display_names(machines)

    updated_count = 0
    changes = []

    for m in machines:
        display_name = getattr(m, "display_name", None) or ""
        current_name = (m.machine_name or "").strip()
        display_name = (display_name or "").strip()

        if not display_name:
            continue

        if display_name != current_name:
            station_name = "—"
            if m.machine_station:
                station_name = m.machine_station.name or "—"

            changes.append({
                "machine_id": m.id,
                "station": station_name,
                "machine_number": m.machine_number or "—",
                "old": current_name or "—",
                "new": display_name,
            })

            if not dry_run:
                m.machine_name = display_name
                updated_count += 1

    if not dry_run and updated_count > 0:
        db.session.commit()

    return updated_count, changes


def main():
    parser = argparse.ArgumentParser(
        description="Синхронизация Machine.machine_name с отображаемым именем (machine_details)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать расхождения, не сохранять изменения",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print("Проверка Machine.machine_name vs отображаемое имя (machine_details)...")
        updated_count, changes = sync_machine_names(dry_run=args.dry_run)

        if not changes:
            print("Расхождений не найдено.")
            return 0

        print(f"\nНайдено расхождений: {len(changes)}")
        for c in changes:
            print(f"  Machine id={c['machine_id']} | {c['station']} | №{c['machine_number']}")
            print(f"    было:  {c['old'][:80]}{'...' if len(c['old']) > 80 else ''}")
            print(f"    станет: {c['new'][:80]}{'...' if len(c['new']) > 80 else ''}")

        if args.dry_run:
            print(f"\n[--dry-run] Изменения не применены. Запустите без --dry-run для сохранения.")
        else:
            print(f"\nОбновлено записей: {updated_count}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
