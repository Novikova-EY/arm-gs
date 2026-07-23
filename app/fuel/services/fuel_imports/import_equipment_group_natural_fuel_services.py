#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сервис загрузки EquipmentGroupNaturalFuel из Excel (Натура99).
Связь по столбцу NUMB1120 = EquipmentGroup.numb."""

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
from app.fuel.models.fue_equipment_group_natural_fuel_model import (
    EquipmentGroupNaturalFuel,
)
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
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
    s = s.replace("е", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


NATURAL_FUEL_FIELDS = [
    "name", "year_number",
    "gaz", "gazpp", "gaz_prir", "isk_gaz", "domen_g", "koks_g", "prochgaz",
    "mazut", "disel", "maztop", "gtt", "nft_proch", "torf", "gtd", "slan",
    "proch", "tvproch", "szh_gaz", "inoe", "ugol", "don", "podm", "vork",
    "intin", "pech", "arkt", "kuzn", "kuzngd", "kuznt", "kuznss", "kuznun",
    "ural", "sver", "chel", "kizel", "bashk", "kazah", "ekib", "maikub",
    "karag", "karajyra", "teniz", "kan", "nazar", "ibor", "berez", "per",
    "irbei", "kansk", "irkut", "azey", "mug", "cher", "tung", "jer", "karab",
    "hak", "tuv", "bur", "gusin", "tugn", "okino", "chit", "har", "urt",
    "tataur", "tarbag", "zab_kam", "yakut", "neru", "zyryan", "pyak", "amur",
    "rai", "erk", "ogodj", "svo", "urg", "ushum", "prim", "bikin", "razdol",
    "hankai", "mag", "chukot", "bering", "anad", "kamch", "sah",
    "obl", "dep", "oes", "er", "numb1120", "numb1",
]

INTEGER_FIELDS = frozenset(["year_number", "numb1120", "numb1", "obl", "dep", "oes", "er"])

STRING_FIELDS = frozenset(["name"])

NUMERIC_FIELDS = frozenset([
    "gaz", "gazpp", "gaz_prir", "isk_gaz", "domen_g", "koks_g", "prochgaz",
    "mazut", "disel", "maztop", "gtt", "nft_proch", "torf", "gtd", "slan",
    "proch", "tvproch", "szh_gaz", "inoe", "ugol", "don", "podm", "vork",
    "intin", "pech", "arkt", "kuzn", "kuzngd", "kuznt", "kuznss", "kuznun",
    "ural", "sver", "chel", "kizel", "bashk", "kazah", "ekib", "maikub",
    "karag", "karajyra", "teniz", "kan", "nazar", "ibor", "berez", "per",
    "irbei", "kansk", "irkut", "azey", "mug", "cher", "tung", "jer", "karab",
    "hak", "tuv", "bur", "gusin", "tugn", "okino", "chit", "har", "urt",
    "tataur", "tarbag", "zab_kam", "yakut", "neru", "zyryan", "pyak", "amur",
    "rai", "erk", "ogodj", "svo", "urg", "ushum", "prim", "bikin", "razdol",
    "hankai", "mag", "chukot", "bering", "anad", "kamch", "sah",
])

COLUMN_ALIASES = {
    "name": ["name", "NAME", "наименование"],
    "year_number": ["year_number", "year", "Year", "YEAR", "год"],
    "numb1120": ["numb1120", "num1120", "номер1120", "numb", "NUMB1120", "ном1120"],
    "numb1": ["numb1", "NUMB1", "numb_1"],
}


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    alias_to_canonical = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in NATURAL_FUEL_FIELDS:
        alias_to_canonical[_normalize_column_name(field)] = field

    rename_map = {}
    for col in df.columns:
        norm = _normalize_column_name(col)
        canonical = alias_to_canonical.get(norm) or (
            norm if norm in NATURAL_FUEL_FIELDS else None
        )
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


def _safe_str(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    return s if s else None


def _numb1120_for_match(value) -> str | None:
    n = _safe_int(value)
    if n is not None:
        return str(n)
    return _safe_str(value)


def _resolve_equipment_groups_from_row(row):
    numb1120_str = _numb1120_for_match(_extract_cell_value(row, "numb1120"))
    if not numb1120_str:
        return []

    groups = (
        EquipmentGroup.query
        .filter(cast(EquipmentGroup.numb, String) == numb1120_str)
        .all()
    )
    return [(g.id, g.database_version_id) for g in groups]


def import_equipment_group_natural_fuel_from_excel(
    file,
    user: str,
    year: int | None = None,
) -> dict:
    """
    Загружает данные из Excel (Натура99) в EquipmentGroupNaturalFuel.
    Связь по numb1120 = EquipmentGroup.numb.
    Для каждой строки используется YEAR из Excel.
    Строки без YEAR пропускаются.
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_NATURAL_FUEL] start user=%s filename=%s page_year=%s",
        user, filename, year,
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(df)

    created = 0
    updated = 0
    skipped_no_match = 0
    skipped_no_year = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        equipment_groups = _resolve_equipment_groups_from_row(row)
        if not equipment_groups:
            skipped_no_match += 1
            continue

        row_values = {}
        for field in NATURAL_FUEL_FIELDS:
            if field not in df.columns:
                continue
            raw = _extract_cell_value(row, field)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                continue
            if field in INTEGER_FIELDS:
                val = _safe_int(raw)
            elif field in NUMERIC_FIELDS:
                val = _safe_decimal(raw)
            elif field in STRING_FIELDS:
                val = str(raw).strip() if raw else None
                if val and len(val) > 512 and field == "name":
                    val = val[:512]
            else:
                val = str(raw).strip() if raw else None
            if val is not None:
                row_values[field] = val

        row_year = row_values.get("year_number")
        if row_year is None:
            skipped_no_year += 1
            continue

        for equipment_group_id, eg_database_version_id in equipment_groups:
            year_query = Year.query.filter_by(number=row_year)
            if eg_database_version_id is not None:
                year_query = year_query.filter_by(database_version_id=eg_database_version_id)
            else:
                year_query = year_query.filter(Year.database_version_id.is_(None))
            if year_query.first() is None:
                skipped_no_year += 1
                continue

            param_query = EquipmentGroupNaturalFuel.query.filter_by(
                equipment_group_id=equipment_group_id,
                year_number=row_year,
            )
            param = param_query.first()
            if param is None:
                param = EquipmentGroupNaturalFuel(
                    equipment_group_id=equipment_group_id,
                    year_number=row_year,
                    database_version_id=eg_database_version_id,
                )
                db.session.add(param)
                db.session.flush()
                created += 1

            changed = False
            for field, val in row_values.items():
                if hasattr(param, field) and field != "year_number":
                    cur = getattr(param, field)
                    if cur != val:
                        setattr(param, field, val)
                        changed = True
            if changed:
                updated += 1

    try:
        if created or updated:
            db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("[IMPORT_EQUIPMENT_GROUP_NATURAL_FUEL] db error: %s", exc)
        raise ValueError("Ошибка сохранения данных: проверьте корректность файла.") from exc

    elapsed = time.perf_counter() - t0
    message = (
        "Загрузка данных в EquipmentGroupNaturalFuel завершена. "
        "Создано: {created}, обновлено: {updated}, "
        "пропущено (нет numb1120): {skipped_no_match}, "
        "пропущено (нет года в версии): {skipped_no_year}."
    ).format(
        created=created,
        updated=updated,
        skipped_no_match=skipped_no_match,
        skipped_no_year=skipped_no_year,
    )
    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_NATURAL_FUEL] done created=%s updated=%s skipped=%s skipped_no_year=%s elapsed=%.2fs",
        created, updated, skipped_no_match, skipped_no_year, elapsed,
    )
    log_to_db(user, "Загрузка EquipmentGroupNaturalFuel", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped": skipped_no_match,
        "skipped_no_year": skipped_no_year,
    }
