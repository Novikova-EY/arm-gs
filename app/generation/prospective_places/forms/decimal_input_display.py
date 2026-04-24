# -*- coding: utf-8 -*-
"""Форматирование Decimal для полей ввода (без лишних нулей справа)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def decimal_for_form_strip_trailing_zeros(val: Any) -> Decimal | None:
    """
    Значение для DecimalField: убирает незначащие нули справа (типично для Numeric из БД).

    None и пустое после очистки → None.
    """
    if val is None:
        return None
    try:
        d = val if isinstance(val, Decimal) else Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("", "-"):
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def format_decimal_plain_str(val: Any) -> str:
    """Строка для поля ввода: без незначащих нулей справа (пусто, если None)."""
    d = decimal_for_form_strip_trailing_zeros(val)
    if d is None:
        return ""
    return str(d)


def format_construction_period_years_display(val: Any) -> str:
    """
    Отображение срока строительства: целое без дробной части, иначе один знак (запятая как в РФ).
    """
    if val is None:
        return ""
    try:
        d = val if isinstance(val, Decimal) else Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return str(val).replace(".", ",")
    s = format(d.quantize(Decimal("0.1")), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def normalize_construction_period_years(val: Any) -> Decimal | None:
    """Значение для сохранения в БД (Numeric с одним знаком после запятой)."""
    if val is None:
        return None
    try:
        d = val if isinstance(val, Decimal) else Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
