#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Копирует годовые данные агрегатов из 2021 в 2018–2020 по всем версиям БД.

Обрабатываются все Machine с database_version_id, существующим в справочнике
DatabaseVersion. Если для конкретного агрегата и вида данных нет записи за 2021,
этот вид данных для агрегата пропускается.

По умолчанию запускается dry-run с rollback. Запись требует --apply.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SKIP_CACHE_WARMUP"] = "true"

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.tranzaction_services import _commit_with_retry
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.machine.machine_fuel_model import MachineFuel


SOURCE_YEAR = 2021
TARGET_YEARS = (2018, 2019, 2020)
MODEL_SPECS = (
    ("Мощности (Руст/Рогр/Ррасп)", MachinePower, ("p_ust", "p_ogr", "p_rasp")),
    ("Название агрегата", MachineName, ("name",)),
    ("Тип ТЭС", MachineTesType, ("id_tes_type",)),
    ("Тип топлива", MachineFuel, ("id_fuel",)),
)


def load_year_rows(model, version_ids: list[int], machine_keys: set[tuple[int, int]]):
    """Загружает строки целевых и исходного годов, индексируя по версии/машине/году."""
    if not machine_keys:
        return {}

    rows = (
        db.session.query(model)
        .filter(
            model.database_version_id.in_(version_ids),
            model.year_number.in_((*TARGET_YEARS, SOURCE_YEAR)),
        )
        .all()
    )
    indexed = {}
    for row in rows:
        machine_key = (row.database_version_id, row.id_machine)
        if machine_key not in machine_keys:
            continue

        key = (*machine_key, row.year_number)
        if key in indexed:
            raise RuntimeError(
                f"Найдены дубли {model.__name__}: версия={key[0]}, "
                f"агрегат id={key[1]}, год={key[2]}. Операция остановлена."
            )
        indexed[key] = row
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Копирует мощности, название, тип ТЭС и тип топлива за 2021 год "
            "в 2018–2020 для всех агрегатов во всех версиях БД."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Сохранить изменения в БД; без этого флага выполняется dry-run.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Не запрашивать подтверждение для --apply.",
    )
    args = parser.parse_args()

    if args.yes and not args.apply:
        parser.error("--yes используется только вместе с --apply.")

    app = create_app()
    with app.app_context():
        versions = (
            db.session.query(DatabaseVersion.id, DatabaseVersion.version_number)
            .order_by(DatabaseVersion.id)
            .all()
        )
        version_names = {version_id: number for version_id, number in versions}
        version_ids = list(version_names)
        if not version_ids:
            raise SystemExit("В БД не найдены версии DatabaseVersion.")

        machines = (
            db.session.query(Machine)
            .filter(Machine.database_version_id.in_(version_ids))
            .order_by(Machine.database_version_id, Machine.id)
            .all()
        )
        machines_by_version: dict[int, list[Machine]] = {
            version_id: [] for version_id in version_ids
        }
        for machine in machines:
            machines_by_version[machine.database_version_id].append(machine)

        machine_keys = {
            (machine.database_version_id, machine.id) for machine in machines
        }
        rows_by_model = {
            model: load_year_rows(model, version_ids, machine_keys)
            for _, model, _ in MODEL_SPECS
        }

        print("Копирование данных 2021 года в 2018–2020 для всех агрегатов")
        print(f"Версий БД: {len(version_ids)}")
        print(f"Агрегатов с database_version_id: {len(machines)}")
        print(
            "Режим: "
            + ("ЗАПИСЬ" if args.apply else "DRY-RUN – без сохранения в БД")
        )

        if args.apply and not args.yes:
            answer = input(
                f"Продолжить для {len(machines)} агрегатов во всех версиях? [y/N]: "
            )
            if answer.strip().lower() not in ("y", "yes", "д", "да"):
                print("Отменено.")
                db.session.rollback()
                return

        stats_by_version = {
            version_id: {
                "machines": len(machines_by_version[version_id]),
                "models": {label: Counter() for label, _, _ in MODEL_SPECS},
            }
            for version_id in version_ids
        }

        try:
            for machine in machines:
                version_id = machine.database_version_id
                for label, model, fields in MODEL_SPECS:
                    indexed = rows_by_model[model]
                    source = indexed.get((version_id, machine.id, SOURCE_YEAR))
                    counts = stats_by_version[version_id]["models"][label]

                    if source is None:
                        counts["no_source"] += 1
                        continue

                    values = {field: getattr(source, field) for field in fields}
                    for year in TARGET_YEARS:
                        key = (version_id, machine.id, year)
                        target = indexed.get(key)
                        if target is None:
                            target = model(
                                id_machine=machine.id,
                                database_version_id=version_id,
                                year_number=year,
                                **values,
                            )
                            db.session.add(target)
                            indexed[key] = target
                            counts["inserted"] += 1
                            continue

                        changed = False
                        for field, value in values.items():
                            if getattr(target, field) != value:
                                setattr(target, field, value)
                                changed = True
                        counts["updated" if changed else "unchanged"] += 1

            total = Counter()
            for version_id in version_ids:
                version_info = stats_by_version[version_id]
                print(
                    f"\nВерсия {version_names[version_id]} (id={version_id}); "
                    f"агрегатов: {version_info['machines']}"
                )
                for label, _, _ in MODEL_SPECS:
                    counts = version_info["models"][label]
                    total.update(counts)
                    print(
                        f"  {label}: добавлено={counts['inserted']}, "
                        f"обновлено={counts['updated']}, "
                        f"без изменений={counts['unchanged']}, "
                        f"нет источника за 2021={counts['no_source']}"
                    )

            print(
                "\nИтого: "
                f"добавлено={total['inserted']}, "
                f"обновлено={total['updated']}, "
                f"без изменений={total['unchanged']}, "
                f"пропусков без источника 2021={total['no_source']}"
            )

            if args.apply:
                _commit_with_retry()
                print("Изменения сохранены.")
            else:
                db.session.rollback()
                print("Dry-run завершён: все изменения отменены.")

        except Exception:
            db.session.rollback()
            raise


if __name__ == "__main__":
    main()
