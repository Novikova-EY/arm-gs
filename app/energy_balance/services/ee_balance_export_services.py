# -*- coding: utf-8 -*-
"""CRUD значений строки «Экспорт электрической энергии»."""
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
from app.energy_balance.models.ee_balance_export_value_model import (
    EXPORT_ROW_KEY,
    EeBalanceExportValue,
)
from app.extensions import db

__all__ = [
    "EXPORT_ROW_KEY",
    "load_ee_balance_export_inputs",
    "update_ee_balance_export_value",
]

_tables_ready = False


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        EeBalanceExportValue.__table__.create(bind, checkfirst=True)
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
    return filter_by_db_version(EeBalanceExportValue.query, EeBalanceExportValue)


def load_ee_balance_export_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """{sheet_slug: {export: {year: value}}} для строк «Экспорт электрической энергии»."""
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
        if not slug:
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
        inputs.setdefault(slug, {}).setdefault(EXPORT_ROW_KEY, {})[year] = Decimal(
            str(row.value_mln_kvtch)
        )
    return inputs


def update_ee_balance_export_value(
    slug: str,
    year: int,
    raw_value: Any,
) -> dict[str, Any]:
    slug = str(slug or "").strip()
    if not slug:
        raise ValueError("Не указан лист баланса")
    try:
        year_int = int(year)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверный год") from exc
    try:
        parsed = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверное число") from exc

    _ensure_tables()
    version_id = _version_id()
    existing = (
        _value_query()
        .filter(
            EeBalanceExportValue.sheet_slug == slug,
            EeBalanceExportValue.year_number == year_int,
        )
        .one_or_none()
    )
    if parsed is None:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
        return {"year": year_int, "value": None}
    if existing is None:
        existing = EeBalanceExportValue(
            sheet_slug=slug,
            year_number=year_int,
            value_mln_kvtch=parsed,
            database_version_id=version_id,
        )
        db.session.add(existing)
    else:
        existing.value_mln_kvtch = parsed
    _commit_with_retry()
    return {"year": year_int, "value": parsed}
