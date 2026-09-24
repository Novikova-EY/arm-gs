# -*- coding: utf-8 -*-
"""Импорт отчетных данных ГИС ТЭК из книги «БАЗА_ГИС ТЭК.xlsx»."""

from __future__ import annotations

import logging
import math
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from typing import Any

import pandas as pd
from sqlalchemy.exc import IntegrityError

from app.common.services.database_version_filter import get_current_db_version_id
from app.ecology.models.pg_report_gis_tek_model import PGReportGisTek
from app.ecology.models.zv_report_gis_tek_model import ZVReportGisTek
from app.ecology.services.gis_tek_constants import (
    REPORT_PG,
    REPORT_ZV,
    SHEET_NAMES,
    SKIP_IMPORT_HEADERS,
    VALUE_COLUMNS,
    ZV_DERIVED_ATTRS,
    ZV_UNSTORED_ATTRS,
)
from app.ecology.services.gis_tek_page_services import apply_zv_derived_metrics
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.logs.services.logging_service import log_to_db
from app.refdata.models.years.year_model import Year


REPORT_MODELS = {
    REPORT_PG: PGReportGisTek,
    REPORT_ZV: ZVReportGisTek,
}

# Старые заголовки Excel «БАЗА_ГИС ТЭК» (до переименования нефтетоплива в мазут).
VALUE_LABEL_ALIASES = {
    REPORT_PG: {
        "oil_fuel_consumption_tce": ("Расход нефтетоплива, тут",),
        "co2_from_oil_fuel_t": ("Выбросы СО2 от сжигания нефтетоплива, т",),
    },
}

IDENTITY_ALIASES = {
    "station_numb": (
        "№_станции",
        "n_станции",
        "номер_станции",
        "numb",
        "numb1120",
    ),
    "gis_tek_station_name": (
        "электростанция_гис_тэк",
        "электростанциягистэк",
        "электростанция_гис тэк",
    ),
    "station_type": ("тип_станции", "типстанции"),
    "year_number": ("год", "year", "year_number"),
}


def _get_logger():
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            return current_app.logger
    except Exception:
        pass
    return logging.getLogger(__name__)


def normalize_header(col) -> str:
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").strip().lower()
    s = s.replace("№", "n").replace("№", "n")
    s = " ".join(s.split())
    s = s.replace("(", " ").replace(")", " ").replace("[", " ").replace("]", " ")
    s = s.replace("«", " ").replace("»", " ")
    s = s.replace(".", " ").replace(",", " ").replace(";", " ")
    s = "_".join(filter(None, s.split()))
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    return "_".join(filter(None, s.split("_")))


