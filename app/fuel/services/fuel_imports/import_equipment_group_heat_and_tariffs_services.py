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


def _resolve_equipment_groups_from_numb(numb1120_val):
    """
    Список (equipment_group_id, database_version_id) по NUMB1120 = EquipmentGroup.numb
    для всех версий БД (как в остальных fuel-импортах).
    """
    numb1120_str = _numb1120_for_match(numb1120_val)
    if not numb1120_str:
        return []

    groups = (
        EquipmentGroup.query.filter(cast(EquipmentGroup.numb, String) == numb1120_str)
        .order_by(EquipmentGroup.id)
        .all()
    )
    return [(g.id, g.database_version_id) for g in groups]


def _targets_for_row(numb1120_val):
    """
    Цели записи для всех версий БД:
    - для каждой EG с тем же numb1120 — (equipment_group_id, database_version_id);
    - для версий без такой EG — (None, database_version_id).
    """
    from app.refdata.services.refdata_all_versions_common import (
        all_database_version_ids_for_refdata,
    )

    eg_targets = _resolve_equipment_groups_from_numb(numb1120_val)
    covered_version_ids = {
        version_id for _, version_id in eg_targets if version_id is not None
    }

    targets = list(eg_targets)
    for version_id in all_database_version_ids_for_refdata():
        if version_id not in covered_version_ids:
            targets.append((None, version_id))
    return targets


def _year_exists_for_version(year_number: int, database_version_id) -> bool:
    from app.refdata.models.years.year_model import Year

    year_query = Year.query.filter_by(number=year_number)
    if database_version_id is not None:
        year_query = year_query.filter_by(database_version_id=database_version_id)
    else:
        year_query = year_query.filter(Year.database_version_id.is_(None))
    return year_query.first() is not None


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


def _orm_session():
    """Реальная Session: Flask-SQLAlchemy отдаёт scoped_session без expire_on_commit."""
    sess = db.session
    if not hasattr(sess, "expire_on_commit") and callable(sess):
        return sess()
    return sess


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


def _uq_key(kod_goroda, name_eto, numb1120, var_razv, year_number, database_version_id):
    return (kod_goroda, name_eto, numb1120, var_razv, year_number, database_version_id)


def _preload_eg_by_numb() -> dict[str, list[tuple]]:
    """numb (str) → [(equipment_group_id, database_version_id), ...] включая копии по external_code."""
    from collections import defaultdict

    from app.fuel.services.fuel_imports.fuel_import_all_versions import (
        normalize_import_numb,
    )

    rows = (
        EquipmentGroup.query.with_entities(
            EquipmentGroup.id,
            EquipmentGroup.numb,
            EquipmentGroup.database_version_id,
            EquipmentGroup.external_code,
        ).all()
    )
    id_to_target: dict[int, tuple] = {}
    id_to_code: dict[int, str] = {}
    code_to_ids: dict[str, list[int]] = defaultdict(list)
    numb_to_ids: dict[str, list[int]] = defaultdict(list)
    for eg_id, numb, version_id, external_code in rows:
        if eg_id is None:
            continue
        id_to_target[eg_id] = (eg_id, version_id)
        code = (external_code or "").strip()
        if code:
            id_to_code[eg_id] = code
            code_to_ids[code].append(eg_id)
        numb_str = normalize_import_numb(numb)
        if numb_str:
            numb_to_ids[numb_str].append(eg_id)

    expanded: dict[str, list[tuple]] = {}
    for numb_str, eg_ids in numb_to_ids.items():
        merged: dict[int, tuple] = {}
        for eg_id in eg_ids:
            merged[eg_id] = id_to_target[eg_id]
            code = id_to_code.get(eg_id)
            if not code:
                continue
            for sibling_id in code_to_ids.get(code, []):
                merged[sibling_id] = id_to_target[sibling_id]
        expanded[numb_str] = list(merged.values())
    return expanded


def _preload_years_set() -> set[tuple]:
    from app.refdata.models.years.year_model import Year

    return {
        (number, version_id)
        for number, version_id in Year.query.with_entities(
            Year.number, Year.database_version_id
        ).all()
    }


def _targets_from_cache(numb1120_val, eg_by_numb: dict, version_ids: list) -> list[tuple]:
    numb1120_str = _numb1120_for_match(numb1120_val)
    eg_targets = list(eg_by_numb.get(numb1120_str, [])) if numb1120_str else []
    covered_version_ids = {
        version_id for _, version_id in eg_targets if version_id is not None
    }
    targets = list(eg_targets)
    for version_id in version_ids:
        if version_id not in covered_version_ids:
            targets.append((None, version_id))
    return targets


def _lookup_existing(
    existing_by_key: dict,
    existing_by_key_ndv: dict,
    *,
    kod_goroda,
    name_eto,
    numb1120,
    var_razv,
    year_number,
    database_version_id,
    ndv_st=None,
):
    key = _uq_key(
        kod_goroda, name_eto, numb1120, var_razv, year_number, database_version_id
    )
    if ndv_st is not None:
        matched = existing_by_key_ndv.get((key, ndv_st))
        if matched is not None:
            return matched
    return existing_by_key.get(key)


