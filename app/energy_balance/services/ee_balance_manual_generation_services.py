# -*- coding: utf-8 -*-
"""Ручная плановая выработка СНЭЭ и ТЭС, ГЭС, ГАЭС всех ОЭС.

СЭС и ВЭС считаются со страницы «Выработка ВИЭ» / карточки станции
и ручным вводом не подменяются.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

_logger = logging.getLogger(__name__)
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
    GENERATION_GAES_KEY,
    GENERATION_GES_KEY,
    GENERATION_TES_KEY,
    classify_ee_balance_generation_years,
)
from app.energy_balance.services.power_balance_page_services import (
    GROUP_OES,
    get_power_balance_sheet,
    get_power_balance_sheets,
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
    }
)
_AUTO_SES_VES_GENERATION_KEYS = frozenset(
    {
        "generation_ses_ves",
        "generation_ses",
        "generation_ves",
    }
)
_OES_MANUAL_GENERATION_KEYS = frozenset(
    {GENERATION_TES_KEY, GENERATION_GES_KEY, GENERATION_GAES_KEY}
)

_tables_ready = False
URAL_WITHOUT_TYUMEN_SLUG = "ural-without-tyumen"


def _norm_label(raw: Any) -> str:
    return " ".join(str(raw or "").split()).casefold().replace("ё", "е")


def is_manual_plan_generation_row_key(key: Any, label: Any = None) -> bool:
    raw = str(key or "").strip()
    if raw in _AUTO_SES_VES_GENERATION_KEYS:
        return False
    if raw in MANUAL_PLAN_GENERATION_KEYS:
        return True
    if raw.startswith(("installed_", "available_", "chiim_")):
        return False
    label_n = _norm_label(label)
    if "сэс" in label_n or "вэс" in label_n:
        return False
    if "снээ" in label_n:
        return True
    return False


def _is_ural_tyumen_energy_system_sheet(sheet: dict[str, Any]) -> bool:
    if sheet.get("tyumen_energy_system"):
        return True
    if sheet.get("group") != "res":
        return False
    name = _norm_label(
        sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
    )
    if not all(token in name for token in ("тюмен", "ханты", "ямало")):
        return False
    parent_slug = str(sheet.get("parent_slug") or "").strip()
    parent = get_power_balance_sheet(parent_slug) if parent_slug else None
    return bool(parent) and parent.get("group") == GROUP_OES and "урал" in _norm_label(
        parent.get("sheet_name")
    )


def _is_manual_plan_generation_row_for_sheet(
    slug: Any, key: Any, label: Any = None, *, sheet: dict[str, Any] | None = None
) -> bool:
    row_key = str(key or "").strip()
    if is_manual_plan_generation_row_key(row_key, label):
        return True
    if row_key not in _OES_MANUAL_GENERATION_KEYS:
        return False
    sheet_slug = str(slug or "").strip()
    if sheet_slug == URAL_WITHOUT_TYUMEN_SLUG:
        return True
    if sheet is None:
        sheet = get_power_balance_sheet(sheet_slug)
    return bool(sheet) and (
        sheet.get("group") == GROUP_OES
        or sheet.get("layout") == "oes_vostok"
        or _is_ural_tyumen_energy_system_sheet(sheet)
    )


def overlay_manual_generation_inputs(
    generation_inputs: dict[str, dict[str, dict[int, Any]]] | None,
    manual_inputs: dict[str, dict[str, dict[int, Decimal]]] | None,
    *,
    sheets: list[dict[str, Any]],
    plan_years: list[int],
) -> dict[str, dict[str, dict[int, Any]]]:
    """Плановые ТЭС/ГЭС/ГАЭС ОЭС используют только ручные значения, без автоподстановки."""
    result = generation_inputs if generation_inputs is not None else {}
    plan_set = set(plan_years)
    sheets_by_slug = {sheet["slug"]: sheet for sheet in sheets}
    for slug, sheet in sheets_by_slug.items():
        rows = result.get(slug, {})
        for row_key in _OES_MANUAL_GENERATION_KEYS:
            if not _is_manual_plan_generation_row_for_sheet(slug, row_key, sheet=sheet):
                continue
            if row_key in rows:
                rows[row_key] = {
                    year: amount for year, amount in rows[row_key].items()
                    if int(year) not in plan_set
                }
    for slug, rows in (manual_inputs or {}).items():
        if slug not in sheets_by_slug:
            continue
        dest_sheet = result.setdefault(slug, {})
        for row_key, year_map in (rows or {}).items():
            if not _is_manual_plan_generation_row_for_sheet(
                slug, row_key, sheet=sheets_by_slug[slug]
            ):
                continue
            dest_row = dest_sheet.setdefault(row_key, {})
            for year, amount in (year_map or {}).items():
                if int(year) in plan_set:
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
        _logger.exception("ee balance manual generation: table ensure failed")
        pass


def _version_id() -> int | None:
    try:
        raw = get_current_db_version_id()
    except Exception:
        _logger.exception("ee balance manual generation: db version id lookup failed")
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
    """{sheet_slug: {row_key: {year: value}}} для ручной выработки СНЭЭ и ОЭС."""
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
        _logger.exception("ee balance manual generation: manual values query failed")
        return {}

    if sheets is None:
        sheets = get_power_balance_sheets()
    sheets_by_slug = {sheet["slug"]: sheet for sheet in sheets}

    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for row in rows:
        slug = str(row.sheet_slug or "")
        row_key = str(row.row_key or "")
        if slug not in sheets_by_slug:
            continue
        if not _is_manual_plan_generation_row_for_sheet(
            slug, row_key, sheet=sheets_by_slug[slug]
        ):
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
    """Поля ввода плановой выработки на листах без формулы строки."""
    if not tables or not years:
        return
    try:
        _fact_current, plan_years = classify_ee_balance_generation_years(list(years))
    except Exception:
        _logger.exception("ee balance manual generation: generation year classification failed")
        plan_years = []
    if not plan_years:
        return
    plan_list = [int(year) for year in plan_years]
    for slug, payload in tables.items():
        for row in payload.get("rows") or []:
            if row.get("formula"):
                continue
            if not _is_manual_plan_generation_row_for_sheet(
                slug, row.get("key"), row.get("label"), sheet=payload["sheet"]
            ):
                continue
            row["editable_values"] = True
            row["editable_years"] = list(plan_list)
            row["value_save_kind"] = "generation"
            if row.get("key") in _OES_MANUAL_GENERATION_KEYS:
                row.pop("formula_tooltip", None)


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
    if not _is_manual_plan_generation_row_for_sheet(slug, key):
        raise ValueError("Ручной ввод доступен для СНЭЭ и выработки ТЭС, ГЭС, ГАЭС на листах ОЭС")
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
