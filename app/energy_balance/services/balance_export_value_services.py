# -*- coding: utf-8 -*-
"""Общая загрузка и обновление значений строк «Экспорт» для EE/PB."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.exc import ProgrammingError, OperationalError

from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.services.balance_table_bootstrap_services import (
    ensure_table,
    version_filtered_query,
    version_id,
)
from app.extensions import db


@dataclass(frozen=True)
class ExportValueConfig:
    value_model: type
    value_field: str
    export_row_key: str


def load_export_inputs(
    config: ExportValueConfig,
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    if not years:
        return {}
    ensure_table(config.value_model)
    wanted_years = {int(year) for year in years}
    try:
        rows = version_filtered_query(config.value_model).all()
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
        raw_value = getattr(row, config.value_field, None)
        if row.year_number is None or raw_value is None:
            continue
        try:
            year = int(row.year_number)
        except (TypeError, ValueError):
            continue
        if year not in wanted_years:
            continue
        inputs.setdefault(slug, {}).setdefault(config.export_row_key, {})[year] = Decimal(
            str(raw_value)
        )
    return inputs


def update_export_value(
    config: ExportValueConfig,
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

    ensure_table(config.value_model)
    current_version_id = version_id()
    existing = (
        version_filtered_query(config.value_model)
        .filter(
            config.value_model.sheet_slug == slug,
            config.value_model.year_number == year_int,
        )
        .one_or_none()
    )
    if parsed is None:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
        return {"year": year_int, "value": None}
    if existing is None:
        existing = config.value_model(
            sheet_slug=slug,
            year_number=year_int,
            database_version_id=current_version_id,
        )
        setattr(existing, config.value_field, parsed)
        db.session.add(existing)
    else:
        setattr(existing, config.value_field, parsed)
    _commit_with_retry()
    return {"year": year_int, "value": parsed}