def _cache_existing_record(
    existing_by_key: dict,
    existing_by_key_ndv: dict,
    param: EquipmentGroupHeatAndTariffs,
    *,
    overwrite: bool = True,
):
    key = _uq_key(
        param.kod_goroda,
        param.name_eto,
        param.numb1120,
        param.var_razv,
        param.year_number,
        param.database_version_id,
    )
    if overwrite or key not in existing_by_key:
        existing_by_key[key] = param
    if param.ndv_st is not None:
        ndv_key = (key, param.ndv_st)
        if overwrite or ndv_key not in existing_by_key_ndv:
            existing_by_key_ndv[ndv_key] = param


def import_equipment_group_heat_and_tariffs_from_excel(file, user: str) -> dict:
    """
    Загружает тепло/тарифы из Excel в EquipmentGroupHeatAndTariffs.
    Годы берутся только из файла (столбец year / Year или столбцы-годы широкого формата Access).
    Выбранный на странице год на импорт не влияет.
    Для каждой строки создаётся/обновляется запись во всех версиях БД
    (по группам с тем же numb1120 или по всем database_version_id без EG).
    """
    from app.refdata.services.refdata_all_versions_common import (
        all_database_version_ids_for_refdata,
    )

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

    # Предзагрузка справочников: иначе ~40k строк × N версий = сотни тысяч SQL.
    t_preload = time.perf_counter()
    eg_by_numb = _preload_eg_by_numb()
    version_ids = all_database_version_ids_for_refdata()
    years_ok = _preload_years_set()

    years_in_file = {
        y
        for y in (
            _safe_int(v) for v in df["year_number"].tolist() if v is not None
        )
        if y is not None
    }
    existing_by_key: dict = {}
    existing_by_key_ndv: dict = {}
    existing_q = EquipmentGroupHeatAndTariffs.query
    if years_in_file:
        existing_q = existing_q.filter(
            EquipmentGroupHeatAndTariffs.year_number.in_(years_in_file)
        )
    for rec in existing_q.order_by(EquipmentGroupHeatAndTariffs.id).all():
        _cache_existing_record(
            existing_by_key, existing_by_key_ndv, rec, overwrite=False
        )

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_HEAT_AND_TARIFFS] preload rows=%s eg_numbs=%s "
        "versions=%s years_ok=%s existing=%s elapsed=%.2fs",
        len(df),
        len(eg_by_numb),
        len(version_ids),
        len(years_ok),
        len(existing_by_key),
        time.perf_counter() - t_preload,
    )

    created = 0
    updated = 0
    skipped_no_year = 0
    skipped_no_year_version = 0
    skipped_empty = 0
    years_loaded: set[int] = set()
    writes_since_commit = 0
    COMMIT_EVERY = 10000
    # Не expire'ить объекты после batch commit — иначе лишние SELECT при следующих правках.
    # expire_on_commit — атрибут Session, не scoped_session (db.session).
    sa_session = _orm_session()
    prev_expire = getattr(sa_session, "expire_on_commit", True)
    if hasattr(sa_session, "expire_on_commit"):
        sa_session.expire_on_commit = False

    def _maybe_commit_batch():
        nonlocal writes_since_commit
        if writes_since_commit < COMMIT_EVERY:
            return
        db.session.commit()
        writes_since_commit = 0
        logger.info(
            "[IMPORT_EQUIPMENT_GROUP_HEAT_AND_TARIFFS] batch commit "
            "created=%s updated=%s elapsed=%.2fs",
            created,
            updated,
            time.perf_counter() - t0,
        )

    try:
        for row in df.to_dict(orient="records"):
            if all(
                v is None or (isinstance(v, float) and pd.isna(v))
                for v in row.values()
            ):
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

            targets = _targets_from_cache(
                row_values.get("numb1120"), eg_by_numb, version_ids
            )
            row_written = False

            for equipment_group_id, db_version_id in targets:
                if (row_year, db_version_id) not in years_ok:
                    skipped_no_year_version += 1
                    continue

                param = _lookup_existing(
                    existing_by_key,
                    existing_by_key_ndv,
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
                    writes_since_commit += 1

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
                    writes_since_commit += 1
                if is_new or changed:
                    _cache_existing_record(existing_by_key, existing_by_key_ndv, param)
                row_written = True

            if row_written:
                years_loaded.add(row_year)
            _maybe_commit_batch()

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
    finally:
        if hasattr(sa_session, "expire_on_commit"):
            sa_session.expire_on_commit = prev_expire

    elapsed = time.perf_counter() - t0
    years_txt = (
        f"{min(years_loaded)}–{max(years_loaded)}"
        if years_loaded
        else "—"
    )
    message = (
        "Загрузка данных в EquipmentGroupHeatAndTariffs завершена "
        "(во все версии БД). "
        "Годы из файла: {years_txt}. "
        "Создано: {created}, обновлено: {updated}, "
        "пропущено (нет Q/TARIF): {skipped_empty}, "
        "пропущено (нет года в строке): {skipped_no_year}, "
        "пропущено (нет года в версии БД): {skipped_no_year_version}."
    ).format(
        years_txt=years_txt,
        created=created,
        updated=updated,
        skipped_empty=skipped_empty,
        skipped_no_year=skipped_no_year,
        skipped_no_year_version=skipped_no_year_version,
    )
    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_HEAT_AND_TARIFFS] done created=%s updated=%s "
        "skipped_empty=%s skipped_no_year=%s skipped_no_year_version=%s "
        "years=%s elapsed=%.2fs",
        created,
        updated,
        skipped_empty,
        skipped_no_year,
        skipped_no_year_version,
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
        "skipped_no_year_version": skipped_no_year_version,
        "years_loaded": sorted(years_loaded),
    }
