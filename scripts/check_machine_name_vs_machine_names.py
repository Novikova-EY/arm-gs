#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт проверки Machine.machine_name на соответствие составному имени по модели MachineName.

Вычисляет правильное имя по той же логике, что machine_details / station_details:
- базовое: MachineName.name за год начала диапазона версии БД (текущий/факт), иначе за конец, иначе Machine.machine_name;
- при отличии в плановом периоде: "<текущ.> (<план>)".

Выводит расхождения и сводку.

Запуск:
  python scripts/check_machine_name_vs_machine_names.py           # только расхождения
  python scripts/check_machine_name_vs_machine_names.py --all     # все агрегаты
  python scripts/check_machine_name_vs_machine_names.py --csv    # вывод в CSV
"""

import argparse
import csv
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.services.station_services.station_services import _apply_machine_display_names


def check_machine_names(show_all: bool = False):
    """
    Сравнивает Machine.machine_name с вычисленным именем по MachineName.

    Returns:
        List[dict]: список записей {machine_id, station, machine_number, machine_name, display_name, match}
    """
    machines = Machine.query.options(
        db.joinedload(Machine.machine_station),
    ).all()

    _apply_machine_display_names(machines)

    results = []
    for m in machines:
        display_name = (getattr(m, "display_name", None) or "").strip()
        machine_name = (m.machine_name or "").strip()
        match = machine_name == display_name

        station_name = "—"
        if m.machine_station:
            station_name = m.machine_station.name or "—"

        if show_all or not match:
            results.append({
                "machine_id": m.id,
                "station": station_name,
                "machine_number": m.machine_number or "—",
                "machine_name": machine_name or "—",
                "display_name": display_name or "—",
                "match": match,
            })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Проверка Machine.machine_name vs составное имя по MachineName"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Показать все агрегаты, не только с расхождениями",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Вывод в формате CSV",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        results = check_machine_names(show_all=args.all)

        mismatches = [r for r in results if not r["match"]]
        total = len(results)
        total_machines = Machine.query.count()

        if args.csv:
            writer = csv.DictWriter(
                sys.stdout,
                fieldnames=["machine_id", "station", "machine_number", "machine_name", "display_name", "match"],
                extrasaction="ignore",
                lineterminator="\n",
            )
            writer.writeheader()
            for r in results:
                r["match"] = "да" if r["match"] else "нет"
                writer.writerow(r)
            return 0

        # Текстовый вывод
        if not results:
            print("Нет агрегатов для проверки.")
            return 0

        if mismatches:
            print(f"Расхождений: {len(mismatches)} из {total_machines} агрегатов\n")
            for r in mismatches:
                print(f"  Machine id={r['machine_id']} | {r['station']} | №{r['machine_number']}")
                print(f"    machine_name:   {r['machine_name'][:80]}{'...' if len(r['machine_name']) > 80 else ''}")
                print(f"    display_name:   {r['display_name'][:80]}{'...' if len(r['display_name']) > 80 else ''}")
                print()
        else:
            print("Расхождений не найдено. Machine.machine_name совпадает с вычисленным именем.")

        if args.all and results:
            ok_count = total - len(mismatches)
            print(f"\nСводка: проверено {total} агрегатов, совпадает {ok_count}, расхождений {len(mismatches)}.")

        return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
