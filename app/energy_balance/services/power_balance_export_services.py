# -*- coding: utf-8 -*-
"""CRUD значений строки «Экспорт мощности» на страницах баланса мощности."""
from __future__ import annotations

from typing import Any

from app.energy_balance.models.power_balance_export_value_model import (
    EXPORT_ROW_KEY,
    PowerBalanceExportValue,
)
from app.energy_balance.services.balance_export_value_services import (
    ExportValueConfig,
    load_export_inputs,
    update_export_value,
)

__all__ = [
    "EXPORT_ROW_KEY",
    "load_power_balance_export_inputs",
    "update_power_balance_export_value",
]

_CONFIG = ExportValueConfig(
    value_model=PowerBalanceExportValue,
    value_field="value_mw",
    export_row_key=EXPORT_ROW_KEY,
    action="Изменения в балансе мощности, экспорт мощности",
    change_label="Экспорт мощности",
)


def load_power_balance_export_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
):
    """{sheet_slug: {export: {year: value}}} для строк «Экспорт мощности»."""
    return load_export_inputs(_CONFIG, years, sheets)


def update_power_balance_export_value(
    slug: str,
    year: int,
    raw_value: Any,
    *,
    user: Any = None,
    sheet_name: str | None = None,
):
    return update_export_value(
        _CONFIG, slug, year, raw_value, user=user, sheet_name=sheet_name
    )
