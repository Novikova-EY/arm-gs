#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сервис загрузки EquipmentGroupHeatAndTariffs из Excel.

Поддерживает:
1) длинный формат: year / Q / TARIF + поля сущности;
2) широкий формат Access «Тепло из схем теплоснабжения»: dannie (Q|TARIF) + столбцы-годы.
Связь по NUMB1120 = EquipmentGroup.numb (если задан).
"""

from __future__ import annotations

import logging
import re
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd
from sqlalchemy import cast
from sqlalchemy.types import String
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import (
    EquipmentGroupHeatAndTariffs,
)
from app.fuel.models.fue_equipment_group_model import EquipmentGroup


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
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


IMPORT_FIELDS = [
    "kod_goroda",
    "name_goroda",
    "var_razv",
    "name_eto",
    "numb1120",
    "ndv_st",
    "year_number",
    "q",
    "tarif",
]

INTEGER_FIELDS = frozenset(
    ["kod_goroda", "var_razv", "numb1120", "ndv_st", "year_number"]
)
STRING_FIELDS = frozenset(["name_goroda", "name_eto"])
NUMERIC_FIELDS = frozenset(["q", "tarif"])

COLUMN_ALIASES = {
    "kod_goroda": ["kod_goroda", "kodgoroda", "код_города", "kod"],
    "name_goroda": ["name_goroda", "namegoroda", "город", "name_city"],
    "var_razv": ["var_razv", "varrazv", "вариант"],
    "name_eto": ["name_eto", "nameeto", "name_ETO", "это", "eto"],
    "numb1120": ["numb1120", "num1120", "NUMB1120", "numb", "ном1120"],
    "ndv_st": ["ndv_st", "ndvst", "NDvST", "ndv"],
    "year_number": ["year_number", "year", "Year", "YEAR", "год"],
    "q": ["q", "Q", "тепло"],
    "tarif": ["tarif", "TARIF", "тариф"],
    "dannie": ["dannie", "данные", "dan"],
}


def _apply_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    alias_to_canonical = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            alias_to_canonical[_normalize_column_name(a)] = canonical
    for field in list(IMPORT_FIELDS) + ["dannie"]:
        alias_to_canonical[_normalize_column_name(field)] = field

    rename_map = {}
    for col in df.columns:
        norm = _normalize_column_name(col)
        # столбец-год вида 2024 / y2024
        year_m = re.fullmatch(r"(?:y|year|god)?_?((?:19|20)\d{2})", norm)
        if year_m:
            rename_map[col] = year_m.group(1)
            continue
        # исходное имя столбца уже год
        if re.fullmatch(r"(19|20)\d{2}", str(col).strip()):
            rename_map[col] = str(col).strip()
            continue
        canonical = alias_to_canonical.get(norm) or (
            norm if norm in IMPORT_FIELDS or norm == "dannie" else None
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
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    try:
        f = float(s.replace(",", "."))
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
            raw_scale = (
                -dec_val.as_tuple().exponent if dec_val.as_tuple().exponent < 0 else 0
            )
            scale = min(raw_scale, max_digits)

        if scale <= 0:
            return dec_val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        quant = Decimal("1." + "0" * scale)
        return dec_val.quantize(quant, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_str(value, max_len: int | None = None) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    if max_len and len(s) > max_len:
        return s[:max_len]
    return s


def _numb1120_for_match(value) -> str | None:
    n = _safe_int(value)
    if n is not None:
        return str(n)
    s = str(value).strip() if value is not None else ""
    return s if s else None


def _resolve_equipment_group_from_numb(numb1120_val):
    """
    Одна группа оборудования на NUMB1120: сначала текущая версия БД, иначе любая.
    Нельзя создавать запись на каждую версию EG — уникальный ключ таблицы этого не допускает.
    """
    from app.common.services.database_version_filter import get_current_db_version_id

    numb1120_str = _numb1120_for_match(numb1120_val)
    if not numb1120_str:
        return None, None

    base = EquipmentGroup.query.filter(
        cast(EquipmentGroup.numb, String) == numb1120_str
    )
    current_version_id = get_current_db_version_id()
    if current_version_id is not None:
        eg = base.filter(
            EquipmentGroup.database_version_id == current_version_id
        ).order_by(EquipmentGroup.id).first()
        if eg is not None:
            return eg.id, eg.database_version_id

    eg = base.order_by(EquipmentGroup.id).first()
    if eg is None:
        return None, None
    return eg.id, eg.database_version_id


def _year_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        if re.fullmatch(r"(19|20)\d{2}", str(c).strip()):
            cols.append(str(c).strip())
    return sorted(cols)


def _unpivot_wide_access_df(df: pd.DataFrame) -> pd.DataFrame:
    """Широкий формат Access (dannie + годы) → длинный с q/tarif."""
    year_cols = _year_columns(df)
    if not year_cols or "dannie" not in df.columns:
        return df

    meta_cols = [
        c
        for c in (
            "kod_goroda",
            "name_goroda",
            "var_razv",
            "name_eto",
            "numb1120",
            "ndv_st",
            "dannie",
        )
        if c in df.columns
    ]
    work = df[meta_cols + year_cols].copy()
    melted = work.melt(
        id_vars=meta_cols,
        value_vars=year_cols,
        var_name="year_number",
        value_name="value",
    )
    melted = melted.dropna(subset=["value"], how="any")
    melted["dannie_norm"] = (
        melted["dannie"].astype(str).str.strip().str.upper().replace({"NAN": ""})
    )
    melted = melted[melted["dannie_norm"].isin(["Q", "TARIF"])]
    melted["year_number"] = melted["year_number"].map(_safe_int)

    key_cols = [
        c
        for c in (
            "kod_goroda",
            "name_goroda",
            "var_razv",
            "name_eto",
            "numb1120",
            "ndv_st",
            "year_number",
        )
        if c in melted.columns
    ]
    q_part = melted[melted["dannie_norm"] == "Q"][key_cols + ["value"]].rename(
        columns={"value": "q"}
    )
    t_part = melted[melted["dannie_norm"] == "TARIF"][key_cols + ["value"]].rename(
        columns={"value": "tarif"}
    )
    if q_part.empty and t_part.empty:
        return pd.DataFrame(columns=IMPORT_FIELDS)

    merged = pd.merge(q_part, t_part, on=key_cols, how="outer")
    return merged


def _filter_eq_or_null(query, column, value):
    if value is None:
        return query.filter(column.is_(None))
    return query.filter(column == value)


def _find_existing_record(
    *,
    kod_goroda,
    name_eto,
    numb1120,
    var_razv,
    year_number,
    database_version_id,
    ndv_st=None,
):
    """Поиск по уникальному ключу таблицы (без equipment_group_id)."""
    with db.session.no_autoflush:
        q = EquipmentGroupHeatAndTariffs.query.filter_by(year_number=year_number)
        q = _filter_eq_or_null(q, EquipmentGroupHeatAndTariffs.kod_goroda, kod_goroda)
        q = _filter_eq_or_null(q, EquipmentGroupHeatAndTariffs.name_eto, name_eto)
        q = _filter_eq_or_null(q, EquipmentGroupHeatAndTariffs.numb1120, numb1120)
        q = _filter_eq_or_null(q, EquipmentGroupHeatAndTariffs.var_razv, var_razv)
        q = _filter_eq_or_null(
            q, EquipmentGroupHeatAndTariffs.database_version_id, database_version_id
        )
        # ndv_st не в UNIQUE, но различает строки Access — предпочитаем точное совпадение
        if ndv_st is not None:
            matched = q.filter(
                EquipmentGroupHeatAndTariffs.ndv_st == ndv_st
            ).order_by(EquipmentGroupHeatAndTariffs.id).first()
            if matched is not None:
                return matched
        return q.order_by(EquipmentGroupHeatAndTariffs.id).first()


def import_equipment_group_heat_and_tariffs_from_excel(file, user: str) -> dict:
    """
    Загружает тепло/тарифы из Excel в EquipmentGroupHeatAndTariffs.
    Годы берутся только из файла (столбец year / Year или столбцы-годы широкого формата Access).
    Выбранный на странице год на импорт не влияет.
    """
    logger = _get_logger()
    t0 = time.perf_counter()
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_HEAT_AND_TARIFFS] start user=%s filename=%s",
        user,
        filename,
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(df)

    if "dannie" in df.columns and _year_columns(df):
        df = _unpivot_wide_access_df(df)
        df = _apply_column_aliases(df)

    if "year_number" not in df.columns:
        raise ValueError(
            "В файле нет годов для загрузки: нужен столбец year/Year "
            "или широкий формат Access со столбцами-годами и dannie (Q/TARIF)."
        )

    from app.common.services.database_version_filter import get_current_db_version_id

    created = 0
    updated = 0
    skipped_no_year = 0
    skipped_empty = 0
    years_loaded: set[int] = set()

    for _index, row in df.iterrows():
        if row.isnull().all():
            continue

        row_values = {}
        for field in IMPORT_FIELDS:
            if field not in df.columns:
                continue
            raw = _extract_cell_value(row, field)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                continue
            if field in INTEGER_FIELDS:
                val = _safe_int(raw)
            elif field in NUMERIC_FIELDS:
                val = _safe_decimal(raw)
            elif field == "name_goroda":
                val = _safe_str(raw, 255)
            elif field == "name_eto":
                val = _safe_str(raw)
            else:
                val = _safe_str(raw)
            if val is not None:
                row_values[field] = val

        row_year = row_values.get("year_number")
        if row_year is None:
            skipped_no_year += 1
            continue
        row_values["year_number"] = row_year

        if row_values.get("q") is None and row_values.get("tarif") is None:
            skipped_empty += 1
            continue

        equipment_group_id, eg_database_version_id = _resolve_equipment_group_from_numb(
            row_values.get("numb1120")
        )
        db_version_id = eg_database_version_id
        if db_version_id is None:
            db_version_id = get_current_db_version_id()

        param = _find_existing_record(
            kod_goroda=row_values.get("kod_goroda"),
            name_eto=row_values.get("name_eto"),
            numb1120=row_values.get("numb1120"),
            var_razv=row_values.get("var_razv"),
            year_number=row_year,
            database_version_id=db_version_id,
            ndv_st=row_values.get("ndv_st"),
        )
        is_new = param is None
        if is_new:
            param = EquipmentGroupHeatAndTariffs(
                equipment_group_id=equipment_group_id,
                year_number=row_year,
                database_version_id=db_version_id,
            )
            db.session.add(param)
            created += 1

        changed = False
        for field, val in row_values.items():
            if hasattr(param, field) and field != "year_number":
                cur = getattr(param, field)
                if cur != val:
                    setattr(param, field, val)
                    changed = True
        if param.equipment_group_id != equipment_group_id:
            param.equipment_group_id = equipment_group_id
            changed = True
        if param.database_version_id != db_version_id:
            param.database_version_id = db_version_id
            changed = True
        if changed and not is_new:
            updated += 1
        years_loaded.add(row_year)

    try:
        if created or updated:
            db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception(
            "[IMPORT_EQUIPMENT_GROUP_HEAT_AND_TARIFFS] db error: %s", exc
        )
        raise ValueError(
            "Ошибка сохранения данных: проверьте корректность файла."
        ) from exc

    elapsed = time.perf_counter() - t0
    years_txt = (
        f"{min(years_loaded)}–{max(years_loaded)}"
        if years_loaded
        else "—"
    )
    message = (
        "Загрузка данных в EquipmentGroupHeatAndTariffs завершена. "
        "Годы из файла: {years_txt}. "
        "Создано: {created}, обновлено: {updated}, "
        "пропущено (нет Q/TARIF): {skipped_empty}, "
        "пропущено (нет года в строке): {skipped_no_year}."
    ).format(
        years_txt=years_txt,
        created=created,
        updated=updated,
        skipped_empty=skipped_empty,
        skipped_no_year=skipped_no_year,
    )
    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_HEAT_AND_TARIFFS] done created=%s updated=%s "
        "skipped_empty=%s skipped_no_year=%s years=%s elapsed=%.2fs",
        created,
        updated,
        skipped_empty,
        skipped_no_year,
        sorted(years_loaded),
        elapsed,
    )
    log_to_db(user, "Загрузка EquipmentGroupHeatAndTariffs", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped": skipped_empty,
        "skipped_no_year": skipped_no_year,
        "years_loaded": sorted(years_loaded),
    }
