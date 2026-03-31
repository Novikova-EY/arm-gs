#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сервис загрузки коэффициента экономии от теплофикации (consumption.k) из Excel.
Связь по столбцу NUMB = EquipmentGroup.numb. Используются только столбцы NUMB и k.

Сервис загрузки расчётных значений удельных показателей (y, btp, sntp, bk, snk) из Excel
в EquipmentGroupSpecificFuelConsumption. Связь по numb1120 = EquipmentGroup.numb."""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd
from sqlalchemy import cast
from sqlalchemy.types import String
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.refdata.models.years.year_model import Year


def _get_logger():
    try:
        from flask import has_app_context, current_app
        if has_app_context():
            return current_app.logger
    except Exception:
        pass
    return logging.getLogger(__name__)


def _normalize_column_name(col) -> str:
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").strip().lower()
    s = s.replace("ё", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


# Столбцы для загрузки: NUMB и k (NAME, numb1 игнорируются)
K_IMPORT_FIELDS = ["numb", "k"]

COLUMN_ALIASES = {
    "numb": ["numb", "NUMB", "numb1120", "num1120", "номер1120", "NUMB1120", "ном1120"],
    "k": ["k", "K", "коэффициент", "koeff"],
}


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    alias_to_canonical = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in K_IMPORT_FIELDS:
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
    except (ValueError, InvalidOperation):
        pass
    return None


def _safe_decimal(value, max_digits: int = 6) -> Decimal | None:
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
        elif isinstance(value, str):
            dec_val = Decimal(value.strip().replace(",", "."))
        else:
            dec_val = Decimal(str(value))

        if isinstance(value, str):
            s = value.strip().replace(",", ".")
            if "." in s:
                frac = s.split(".", 1)[1].rstrip("0")
                scale = len(frac)
            else:
                scale = 0
            scale = min(scale, max_digits)
        else:
            raw_scale = -dec_val.as_tuple().exponent if dec_val.as_tuple().exponent < 0 else 0
            scale = min(raw_scale, max_digits)

        if scale <= 0:
            return dec_val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        quant = Decimal("1." + "0" * scale)
        return dec_val.quantize(quant, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _numb_for_match(value) -> str | None:
    """Нормализует NUMB для сопоставления с EquipmentGroup.numb (строка)."""
    n = _safe_int(value)
    if n is not None:
        return str(n)
    if value is not None and not (isinstance(value, float) and pd.isna(value)):
        s = str(value).strip()
        if s:
            return s
    return None


def import_equipment_group_specific_fuel_consumption_from_excel(
    file, user: str, year: int | None = None
) -> dict:
    """
    Загружает коэффициент экономии от теплофикации (k) из Excel в EquipmentGroupSpecificFuelConsumption.
    K привязан к году: записывается в consumption.k для (equipment_group_id, year_number).
    Формат: таблица со столбцами NAME, k, NUMB, numb1. Используются NUMB и k.
    По NUMB ищем EquipmentGroup.numb, создаём/обновляем consumption для года year.
    :param year: обязателен — год, для которого импортируются значения K.
    """
    if year is None:
        raise ValueError("Год обязателен для импорта коэффициента K. Укажите год в фильтре.")
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_K] start user=%s filename=%s year=%s",
        user, filename, year,
    )

    if Year.query.filter_by(number=year).first() is None:
        raise ValueError(
            f"Год {year} не найден в справочнике gs_years. "
            "Добавьте год в справочник или выберите другой год."
        )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(df)

    if "numb" not in df.columns:
        raise ValueError(
            "В файле отсутствует столбец NUMB. "
            "Ожидаются столбцы NAME, k, NUMB, numb1."
        )
    if "k" not in df.columns:
        raise ValueError(
            "В файле отсутствует столбец k. "
            "Ожидаются столбцы NAME, k, NUMB, numb1."
        )

    from app.common.services.database_version_filter import set_db_version_on_create

    updated = 0
    created = 0
    skipped_no_match = 0
    skipped_no_k = 0
    skipped_no_year = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        numb_str = _numb_for_match(_extract_cell_value(row, "numb"))
        if not numb_str:
            skipped_no_match += 1
            continue

        k_val = _safe_decimal(_extract_cell_value(row, "k"))
        if k_val is None:
            skipped_no_k += 1
            continue

        groups = (
            EquipmentGroup.query
            .filter(cast(EquipmentGroup.numb, String) == numb_str)
            .all()
        )
        if not groups:
            skipped_no_match += 1
            continue

        for eg in groups:
            version_id = getattr(eg, "database_version_id", None)
            year_query = Year.query.filter_by(number=year)
            if version_id is not None:
                year_query = year_query.filter_by(database_version_id=version_id)
            else:
                year_query = year_query.filter(Year.database_version_id.is_(None))
            if year_query.first() is None:
                skipped_no_year += 1
                continue

            consumption = EquipmentGroupSpecificFuelConsumption.query.filter_by(
                equipment_group_id=eg.id,
                year_number=year,
                database_version_id=version_id,
            ).first()
            if consumption is None:
                consumption = EquipmentGroupSpecificFuelConsumption(
                    equipment_group_id=eg.id,
                    year_number=year,
                    database_version_id=version_id,
                    k=k_val,
                )
                set_db_version_on_create(consumption)
                db.session.add(consumption)
                db.session.flush()
                created += 1
            elif consumption.k != k_val:
                consumption.k = k_val
                updated += 1

    try:
        if updated or created:
            db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("[IMPORT_EQUIPMENT_GROUP_K] db error: %s", exc)
        raise ValueError("Ошибка сохранения данных: проверьте корректность файла.") from exc

    elapsed = time.perf_counter() - t0
    message = (
        "Загрузка коэффициента экономии от теплофикации завершена (год {year}). "
        "Создано записей: {created}, обновлено: {updated}, "
        "пропущено (нет совпадения по NUMB): {skipped_no_match}, "
        "пропущено (нет значения k): {skipped_no_k}, "
        "пропущено (нет года в версии): {skipped_no_year}."
    ).format(
        year=year,
        created=created,
        updated=updated,
        skipped_no_match=skipped_no_match,
        skipped_no_k=skipped_no_k,
        skipped_no_year=skipped_no_year,
    )
    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_K] done year=%s created=%s updated=%s skipped=%s elapsed=%.2fs",
        year, created, updated, skipped_no_match + skipped_no_k + skipped_no_year, elapsed,
    )
    log_to_db(user, "Загрузка коэффициента экономии от теплофикации", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped": skipped_no_match,
        "skipped_no_year": skipped_no_year,
    }


# --- Загрузка расчётных значений удельных показателей (y, btp, sntp, bk, snk) ---

CALC_IMPORT_FIELDS = ["numb1120", "name", "year_number", "k", "y", "btp", "sntp", "bk", "snk"]

CALC_COLUMN_ALIASES = {
    "numb1120": ["numb1120", "numb", "NUMB", "num1120", "номер1120", "NUMB1120", "ном1120"],
    "name": ["name", "NAME", "наименование"],
    "year_number": ["year_number", "year", "Year", "YEAR", "год"],
    "k": ["k", "K", "коэффициент", "koeff"],
    "y": ["y", "Y", "удельная выработка"],
    "btp": ["btp", "BTP", "удельный расход теплофик"],
    "sntp": ["sntp", "SNTP", "собственные нужды теплофик"],
    "bk": ["bk", "BK", "удельный расход конд"],
    "snk": ["snk", "SNK", "собственные нужды"],
}


def _apply_calc_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    alias_to_canonical = {}
    for canonical, aliases in CALC_COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in CALC_IMPORT_FIELDS:
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


def _numb1120_for_match(value) -> str | None:
    """Нормализует numb1120 для сопоставления с EquipmentGroup.numb (строка)."""
    n = _safe_int(value)
    if n is not None:
        return str(n)
    if value is not None and not (isinstance(value, float) and pd.isna(value)):
        s = str(value).strip()
        if s:
            return s
    return None


def _resolve_equipment_groups_for_calc(row):
    """
    Возвращает список (equipment_group_id, database_version_id) для строки.
    Сопоставление по numb1120 = EquipmentGroup.numb (все версии БД).
    """
    numb1120_str = _numb1120_for_match(_extract_cell_value(row, "numb1120"))
    if not numb1120_str:
        return []

    groups = (
        EquipmentGroup.query
        .filter(cast(EquipmentGroup.numb, String) == numb1120_str)
        .all()
    )
    return [(g.id, g.database_version_id) for g in groups]


def import_equipment_group_specific_fuel_consumption_calculated_from_excel(
    file, user: str, year: int | None = None
) -> dict:
    """
    Загружает расчётные значения удельных показателей (name, year_number, y, btp, sntp, bk, snk)
    из Excel в EquipmentGroupSpecificFuelConsumption.
    Связь по столбцу numb1120 = EquipmentGroup.numb.
    Ожидаемые столбцы: NUMB1120, NAME, Year, Y, BTP, SNTP, BK, SNK.
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_SPECIFIC_FUEL_CALC] start user=%s filename=%s",
        user, filename,
    )

    from app.common.services.get_services.years.years_get_services import get_filter_start_year

    default_year = year if year is not None else get_filter_start_year()

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_calc_column_aliases(df)

    if "numb1120" not in df.columns:
        raise ValueError(
            "В файле отсутствует столбец NUMB1120. "
            "Ожидаются столбцы: NUMB1120, NAME, Year, K (опц.), Y, BTP, SNTP, BK, SNK."
        )

    created = 0
    updated = 0
    skipped_no_match = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        equipment_groups = _resolve_equipment_groups_for_calc(row)
        if not equipment_groups:
            skipped_no_match += 1
            continue

        row_year = _safe_int(_extract_cell_value(row, "year_number")) or default_year
        name_val = _extract_cell_value(row, "name")
        if name_val is None or (isinstance(name_val, float) and pd.isna(name_val)):
            name_str = None
        else:
            name_str = str(name_val).strip()[:512] or None

        k_val = _safe_decimal(_extract_cell_value(row, "k"))

        y_val = _safe_decimal(_extract_cell_value(row, "y"))
        btp_val = _safe_decimal(_extract_cell_value(row, "btp"))
        sntp_val = _safe_decimal(_extract_cell_value(row, "sntp"))
        bk_val = _safe_decimal(_extract_cell_value(row, "bk"))
        snk_val = _safe_decimal(_extract_cell_value(row, "snk"))

        if k_val is None and y_val is None and btp_val is None and sntp_val is None and bk_val is None and snk_val is None:
            continue

        numb1120_val = _safe_int(_extract_cell_value(row, "numb1120"))

        for equipment_group_id, eg_database_version_id in equipment_groups:
            param = EquipmentGroupSpecificFuelConsumption.query.filter_by(
                equipment_group_id=equipment_group_id,
                year_number=row_year,
            ).first()

            if param is None:
                param = EquipmentGroupSpecificFuelConsumption(
                    equipment_group_id=equipment_group_id,
                    year_number=row_year,
                    database_version_id=eg_database_version_id,
                    numb1120=numb1120_val,
                    name=name_str,
                    k=k_val,
                    y=y_val,
                    btp=btp_val,
                    sntp=sntp_val,
                    bk=bk_val,
                    snk=snk_val,
                )
                db.session.add(param)
                db.session.flush()
                created += 1
            else:
                changed = False
                if name_str is not None and param.name != name_str:
                    param.name = name_str
                    changed = True
                if k_val is not None and param.k != k_val:
                    param.k = k_val
                    changed = True
                if y_val is not None and param.y != y_val:
                    param.y = y_val
                    changed = True
                if btp_val is not None and param.btp != btp_val:
                    param.btp = btp_val
                    changed = True
                if sntp_val is not None and param.sntp != sntp_val:
                    param.sntp = sntp_val
                    changed = True
                if bk_val is not None and param.bk != bk_val:
                    param.bk = bk_val
                    changed = True
                if snk_val is not None and param.snk != snk_val:
                    param.snk = snk_val
                    changed = True
                if numb1120_val is not None and param.numb1120 != numb1120_val:
                    param.numb1120 = numb1120_val
                    changed = True

                if changed:
                    updated += 1

    try:
        if created or updated:
            db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("[IMPORT_EQUIPMENT_GROUP_SPECIFIC_FUEL_CALC] db error: %s", exc)
        raise ValueError("Ошибка сохранения данных: проверьте корректность файла.") from exc

    elapsed = time.perf_counter() - t0
    message = (
        "Загрузка расчётных значений удельных показателей завершена. "
        "Создано: {created}, обновлено: {updated}, "
        "пропущено (нет совпадения по NUMB1120): {skipped_no_match}."
    ).format(
        created=created,
        updated=updated,
        skipped_no_match=skipped_no_match,
    )
    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_SPECIFIC_FUEL_CALC] done created=%s updated=%s skipped=%s elapsed=%.2fs",
        created, updated, skipped_no_match, elapsed,
    )
    log_to_db(user, "Загрузка расчётных значений удельных показателей", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped": skipped_no_match,
    }
