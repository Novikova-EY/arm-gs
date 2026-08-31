# -*- coding: utf-8 -*-
"""Ручной ввод выработки СНЭЭ, СЭС и ВЭС в плановых годах баланса ЭЭ."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.exc import ProgrammingError, OperationalError

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.ee_balance_manual_generation_value_model import (
    EeBalanceManualGenerationValue,
)
from app.energy_balance.services.ee_balance_generation_services import (
    classify_ee_balance_generation_years,
)
from app.extensions import db

__all__ = [
    "MANUAL_PLAN_GENERATION_KEYS",
    "is_manual_plan_generation_row_key",
    "overlay_manual_generation_inputs",
    "load_ee_balance_manual_generation_inputs",
    "mark_manual_plan_generation_rows",
    "update_ee_balance_manual_generation_value",
]

MANUAL_PLAN_GENERATION_KEYS = frozenset(
    {
        "generation_snee",
        "generation_ses_ves",
        "generation_ses",
        "generation_ves",
    }
)

_tables_ready = False


def _norm_label(raw: Any) -> str:
    return " ".join(str(raw or "").split()).casefold().replace("ё", "е")


def is_manual_plan_generation_row_key(key: Any, label: Any = None) -> bool:
    raw = str(key or "").strip()
    if raw in MANUAL_PLAN_GENERATION_KEYS:
        return True
    label_n = _norm_label(label)
    if "снээ" in label_n:
        return True
    if "сэс" in label_n or "вэс" in label_n:
        return True
    return False


def overlay_manual_generation_inputs(
    generation_inputs: dict[str, dict[str, dict[int, Decimal]]] | None,
    manual_inputs: dict[str, dict[str, dict[int, Decimal]]] | None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """Накладывает ручные плановые значения на автовыработку по годам (не затирая остальные)."""
    result = generation_inputs if generation_inputs is not None else {}
    for slug, rows in (manual_inputs or {}).items():
        dest_sheet = result.setdefault(slug, {})
        for row_key, year_map in (rows or {}).items():
            dest_row = dest_sheet.setdefault(row_key, {})
            for year, amount in (year_map or {}).items():
                dest_row[int(year)] = amount
    return result


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        EeBalanceManualGenerationValue.__table__.create(bind, checkfirst=True)
        _tables_ready = True
    except Exception:
        pass


def _version_id() -> int | None:
    try:
        raw = get_current_db_version_id()
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _value_query():
    return filter_by_db_version(
        EeBalanceManualGenerationValue.query, EeBalanceManualGenerationValue
    )


def load_ee_balance_manual_generation_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """{sheet_slug: {row_key: {year: value}}} для ручной выработки СНЭЭ / СЭС / ВЭС."""
    if not years:
        return {}
    _ensure_tables()
    wanted_years = {int(year) for year in years}
    try:
        rows = _value_query().all()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return {}
    except Exception:
        return {}

    allowed = None
    if sheets is not None:
        allowed = {str(sheet.get("slug") or "") for sheet in sheets}

    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for row in rows:
        slug = str(row.sheet_slug or "")
        row_key = str(row.row_key or "")
        if not slug or not is_manual_plan_generation_row_key(row_key):
            continue
        if allowed is not None and slug not in allowed:
            continue
        if row.year_number is None or row.value_mln_kvtch is None:
            continue
        try:
            year = int(row.year_number)
        except (TypeError, ValueError):
            continue
        if year not in wanted_years:
            continue
        inputs.setdefault(slug, {}).setdefault(row_key, {})[year] = Decimal(
            str(row.value_mln_kvtch)
        )
    return inputs


def mark_manual_plan_generation_rows(
    tables: dict[str, dict[str, Any]],
    years: list[int] | None,
) -> None:
    """Поля ввода в плановых годах для СНЭЭ / СЭС / ВЭС на листах без формулы строки."""
    if not tables or not years:
        return
    try:
        _fact_current, plan_years = classify_ee_balance_generation_years(list(years))
    except Exception:
        plan_years = []
    if not plan_years:
        return
    plan_list = [int(year) for year in plan_years]
    for payload in tables.values():
        for row in payload.get("rows") or []:
            if row.get("formula"):
                continue
            if not is_manual_plan_generation_row_key(row.get("key"), row.get("label")):
                continue
            row["editable_values"] = True
            row["editable_years"] = list(plan_list)
            row["value_save_kind"] = "generation"


def update_ee_balance_manual_generation_value(
    slug: str,
    row_key: str,
    year: int,
    raw_value: Any,
) -> dict[str, Any]:
    slug = str(slug or "").strip()
    if not slug:
        raise ValueError("Не указан лист баланса")
    key = str(row_key or "").strip()
    if not is_manual_plan_generation_row_key(key):
        raise ValueError("Ручной ввод доступен только для СНЭЭ, СЭС и ВЭС")
    try:
        year_int = int(year)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверный год") from exc
    _fact_current, plan_years = classify_ee_balance_generation_years([year_int])
    if year_int not in set(plan_years):
        raise ValueError("Ручной ввод доступен только для плановых годов")
    try:
        parsed = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверное число") from exc

    _ensure_tables()
    version_id = _version_id()
    existing = (
        _value_query()
        .filter(
            EeBalanceManualGenerationValue.sheet_slug == slug,
            EeBalanceManualGenerationValue.row_key == key,
            EeBalanceManualGenerationValue.year_number == year_int,
        )
        .one_or_none()
    )
    if parsed is None:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
        return {"year": year_int, "row_key": key, "value": None}
    if existing is None:
        existing = EeBalanceManualGenerationValue(
            sheet_slug=slug,
            row_key=key,
            year_number=year_int,
            value_mln_kvtch=parsed,
            database_version_id=version_id,
        )
        db.session.add(existing)
    else:
        existing.value_mln_kvtch = parsed
    _commit_with_retry()
    return {"year": year_int, "row_key": key, "value": parsed}
