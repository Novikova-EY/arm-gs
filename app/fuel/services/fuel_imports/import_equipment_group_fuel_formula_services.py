#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Импорт формул топлива (EquipmentGroupFuelFormula) из Excel.

Ожидаемые столбцы: NAME, year, formtxt, numb1120, numb1, v.
Сопоставление группы: EquipmentGroup.numb == значению столбца numb1120 (как в импорте удельных показателей).
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy import cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.types import String

from app.common.services.database_version_filter import set_db_version_on_create
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.logs.services.logging_service import log_to_db
from app.refdata.models.years.year_model import Year


def _get_logger():
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            return current_app.logger
    except Exception:
        pass
    return logging.getLogger(__name__)


def _normalize_column_name(col) -> str:
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").strip().lower()
    s = s.replace("е", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


FORMULA_IMPORT_FIELDS = ["name", "year_number", "formtxt", "numb1120", "numb1", "variant_number"]

COLUMN_ALIASES = {
    "name": ["name", "NAME", "наименование", "toplname"],
    "year_number": ["year_number", "year", "Year", "YEAR", "год"],
    "formtxt": ["formtxt", "form_txt", "формула"],
    "numb1120": ["numb1120", "numb", "NUMB", "num1120", "номер1120", "NUMB1120", "ном1120"],
    "numb1": ["numb1", "numb_1"],
    "variant_number": ["v", "V", "variant", "variant_number", "вариант"],
}


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    alias_to_canonical = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in FORMULA_IMPORT_FIELDS:
        alias_to_canonical[_normalize_column_name(field)] = field

    rename_map = {}
    for col in df.columns:
        norm = _normalize_column_name(col)
        canonical = alias_to_canonical.get(norm)
        if canonical and canonical not in rename_map.values():
            rename_map[col] = canonical
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _extract_cell_value(row, field: str):
    val = row.get(field)
    if isinstance(val, pd.Series):
        for v in val:
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                if isinstance(v, str) and not v.strip():
                    continue
                return v
        return None
    return val


def _safe_int(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    try:
        f = float(s)
        if f.is_integer():
            return int(f)
    except (TypeError, ValueError):
        pass
    return None


def _safe_decimal_numb1(value) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        s = value.strip().replace("\u00a0", " ").replace("\xa0", " ")
        s = "".join(ch for ch in s if ch != " ")
        if not s or s.lower() in ("nan", "—", "-", "–"):
            return None
    try:
        if isinstance(value, Decimal):
            dec_val = value
        elif isinstance(value, (int, float)):
            dec_val = Decimal(str(value))
        else:
            dec_val = Decimal(str(value).strip().replace(",", "."))
        return dec_val
    except (InvalidOperation, ValueError, TypeError):
        return None


def _numb1_equal(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError, TypeError):
        return False


def _numb_for_match(value) -> str | None:
    n = _safe_int(value)
    if n is not None:
        return str(n)
    if value is not None and not (isinstance(value, float) and pd.isna(value)):
        s = str(value).strip()
        if s:
            return s
    return None


def import_equipment_group_fuel_formula_from_excel(file, user: str) -> dict:
    """
    Загружает строки в EquipmentGroupFuelFormula.
    По numb1120 ищутся все EquipmentGroup с таким EquipmentGroup.numb.
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)
    logger.info("[IMPORT_FUEL_FORMULA] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(df)

    if "numb1120" not in df.columns:
        raise ValueError(
            "В файле отсутствует столбец numb1120 (или NUMB). "
            "Ожидаются столбцы NAME, year, formtxt, numb1120, numb1, v."
        )
    if "year_number" not in df.columns:
        raise ValueError(
            "В файле отсутствует столбец year. "
            "Ожидаются столбцы NAME, year, formtxt, numb1120, numb1, v."
        )

    updated = 0
    created = 0
    skipped_no_match = 0
    skipped_no_year = 0
    skipped_bad_year = 0

    for _index, row in df.iterrows():
        if row.isnull().all():
            continue

        numb_str = _numb_for_match(_extract_cell_value(row, "numb1120"))
        if not numb_str:
            skipped_no_match += 1
            continue

        year_val = _safe_int(_extract_cell_value(row, "year_number"))
        if year_val is None:
            skipped_bad_year += 1
            continue

        variant_val = _safe_int(_extract_cell_value(row, "variant_number"))
        if variant_val is None:
            variant_val = 0

        name_raw = _extract_cell_value(row, "name")
        name_str = None if name_raw is None or (isinstance(name_raw, float) and pd.isna(name_raw)) else str(name_raw).strip()
        if name_str == "":
            name_str = None

        formtxt_raw = _extract_cell_value(row, "formtxt")
        if formtxt_raw is None or (isinstance(formtxt_raw, float) and pd.isna(formtxt_raw)):
            formtxt_str = None
        else:
            formtxt_str = str(formtxt_raw)

        numb1120_val = _safe_int(_extract_cell_value(row, "numb1120"))
        numb1_val = None
        if "numb1" in df.columns:
            numb1_val = _safe_decimal_numb1(_extract_cell_value(row, "numb1"))

        groups = (
            EquipmentGroup.query.filter(cast(EquipmentGroup.numb, String) == numb_str).all()
        )
        if not groups:
            skipped_no_match += 1
            continue

        for eg in groups:
            version_id = getattr(eg, "database_version_id", None)
            year_query = Year.query.filter_by(number=year_val)
            if version_id is not None:
                year_query = year_query.filter_by(database_version_id=version_id)
            else:
                year_query = year_query.filter(Year.database_version_id.is_(None))
            if year_query.first() is None:
                skipped_no_year += 1
                continue

            existing = (
                EquipmentGroupFuelFormula.query.filter_by(
                    equipment_group_id=eg.id,
                    year_number=year_val,
                    variant_number=variant_val,
                    database_version_id=version_id,
                ).first()
            )

            if existing is None:
                new_row = EquipmentGroupFuelFormula(
                    equipment_group_id=eg.id,
                    name=name_str,
                    year_number=year_val,
                    variant_number=variant_val,
                    numb1120=numb1120_val,
                    numb1=numb1_val,
                    formtxt=formtxt_str,
                    database_version_id=version_id,
                )
                set_db_version_on_create(new_row)
                db.session.add(new_row)
                db.session.flush()
                created += 1
            else:
                changed = False
                if existing.name != name_str:
                    existing.name = name_str
                    changed = True
                if existing.formtxt != formtxt_str:
                    existing.formtxt = formtxt_str
                    changed = True
                if existing.numb1120 != numb1120_val:
                    existing.numb1120 = numb1120_val
                    changed = True
                if not _numb1_equal(existing.numb1, numb1_val):
                    existing.numb1 = numb1_val
                    changed = True
                if changed:
                    updated += 1

    try:
        if updated or created:
            db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("[IMPORT_FUEL_FORMULA] db error: %s", exc)
        raise ValueError("Ошибка сохранения данных: проверьте корректность файла.") from exc

    elapsed = time.perf_counter() - t0
    message = (
        "Загрузка формул топлива завершена. "
        "Создано записей: {created}, обновлено: {updated}, "
        "пропущено (нет группы по numb1120): {skipped_no_match}, "
        "пропущено (нет года в версии): {skipped_no_year}, "
        "пропущено (некорректный year в строке): {skipped_bad_year}."
    ).format(
        created=created,
        updated=updated,
        skipped_no_match=skipped_no_match,
        skipped_no_year=skipped_no_year,
        skipped_bad_year=skipped_bad_year,
    )
    logger.info(
        "[IMPORT_FUEL_FORMULA] done created=%s updated=%s elapsed=%.2fs",
        created,
        updated,
        elapsed,
    )
    log_to_db(user, "Загрузка формул топлива из Excel", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
    }
