# -*- coding: utf-8 -*-
"""Сервис загрузки EquipmentGroupFuelParam из Excel. Жёсткое сравнение: NUMB1120 == EquipmentGroupSet.numb."""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from sqlalchemy.exc import IntegrityError

from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.refdata.models.years.year_model import Year


def _get_logger():
    try:
        from flask import has_app_context
        if has_app_context():
            from flask import current_app
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


# Поля EquipmentGroupFuelParam для заполнения из Excel (кроме id, equipment_group_set_station_id, year_number)
EQUIPMENT_GROUP_FUEL_PARAM_FIELDS = [
    "name", "obor", "ved", "ved_cyrillic", "obl", "dep", "oes", "ees", "er", "gk", "be",
    "numb1120", "numb1",
    "nust", "nr", "e", "eotp", "eurt", "eust", "q", "turt", "tust", "b",
    "gaz", "isk_gaz", "mazut", "torf", "slan", "proch", "ugol", "don", "podm", "pech",
    "arkt", "kuzn", "ural", "bashk", "kazah", "kan", "tung", "irkut", "hak", "tuv",
    "bur", "chit", "yakut", "amur", "urg", "ushum", "prim", "mag", "chukot", "kamch", "sah",
    "qotr", "snk", "sn_t", "ewtp", "nt", "nt_sum",
]

INTEGER_FIELDS = frozenset([
    "obor", "ved", "ved_cyrillic", "obl", "dep", "oes", "ees", "er", "gk", "be",
    "numb1120", "numb1",
])

NUMERIC_FIELDS = frozenset([
    "nust", "nr", "e", "eotp", "eurt", "eust", "q", "turt", "tust", "b",
    "gaz", "isk_gaz", "mazut", "torf", "slan", "proch", "ugol", "don", "podm", "pech",
    "arkt", "kuzn", "ural", "bashk", "kazah", "kan", "tung", "irkut", "hak", "tuv",
    "bur", "chit", "yakut", "amur", "urg", "ushum", "prim", "mag", "chukot", "kamch", "sah",
    "qotr", "snk", "sn_t", "ewtp", "nt", "nt_sum",
])

COLUMN_ALIASES = {
    "numb1120": ["numb1120", "num1120", "номер1120", "numb", "ном1120", "agr_numb1120", "topl_agr_numb1120"],
    "ved_cyrillic": ["вед", "ved_cyrillic"],
}


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Приводит имена колонок к каноническим (поля модели)."""
    alias_to_canonical = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in EQUIPMENT_GROUP_FUEL_PARAM_FIELDS:
        alias_to_canonical[_normalize_column_name(field)] = field

    rename_map = {}
    for col in df.columns:
        norm = _normalize_column_name(col)
        canonical = alias_to_canonical.get(norm) or (norm if norm in EQUIPMENT_GROUP_FUEL_PARAM_FIELDS else None)
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
    """
    Приводит значение к Decimal для нецелочисленных полей импорта.
    Поддерживает запятую как десятичный разделитель и сохраняет все знаки
    после запятой точно (как у мощностей на station_list). Пустые значения → None.
    """
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

        scale: int
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


def _numb1120_to_str_for_match(val):
    """
    Преобразует значение NUMB1120 из файла в строку для жёсткого сравнения с topl_numb.
    Excel отдаёт числа как float (1120.0) — приводим к целой строке.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    s = str(val).strip()
    return s if s else None


