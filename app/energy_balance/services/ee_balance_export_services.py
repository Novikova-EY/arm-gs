# -*- coding: utf-8 -*-
"""CRUD значений строки «Экспорт электрической энергии»."""
from __future__ import annotations

from typing import Any

from app.energy_balance.models.ee_balance_export_value_model import (
    EXPORT_ROW_KEY,
    EeBalanceExportValue,
)
from app.energy_balance.services.balance_export_value_services import (
    ExportValueConfig,
    load_export_inputs,
    update_export_value,
)

__all__ = [
    "EXPORT_ROW_KEY",
    "load_ee_balance_export_inputs",
    "update_ee_balance_export_value",
]

_CONFIG = ExportValueConfig(
    value_model=EeBalanceExportValue,
    value_field="value_mln_kvtch",
    export_row_key=EXPORT_ROW_KEY,
)


def load_ee_balance_export_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
):
    """{sheet_slug: {export: {year: value}}} для строк «Экспорт электрической энергии»."""
    return load_export_inputs(_CONFIG, years, sheets)


def update_ee_balance_export_value(slug: str, year: int, raw_value: Any):
    return update_export_value(_CONFIG, slug, year, raw_value)