def _alias_map_for_kind(kind: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical, aliases in IDENTITY_ALIASES.items():
        mapping[normalize_header(canonical)] = canonical
        for alias in aliases:
            mapping[normalize_header(alias)] = canonical
    for attr, label in VALUE_COLUMNS[kind]:
        mapping[normalize_header(attr)] = attr
        mapping[normalize_header(label)] = attr
    for attr, aliases in (VALUE_LABEL_ALIASES.get(kind) or {}).items():
        for alias in aliases:
            mapping[normalize_header(alias)] = attr
    return mapping


def apply_column_aliases(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    alias_to_canonical = _alias_map_for_kind(kind)
    rename_map = {}
    used: set[str] = set()
    for col in df.columns:
        norm = normalize_header(col)
        if norm in SKIP_IMPORT_HEADERS:
            continue
        canonical = alias_to_canonical.get(norm)
        if canonical and canonical not in used:
            rename_map[col] = canonical
            used.add(canonical)
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def find_sheet_name(sheet_names: list[str], kind: str) -> str | None:
    expected = SHEET_NAMES[kind]
    expected_norm = normalize_header(expected)
    for name in sheet_names:
        if name == expected or normalize_header(name) == expected_norm:
            return name
        if expected_norm and expected_norm in normalize_header(name):
            return name
    return None


def _header_row_index(raw: pd.DataFrame) -> int:
    for i, row in raw.iterrows():
        values = [normalize_header(v) for v in row.tolist()]
        if any(v in ("n_станции", "номер_станции") or v.endswith("станции") and "n" in v for v in values):
            if any("год" in (v or "") or v == "year" for v in values) or any(
                "электростанция" in (v or "") for v in values
            ):
                return int(i)
        if "n_станции" in values or "номер_станции" in values:
            return int(i)
    return 0


def read_gis_tek_sheet(file_bytes: bytes, kind: str) -> pd.DataFrame:
    xls = pd.ExcelFile(BytesIO(file_bytes))
    sheet = find_sheet_name(list(xls.sheet_names), kind)
    if sheet is None:
        raise ValueError(
            f"В файле нет листа «{SHEET_NAMES[kind]}». Найдены: {', '.join(xls.sheet_names)}."
        )
    raw = xls.parse(sheet, header=None)
    header_idx = _header_row_index(raw)
    header = raw.iloc[header_idx].tolist()
    df = raw.iloc[header_idx + 1 :].copy()
    df.columns = header
    df = df.dropna(how="all")
    df = apply_column_aliases(df, kind)
    return df


def _cell(row, field: str):
    if field not in getattr(row, "index", []):
        return None
    val = row.get(field)
    if isinstance(val, pd.Series):
        for v in val:
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                if isinstance(v, str) and not v.strip():
                    continue
                return v
        return None
    return val


def safe_int(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return int(value)
        return None
    s = str(value).strip().replace("\xa0", " ")
    if not s or s.lower() in ("nan", "none", "—", "-", "–"):
        return None
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    try:
        f = float(s.replace(",", "."))
        if f.is_integer():
            return int(f)
    except (ValueError, TypeError):
        return None
    return None


def safe_str(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    return s


def station_type_str(value) -> str | None:
    s = safe_str(value)
    if s is None or s == "0":
        return None
    try:
        if float(s.replace(",", ".")) == 0:
            return None
    except (ValueError, TypeError):
        pass
    return s


def safe_decimal(value, max_digits: int = 16) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        s = value.strip().replace("\u00a0", " ").replace("\xa0", " ")
        s = "".join(ch for ch in s if ch != " ")
        if not s or s.lower() in ("nan", "—", "-", "–"):
            return None
        value = s.replace(",", ".")
    try:
        if isinstance(value, Decimal):
            dec_val = value
        else:
            dec_val = Decimal(str(value))
        raw_scale = -dec_val.as_tuple().exponent if dec_val.as_tuple().exponent < 0 else 0
        scale = min(raw_scale, max_digits)
        if scale <= 0:
            return dec_val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        quant = Decimal("1." + "0" * scale)
        return dec_val.quantize(quant, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _load_equipment_groups_by_numb(version_id: int | None) -> dict[int, list[EquipmentGroup]]:
    query = EquipmentGroup.query
    if version_id is not None:
        query = query.filter(EquipmentGroup.database_version_id == version_id)
    else:
        query = query.filter(EquipmentGroup.database_version_id.is_(None))
    by_numb: dict[int, list[EquipmentGroup]] = {}
    for group in query.all():
        numb = getattr(group, "numb", None)
        if numb is None:
            continue
        by_numb.setdefault(int(numb), []).append(group)
    return by_numb


def _pick_equipment_group(
    groups: list[EquipmentGroup],
    excel_base_name: str | None,
) -> EquipmentGroup | None:
    if not groups:
        return None
    if len(groups) == 1:
        return groups[0]
    needle = (excel_base_name or "").strip().lower()
    if needle:
        for group in groups:
            for candidate in (group.name, group.name_ext):
                if (candidate or "").strip().lower() == needle:
                    return group
    return groups[0]


def _known_year_numbers(version_id: int | None) -> set[int]:
    query = Year.query
    if version_id is not None:
        query = query.filter(Year.database_version_id == version_id)
    else:
        query = query.filter(Year.database_version_id.is_(None))
    return {int(y.number) for y in query.all() if y.number is not None}


def import_gis_tek_from_xlsx_bytes(file_bytes: bytes, kind: str, user: str) -> dict:
    if kind not in REPORT_MODELS:
        raise ValueError("Неизвестный вид отчетных данных.")
    logger = _get_logger()
    t0 = time.perf_counter()
    df = read_gis_tek_sheet(file_bytes, kind)
    if "station_numb" not in df.columns or "year_number" not in df.columns:
        raise ValueError(
            "В листе нет обязательных столбцов «№_станции» и «Год»."
        )

    model = REPORT_MODELS[kind]
    value_attrs = [
        attr
        for attr, _label in VALUE_COLUMNS[kind]
        if kind != REPORT_ZV or attr not in ZV_DERIVED_ATTRS
    ]
    version_id = get_current_db_version_id()
    groups_by_numb = _load_equipment_groups_by_numb(version_id)
    known_years = _known_year_numbers(version_id)

    existing_query = model.query
    if version_id is not None:
        existing_query = existing_query.filter(model.database_version_id == version_id)
    else:
        existing_query = existing_query.filter(model.database_version_id.is_(None))
    existing = {
        (row.station_numb, row.year_number): row for row in existing_query.all()
    }

    created = 0
    updated = 0
    skipped_no_year = 0
    skipped_no_numb = 0
    unmatched_groups = 0

    for _, row in df.iterrows():
        station_numb = safe_int(_cell(row, "station_numb"))
        year_number = safe_int(_cell(row, "year_number"))
        if station_numb is None:
            skipped_no_numb += 1
            continue
        if year_number is None:
            skipped_no_year += 1
            continue
        if year_number not in known_years:
            skipped_no_year += 1
            continue

        gis_name = safe_str(_cell(row, "gis_tek_station_name"))
        st_type = station_type_str(_cell(row, "station_type"))
        group = _pick_equipment_group(groups_by_numb.get(station_numb) or [], None)
        if group is None:
            unmatched_groups += 1

        values: dict[str, Any] = {}
        for attr in value_attrs:
            values[attr] = safe_decimal(_cell(row, attr))
        if kind == REPORT_ZV:
            values = apply_zv_derived_metrics(values)

        key = (station_numb, year_number)
        param = existing.get(key)
        is_new = param is None
        if is_new:
            param = model(
                station_numb=station_numb,
                year_number=year_number,
                database_version_id=version_id,
            )
            db.session.add(param)
            existing[key] = param
            created += 1

        changed = is_new
        if param.gis_tek_station_name != gis_name:
            param.gis_tek_station_name = gis_name
            changed = True
        if param.station_type != st_type:
            param.station_type = st_type
            changed = True
        group_id = group.id if group is not None else None
        if param.equipment_group_id != group_id:
            param.equipment_group_id = group_id
            changed = True
        for attr, val in values.items():
            if attr in ZV_UNSTORED_ATTRS:
                continue
            if getattr(param, attr, None) != val:
                setattr(param, attr, val)
                changed = True
        if changed and not is_new:
            updated += 1

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("[ECO_GIS_TEK_IMPORT] db error: %s", exc)
        raise ValueError("Ошибка сохранения данных: проверьте корректность файла.") from exc

    seeded_params = 0
    if kind == REPORT_PG:
        from app.ecology.services.analysis_pg_param_services import (
            seed_missing_analysis_pg_params_from_reports,
        )
        from app.ecology.services.gis_tes_fuel_comparison_constants import (
            PG_ANALYSIS_SHEET_SLUGS,
        )

        for sheet_slug in sorted(PG_ANALYSIS_SHEET_SLUGS):
            seeded_params += seed_missing_analysis_pg_params_from_reports(sheet_slug)

    elapsed = time.perf_counter() - t0
    message = (
        f"Загрузка «{SHEET_NAMES[kind]}» завершена. "
        f"Создано: {created}, обновлено записей: {updated}, "
        f"без №_станции: {skipped_no_numb}, без года в справочнике: {skipped_no_year}, "
        f"без группы оборудования: {unmatched_groups}."
    )
    if kind == REPORT_PG and seeded_params:
        message += f" В параметры анализа ПГ добавлено: {seeded_params}."
    logger.info(
        "[ECO_GIS_TEK_IMPORT] kind=%s created=%s updated=%s skipped_numb=%s skipped_year=%s unmatched=%s seeded_params=%s elapsed=%.2fs",
        kind,
        created,
        updated,
        skipped_no_numb,
        skipped_no_year,
        unmatched_groups,
        seeded_params,
        elapsed,
    )
    log_to_db(user, f"Импорт ГИС ТЭК ({kind})", message)
    return {
        "message": message,
        "created": created,
        "updated": updated,
        "skipped_no_numb": skipped_no_numb,
        "skipped_no_year": skipped_no_year,
        "unmatched_groups": unmatched_groups,
        "seeded_analysis_pg_params": seeded_params,
    }