def import_equipment_group_fuel_params_from_excel(file, user: str, year: int) -> dict:
    """
    Загружает данные из Excel в EquipmentGroupFuelParam.
    Жёсткое сравнение: NUMB1120 из файла == EquipmentGroupSet.numb (точно).
    Поиск только среди записей текущей версии БД (database_version_id).
    Находим EquipmentGroupSet.id -> EquipmentGroupSetStation (тоже по версии).
    Данные из файла сохраняются в EquipmentGroupFuelParam для каждого EquipmentGroupSetStation.
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_FUEL_PARAMS] start user=%s filename=%s year=%s",
        user, filename, year,
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(df)

    if "numb1120" not in df.columns:
        raise ValueError(
            "Неверный шаблон файла: отсутствует колонка NUMB1120. "
            "Найдены колонки: " + ", ".join(str(c) for c in df.columns[:20]) + ("..." if len(df.columns) > 20 else "") + ". "
            "NUMB1120 необходима для связи с EquipmentGroupSet.numb."
        )

    if Year.query.filter_by(number=year).first() is None:
        raise ValueError(
            f"Год {year} не найден в справочнике gs_years. "
            "Добавьте год в справочник или выберите другой год."
        )

    current_version = get_current_db_version_id()
    created = 0
    updated = 0
    skipped_no_match = 0
    errors = []

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        numb1120_raw = _extract_cell_value(row, "numb1120")
        numb1120_str = _numb1120_to_str_for_match(numb1120_raw)
        if not numb1120_str:
            skipped_no_match += 1
            continue

        eq_query = EquipmentGroupSet.query.filter(EquipmentGroupSet.numb == numb1120_str)
        if current_version is not None:
            eq_query = eq_query.filter(EquipmentGroupSet.database_version_id == current_version)
        else:
            eq_query = eq_query.filter(EquipmentGroupSet.database_version_id.is_(None))
        equipment_group_set = eq_query.first()
        if not equipment_group_set:
            skipped_no_match += 1
            if len(errors) < 20:
                errors.append(
                    f"Строка {index + 2}: NUMB1120={numb1120_raw!r} — нет EquipmentGroupSet с numb={numb1120_str!r} "
                    f"в текущей версии БД"
                )
            continue

        link_query = EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.equipment_group_set_id == equipment_group_set.id
        )
        if current_version is not None:
            link_query = link_query.filter(EquipmentGroupSetStation.database_version_id == current_version)
        else:
            link_query = link_query.filter(EquipmentGroupSetStation.database_version_id.is_(None))
        links = link_query.all()
        if not links:
            skipped_no_match += 1
            if len(errors) < 20:
                errors.append(
                    f"Строка {index + 2}: NUMB1120={numb1120_raw!r} — найдено EquipmentGroupSet id={equipment_group_set.id}, "
                    "но нет EquipmentGroupSetStation в текущей версии БД"
                )
            continue

        row_values = {}
        for field in EQUIPMENT_GROUP_FUEL_PARAM_FIELDS:
            if field not in df.columns:
                continue
            raw = _extract_cell_value(row, field)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                continue
            if field in INTEGER_FIELDS:
                val = _safe_int(raw)
            elif field in NUMERIC_FIELDS:
                val = _safe_decimal(raw)
            else:
                val = str(raw).strip() if raw else None
                if val and len(val) > 512 and field == "name":
                    val = val[:512]
            if val is not None:
                row_values[field] = val

        for link in links:
            param = (
                EquipmentGroupFuelParam.query
                .filter_by(
                    equipment_group_set_station_id=link.id,
                    year_number=year,
                )
                .first()
            )
            if param is None:
                param = EquipmentGroupFuelParam(
                    equipment_group_set_station_id=link.id,
                    year_number=year,
                )
                if current_version:
                    set_db_version_on_create(param)
                db.session.add(param)
                db.session.flush()
                created += 1

            changed = False
            for field, val in row_values.items():
                if hasattr(param, field):
                    cur = getattr(param, field)
                    if cur != val:
                        setattr(param, field, val)
                        changed = True
            if changed:
                updated += 1

    try:
        if created or updated:
            db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        logger.exception("[IMPORT_EQUIPMENT_GROUP_FUEL_PARAMS] IntegrityError on commit")
        raise ValueError(
            f"Ошибка при сохранении в БД: {e}. "
            "Возможно, год отсутствует в справочнике gs_years."
        ) from e

    elapsed = time.perf_counter() - t0
    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_FUEL_PARAMS] done user=%s filename=%s year=%s created=%s updated=%s skipped=%s time=%.2fs",
        user, filename, year, created, updated, skipped_no_match, elapsed,
    )
    try:
        log_to_db(
            user,
            "Загрузка EquipmentGroupFuelParam",
            details=f"filename={filename}; year={year}; created={created}; updated={updated}; skipped={skipped_no_match}; errors={len(errors)}",
            entity_type="import_equipment_group_fuel_params",
            entity_id=None,
        )
    except Exception:
        logger.exception("[IMPORT_EQUIPMENT_GROUP_FUEL_PARAMS] failed to write log")

    total_rows = len([r for i, r in df.iterrows() if not r.isnull().all()])
    if total_rows > 0 and created == 0 and updated == 0 and skipped_no_match >= total_rows:
        hint = (
            " Ни одна строка не сопоставлена. Жёсткое сравнение: NUMB1120 == EquipmentGroupSet.numb, "
            "поиск в пределах текущей версии БД. Запустите сначала импорт групп оборудования."
        )
    else:
        hint = ""

    message = (
        f"Загрузка данных в EquipmentGroupFuelParam за {year} год завершена. "
        f"Создано: {created}, обновлено: {updated}, пропущено (нет связи по NUMB1120): {skipped_no_match}. "
        f"Ошибок: {len(errors)}.{hint}"
    )
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped_no_match": skipped_no_match,
        "errors_count": len(errors),
    }
