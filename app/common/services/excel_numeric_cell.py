# -*- coding: utf-8 -*-
"""Числовые ячейки Excel: полное значение + number_format для отображения.

Паттерн как на выгрузке «Выработка ЭЭ»: в ячейке float без округления,
формат задаёт число знаков (пользователь может сменить его в Excel).
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Any


def excel_number_format(rounding_digits: int) -> str:
    """Числовой формат Excel (US-код в файле; отображение по локали ОС).

    В OOXML десятичный разделитель — точка, тысячи — запятая. В русской локали
    Excel покажет пробел и запятую.
    """
    if rounding_digits == -1:
        return "#,##0"
    if rounding_digits >= 1:
        return "#,##0." + ("0" * rounding_digits)
    return "#,##0.##########"


def parse_excel_numeric(value: Any) -> float | None:
    """Приводит сырое или экранное значение к float."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, Decimal):
        x = float(value)
        return x if math.isfinite(x) else None

    s = str(value).strip()
    if s in ("", "—", "-"):
        return None
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    negative = s.startswith("-")
    if negative:
        s = s[1:].strip()
    s = s.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        x = float(s)
    except ValueError:
        return None
    if not math.isfinite(x):
        return None
    return -x if negative else x


def excel_numeric_cell_value(
    value: Any,
    *,
    verification: bool = False,
    zero_as_dash: bool = False,
) -> tuple[Any, bool]:
    """Возвращает (значение ячейки, нужен ли числовой формат)."""
    parsed = parse_excel_numeric(value)
    if parsed is None:
        if value in (None, ""):
            return "—", False
        s = str(value).strip()
        if s in ("—", "-"):
            return "—", False
        return value if value not in (None, "") else "—", False
    if zero_as_dash and parsed == 0 and not verification:
        return "—", False
    return parsed, True
