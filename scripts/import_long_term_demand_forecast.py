#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Загрузка исходного листа прогноза спроса в техническую таблицу gs_pd.

Пример (только разбор, без подключения к БД и изменений):
    python scripts/import_long_term_demand_forecast.py --file "C:/path/to/forecast.xlsx"

Пример записи в текущую БД проекта (если версия с префиксом «ГС» одна):
    python scripts/import_long_term_demand_forecast.py --file "C:/path/to/forecast.xlsx" --apply

Если таких версий несколько, выберите нужную по id:
    python scripts/import_long_term_demand_forecast.py --file "C:/path/to/forecast.xlsx" --apply --database-version-id 7


Данные сохраняются в gs_pd.gs_pd_long_term_forecast_source_rows в нормализованном
виде: одна строка на показатель/год, с отдельным признаком ГАЭС (with_gaes /
without_gaes / NULL). Признак «с/без НТ» из книги не выводится. Повторный запуск
того же файла в ту же версию не создаёт дубликаты. Другой файл сохраняется как
отдельный исходный снимок.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHEET_NAME = "ЭЭ и Р по ЭС до 2042"
HEADER_ROW = 5
FIRST_DATA_ROW = HEADER_ROW + 1
ENTITY_COLUMN = 2
INDICATOR_COLUMN = 3
UNIT_COLUMN = 4
TABLE_NAME = "gs_pd_long_term_forecast_source_rows"
TARGET_VERSION_PREFIX = "ГС"
SCRIPT_USER = "script:import_long_term_demand_forecast"
_YEAR_RE = re.compile(r"^\s*((?:19|20)\d{2})(?:\s*(?:г|[gG])\.?)?\s*$", re.IGNORECASE)
_GAES_WITH_RE = re.compile(r"\bс(?:\s+зарядом)?\s+гаэс\b", re.IGNORECASE)
_GAES_WITHOUT_RE = re.compile(r"\bбез(?:\s+заряда)?\s+гаэс\b", re.IGNORECASE)


def _year_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        year = int(value)
        return year if 1900 <= year <= 2100 else None
    match = _YEAR_RE.fullmatch(str(value).replace("\xa0", " ")) if value is not None else None
    return int(match.group(1)) if match else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).replace("\xa0", " ").strip()
    return result or None


def _gaes_variant(value: str | None, *, row_number: int) -> str | None:
    if not value:
        return None
    has_with = bool(_GAES_WITH_RE.search(value))
    has_without = bool(_GAES_WITHOUT_RE.search(value))
    if has_with and has_without:
        raise ValueError(
            f"Строка {row_number}: подпись одновременно указывает «с ГАЭС» и «без ГАЭС»: {value!r}."
        )
    if has_with:
        return "with_gaes"
    if has_without:
        return "without_gaes"
    return None


def _decimal(value: Any, *, row_number: int, year: int) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError(f"Строка {row_number}, {year}: вместо числа найдено логическое значение {value!r}.")
    if isinstance(value, str):
        raw = value.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
        if raw in {"-", "–", "–"}:
            return None
    else:
        raw = str(value)
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Строка {row_number}, {year}: значение {value!r} не является числом."
        ) from exc
    if not number.is_finite():
        raise ValueError(f"Строка {row_number}, {year}: недопустимое число {value!r}.")
    return number


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float) and not (float("-inf") < value < float("inf")):
        return str(value)
    return value


