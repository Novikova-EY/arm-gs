# -*- coding: utf-8 -*-
"""Убрать float-шум из отчётных значений ГИС ТЭК в БД.

Числа в эти таблицы попадают из Excel/Access, где хранятся как double, поэтому в
БД оседает хвост вроде 105.1000000000000100 – его видно на страницах при выборе
«Не округлять». Скрипт округляет такие значения до 15 значащих цифр, как это
делают показ на страницах и импорт из Excel; значения короче предела не меняются.
Значения с целой частью длиннее 15 цифр не трогаются: округление до значащих
цифр исказило бы её (такие строки попадают в отчёт как пропущенные).

Справочные характеристики топлива (gs_eco_operating_tes_fuel_chars) в список не
входят: там длинный хвост – реальная точность double у расчётных констант.

По умолчанию выполняется dry-run с отчётом по колонкам; для записи – --apply.
В режиме --apply старые значения сохраняются в файл отката в backups/.

Примеры:
  python scripts/clean_float_noise_in_gis_tek_params.py
  python scripts/clean_float_noise_in_gis_tek_params.py --apply
  python scripts/clean_float_noise_in_gis_tek_params.py --table gs_eco_gis_tek_pollutant_params --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import Numeric

from app import create_app
from app.ecology.models.pg_param_calc_model import PGParamCalc
from app.ecology.models.pg_report_gis_tek_model import PGReportGisTek
from app.ecology.models.zv_report_gis_tek_model import ZVReportGisTek
from app.ecology.services.ecology_decimal_helpers import (
    SIGNIFICANT_DIGITS,
    drop_float_noise,
)
from app.extensions import db


TABLES = {
    PGReportGisTek.__tablename__: PGReportGisTek,
    ZVReportGisTek.__tablename__: ZVReportGisTek,
    PGParamCalc.__tablename__: PGParamCalc,
}

# Целая часть такой длины уже сопоставима с пределом значащих цифр: округление
# затронуло бы её, а не хвост.
INTEGER_LIMIT = Decimal(10) ** SIGNIFICANT_DIGITS

SAMPLES_PER_COLUMN = 3


def numeric_columns(model) -> list[str]:
    """Числовые колонки модели – только в них может осесть хвост double."""
    return [
        column.name
        for column in model.__table__.columns
        if isinstance(column.type, Numeric)
    ]


def cleaned_value(value: Decimal | None) -> Decimal | None:
    """Значение без хвоста float-шума; None, если менять нечего или нельзя."""
    if value is None or abs(value) >= INTEGER_LIMIT:
        return None
    cleaned = drop_float_noise(value)
    return cleaned if cleaned is not None and cleaned != value else None


def collect_updates(model, columns: list[str]) -> dict:
    """Строки с float-шумом и статистика по колонкам."""
    query = model.query.with_entities(
        model.id, *[getattr(model, name) for name in columns]
    )
    updates: list[tuple[int, dict[str, Decimal]]] = []
    counts = {name: 0 for name in columns}
    samples: dict[str, list[str]] = {name: [] for name in columns}
    skipped = 0

    for row in query.all():
        changed: dict[str, Decimal] = {}
        for index, name in enumerate(columns, start=1):
            value = row[index]
            cleaned = cleaned_value(value)
            if cleaned is None:
                if value is not None and abs(value) >= INTEGER_LIMIT:
                    skipped += 1
                continue
            changed[name] = cleaned
            counts[name] += 1
            if len(samples[name]) < SAMPLES_PER_COLUMN:
                samples[name].append(f"{value} → {cleaned.normalize()}")
        if changed:
            updates.append((row[0], changed))

    return {"updates": updates, "counts": counts, "samples": samples, "skipped": skipped}


def apply_updates(model, updates: list[tuple[int, dict[str, Decimal]]]) -> None:
    """UPDATE по первичному ключу: меняем только значения, состав строк не трогаем."""
    table = model.__table__
    for row_id, changed in updates:
        db.session.execute(table.update().where(table.c.id == row_id).values(**changed))
    db.session.commit()


def rollback_payload(model, updates: list[tuple[int, dict[str, Decimal]]]) -> dict:
    """Старые значения изменённых ячеек – чтобы правку можно было откатить."""
    payload: dict[str, dict[str, list]] = {}
    table = model.__table__
    for row_id, changed in updates:
        stored = db.session.execute(
            table.select().where(table.c.id == row_id)
        ).mappings().one()
        for name in changed:
            payload.setdefault(name, []).append([row_id, str(stored[name])])
    return payload


def write_rollback(backup_dir: str, kind: str, payload: dict) -> str:
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(backup_dir, f"float_noise_cleanup_{kind}_{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Округлить отчётные значения ГИС ТЭК до 15 значащих цифр (убрать float-шум)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Записать очищенные значения (по умолчанию выполняется dry-run)",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать план правок (режим по умолчанию)",
    )
    parser.add_argument(
        "--table",
        action="append",
        choices=sorted(TABLES),
        help="Обработать только указанную таблицу (можно повторять)",
    )
    args = parser.parse_args()

    tables = args.table or sorted(TABLES)
    app = create_app()
    with app.app_context():
        backup_dir = os.path.join(app.config.get("BACKUP_BASE_DIR", "backups"), "float_noise")
        print(f"host={os.getenv('DB_HOST', '?')} db={os.getenv('DB_NAME', '?')}")
        print(f"Режим: {'ЗАПИСЬ' if args.apply else 'dry-run'}")

        total_rows = 0
        total_values = 0
        for table_name in tables:
            model = TABLES[table_name]
            columns = numeric_columns(model)
            plan = collect_updates(model, columns)
            rows = len(plan["updates"])
            values = sum(plan["counts"].values())
            total_rows += rows
            total_values += values
            print(f"{table_name}: строк с шумом {rows}, значений {values}")
            for name in columns:
                if plan["counts"][name]:
                    print(
                        f"  {name}: {plan['counts'][name]} | "
                        + "; ".join(plan["samples"][name])
                    )
            if plan["skipped"]:
                print(f"  пропущено (целая часть ≥ {SIGNIFICANT_DIGITS} цифр): {plan['skipped']}")

            if args.apply and plan["updates"]:
                payload = rollback_payload(model, plan["updates"])
                path = write_rollback(backup_dir, table_name, payload)
                apply_updates(model, plan["updates"])
                print(f"  записано строк: {rows}; файл отката: {path}")

        print(f"Итого: строк {total_rows}, значений {total_values}")
        if not args.apply:
            print("Изменений не внесено. Для записи запустите скрипт с --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
