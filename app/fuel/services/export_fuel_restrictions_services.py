# -*- coding: utf-8 -*-
"""Экспорт «Ограничения» в Excel (шапка как в Access)."""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Iterable

from openpyxl import Workbook

from app.fuel.models.fue_restriction_model import FuelRestriction

# Порядок столбцов как в Access-таблице «Ограничения».
_EXPORT_COLUMNS: list[tuple[str, str]] = [
    ("year", "year"),
    ("oes", "oes"),
    ("restriction_name", "name"),
    ("obl", "obl"),
    ("emin", "emin"),
    ("emax", "emax"),
    ("ecur", "ecur"),
    ("h", "H"),
    ("ecurdis", "ecurdis"),
    ("hdis", "Hdis"),
    ("etp", "etp"),
    ("kobl", "kobl"),
    ("kcur", "kcur"),
]


def _excel_number(value) -> int | float | str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            try:
                return int(value)
            except Exception:
                return float(value)
        return float(value)
    if isinstance(value, float):
        if value == int(value):
            return int(value)
        return value
    return value


def export_fuel_restrictions_to_excel(rows: Iterable[FuelRestriction]) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Ограничения"
    ws.append([header for _, header in _EXPORT_COLUMNS])
    for row in rows:
        ws.append([_excel_number(getattr(row, attr)) for attr, _ in _EXPORT_COLUMNS])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