def parse_workbook(path: Path) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Разбирает поддерживаемую книгу, не устанавливая соединение с БД."""
    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден: {path}")
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Ожидается файл формата .xlsx.")

    raw_file = path.read_bytes()
    source_sha256 = hashlib.sha256(raw_file).hexdigest()
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if SHEET_NAME not in workbook.sheetnames:
            raise ValueError(
                f"В книге нет листа «{SHEET_NAME}». Найдены листы: {', '.join(workbook.sheetnames)}"
            )
        sheet = workbook[SHEET_NAME]
        header = next(
            sheet.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW, values_only=True),
            (),
        )
        year_columns = {
            column_number: year
            for column_number, value in enumerate(header, start=1)
            if (year := _year_number(value)) is not None
        }
        years = list(year_columns.values())
        if not years:
            raise ValueError(f"В строке {HEADER_ROW} не найдены годы.")
        if len(years) != len(set(years)):
            raise ValueError(f"В строке {HEADER_ROW} обнаружены повторяющиеся годы.")
        if years != sorted(years):
            raise ValueError(f"Годы в строке {HEADER_ROW} идут не по возрастанию.")

        header_context = {}
        for column_number in range(1, sheet.max_column + 1):
            if column_number in year_columns or column_number in {
                ENTITY_COLUMN,
                INDICATOR_COLUMN,
                UNIT_COLUMN,
            }:
                continue
            labels = [
                _text(sheet.cell(row=row_number, column=column_number).value)
                for row_number in (3, 4)
            ]
            label = " / ".join(item for item in labels if item)
            if label:
                header_context[column_number] = label

        records: list[dict[str, Any]] = []
        entities: set[str] = set()
        indicators: set[str] = set()
        rows_with_data = 0
        gaes_variant_counts = {"with_gaes": 0, "without_gaes": 0, "unspecified": 0}
        current_entity: str | None = None

        for row_number, row in enumerate(
            sheet.iter_rows(min_row=FIRST_DATA_ROW, values_only=True),
            start=FIRST_DATA_ROW,
        ):
            entity_raw = _text(row[ENTITY_COLUMN - 1] if len(row) >= ENTITY_COLUMN else None)
            indicator = _text(row[INDICATOR_COLUMN - 1] if len(row) >= INDICATOR_COLUMN else None)
            unit = _text(row[UNIT_COLUMN - 1] if len(row) >= UNIT_COLUMN else None)

            if entity_raw:
                current_entity = entity_raw
            year_values = {
                year: row[column_number - 1] if len(row) >= column_number else None
                for column_number, year in year_columns.items()
            }
            if not any(value is not None for value in year_values.values()):
                if not entity_raw and not indicator and not unit:
                    current_entity = None
                continue
            rows_with_data += 1
            if current_entity:
                entities.add(current_entity)
            if indicator:
                indicators.add(indicator)

            # Подпись показателя точнее унаследованного названия объекта: например,
            # строка может называться «Тверская область с ГАЭС», но показатель явно
            # указывать потребление «без ГАЭС».
            gaes_variant = _gaes_variant(indicator, row_number=row_number)
            if gaes_variant is None:
                gaes_variant = _gaes_variant(entity_raw or current_entity, row_number=row_number)

            extra_cells = {}
            for column_number, value in enumerate(row, start=1):
                if value is None or column_number in year_columns or column_number in {
                    ENTITY_COLUMN,
                    INDICATOR_COLUMN,
                    UNIT_COLUMN,
                }:
                    continue
                key = get_column_letter(column_number)
                if column_number in header_context:
                    key = f"{key} ({header_context[column_number]})"
                extra_cells[key] = _json_value(value)

            for column_number, year in year_columns.items():
                value = _decimal(
                    year_values[year], row_number=row_number, year=year
                )
                if value is None:
                    continue
                records.append(
                    {
                        "source_row": row_number,
                        "entity_name": current_entity,
                        "entity_name_raw": entity_raw,
                        "indicator": indicator,
                        "unit": unit,
                        "gaes_variant": gaes_variant,
                        "year_number": year,
                        "value": value,
                        "extra_cells": json.dumps(
                            extra_cells,
                            ensure_ascii=False,
                            allow_nan=False,
                            default=_json_value,
                        ),
                    }
                )
                gaes_variant_counts[gaes_variant or "unspecified"] += 1

        if not records:
            raise ValueError("На листе не найдено ни одного числового значения по годам.")
        stats = {
            "sheet": SHEET_NAME,
            "years": years,
            "rows_with_year_data": rows_with_data,
            "records": len(records),
            "entities": len(entities),
            "indicators": len(indicators),
            "gaes_variant_records": gaes_variant_counts,
        }
        return source_sha256, records, stats
    finally:
        workbook.close()


def _qualified_table(engine: Any) -> str:
    from config import SCHEMA_POWER_DEMAND

    preparer = engine.dialect.identifier_preparer
    return f"{preparer.quote_schema(SCHEMA_POWER_DEMAND)}.{preparer.quote(TABLE_NAME)}"


def _write_records(
    records: list[dict[str, Any]],
    *,
    path: Path,
    source_sha256: str,
    database_version_id: int | None,
) -> tuple[int, int, str]:
    from app import create_app
    from app.common.models.database_version_model import DatabaseVersion
    from app.extensions import db
    from config import SCHEMA_POWER_DEMAND

    app = create_app()
    with app.app_context():
        if database_version_id is None:
            versions = DatabaseVersion.query.order_by(DatabaseVersion.version_number).all()
            candidates = [
                item
                for item in versions
                if (item.version_number or "").strip().casefold().startswith(
                    TARGET_VERSION_PREFIX.casefold()
                )
            ]
            if not candidates:
                raise ValueError(
                    f"Не найдена версия БД, название которой начинается с «{TARGET_VERSION_PREFIX}»."
                )
            if len(candidates) > 1:
                choices = ", ".join(
                    f"{item.id}: {item.version_number}" for item in candidates
                )
                raise ValueError(
                    "Найдено несколько версий БД с префиксом «ГС»; "
                    f"укажите --database-version-id. Варианты: {choices}"
                )
            version = candidates[0]
        else:
            version = db.session.get(DatabaseVersion, database_version_id)
            if version is None:
                raise ValueError(f"Версия БД с id={database_version_id} не найдена.")
            if not (version.version_number or "").strip().casefold().startswith(
                TARGET_VERSION_PREFIX.casefold()
            ):
                raise ValueError(
                    f"Импорт разрешён только в версию БД, название которой начинается с "
                    f"«{TARGET_VERSION_PREFIX}». У версии id={database_version_id} "
                    f"название «{version.version_number}»."
                )

        table = _qualified_table(db.engine)
        preparer = db.engine.dialect.identifier_preparer
        quoted_schema = preparer.quote_schema(SCHEMA_POWER_DEMAND)
        quoted_table_name = preparer.quote(TABLE_NAME)
        quoted_table = f"{quoted_schema}.{quoted_table_name}"
        constraint_name = preparer.quote("uq_pd_long_term_forecast_source_version_hash_row_year")
        index_name = preparer.quote("ix_pd_long_term_forecast_source_version_year")
        variant_index_name = preparer.quote("ix_pd_long_term_forecast_source_variant_year")

        create_table = f"""
            CREATE TABLE IF NOT EXISTS {quoted_table} (
                id BIGSERIAL PRIMARY KEY,
                database_version_id INTEGER NOT NULL,
                source_sha256 CHAR(64) NOT NULL,
                source_file TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                entity_name TEXT,
                entity_name_raw TEXT,
                indicator TEXT,
                unit TEXT,
                gaes_variant VARCHAR(16),
                year_number INTEGER NOT NULL,
                value NUMERIC(30, 16) NOT NULL,
                extra_cells JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                imported_by TEXT NOT NULL,
                imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT {constraint_name} UNIQUE (
                    database_version_id, source_sha256, sheet_name, source_row, year_number
                )
            )
        """
        create_index = f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {quoted_table} (database_version_id, year_number)
        """
        create_variant_index = f"""
            CREATE INDEX IF NOT EXISTS {variant_index_name}
            ON {quoted_table} (database_version_id, gaes_variant, year_number)
        """
        insert = f"""
            INSERT INTO {table} AS target (
                database_version_id, source_sha256, source_file, sheet_name,
                source_row, entity_name, entity_name_raw, indicator, unit,
                gaes_variant, year_number, value, extra_cells, imported_by
            ) VALUES (
                :database_version_id, :source_sha256, :source_file, :sheet_name,
                :source_row, :entity_name, :entity_name_raw, :indicator, :unit,
                :gaes_variant, :year_number, :value, CAST(:extra_cells AS JSONB), :imported_by
            )
            ON CONFLICT (
                database_version_id, source_sha256, sheet_name, source_row, year_number
            ) DO UPDATE SET gaes_variant = EXCLUDED.gaes_variant
            WHERE target.gaes_variant IS DISTINCT FROM EXCLUDED.gaes_variant
        """

        from sqlalchemy import text

        inserted = 0
        try:
            with db.engine.begin() as connection:
                connection.execute(text(create_table))
                connection.execute(
                    text(f"ALTER TABLE {quoted_table} ADD COLUMN IF NOT EXISTS gaes_variant VARCHAR(16)")
                )
                connection.execute(text(create_index))
                connection.execute(text(create_variant_index))
                for start in range(0, len(records), 1000):
                    batch = []
                    for record in records[start : start + 1000]:
                        batch.append(
                            {
                                **record,
                                "database_version_id": database_version_id,
                                "source_sha256": source_sha256,
                                "source_file": path.name,
                                "sheet_name": SHEET_NAME,
                                "imported_by": SCRIPT_USER,
                            }
                        )
                    result = connection.execute(text(insert), batch)
                    inserted += result.rowcount or 0
        except Exception:
            db.session.rollback()
            raise
        return inserted, int(version.id), version.version_number


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path, help="Путь к исходному .xlsx")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать данные в PostgreSQL; без этого флага выполняется только проверка файла.",
    )
    parser.add_argument(
        "--database-version-id",
        type=int,
        help=(
            "id целевой версии БД (необязательно, только вместе с --apply). "
            "Разрешены только названия, начинающиеся с «ГС»; если id не указан, "
            "скрипт выберет единственную подходящую версию."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.apply and args.database_version_id is not None:
        raise ValueError("--database-version-id используется только вместе с --apply.")

    source_sha256, records, stats = parse_workbook(args.file)
    print(f"Файл: {args.file}")
    print(f"SHA-256: {source_sha256}")
    print(
        "Проверка пройдена: лист «{sheet}», годы {first}–{last}; "
        "строк с данными {rows}; записей показатель/год {records}; "
        "объектов {entities}; показателей {indicators}; "
        "варианты ГАЭС (строки/год): {gaes_variants}.".format(
            sheet=stats["sheet"],
            first=stats["years"][0],
            last=stats["years"][-1],
            rows=stats["rows_with_year_data"],
            records=stats["records"],
            entities=stats["entities"],
            indicators=stats["indicators"],
            gaes_variants=stats["gaes_variant_records"],
        )
    )
    if not args.apply:
        print(
            "Режим проверки: БД не изменялась. Для записи добавьте --apply; "
            f"импорт разрешён только в версию БД с названием, начинающимся с «{TARGET_VERSION_PREFIX}»."
        )
        return 0

    inserted, target_version_id, target_version_name = _write_records(
        records,
        path=args.file,
        source_sha256=source_sha256,
        database_version_id=args.database_version_id,
    )
    print(
        f"Записано новых строк: {inserted}; пропущено повторов: {len(records) - inserted}; "
        f"версия БД: {target_version_name} (id={target_version_id}); "
        f"таблица: gs_pd.{TABLE_NAME}."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Ошибка импорта: {exc}", file=sys.stderr)
        raise SystemExit(2)
