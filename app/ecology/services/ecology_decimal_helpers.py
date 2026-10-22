# -*- coding: utf-8 -*-
"""Общие helpers для парсинга Decimal в модуле экологии."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any


# «Не округлять» показывает значение целиком. Исходные данные (Excel/Access) хранят
# числа как double, поэтому у них бывает хвост из float-шума: 105.10000000000001.
# 15 значащих цифр – предел, на котором double ещё воспроизводит исходное число,
# поэтому более длинный хвост – артефакт, а не данные.
SIGNIFICANT_DIGITS = 15


def decimal_or_none(value: Any) -> Decimal | None:
    """None/''/невалидное → None; существующий Decimal возвращается как есть."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def decimal_from_loose_text(value: Any) -> Decimal | None:
    """Парсинг отображаемого/импортного текста: strip, запятая → точка, bool → None."""
    if value is None or value is True or value is False:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        text = str(value).strip().replace(",", ".")
    except Exception:
        return None
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def drop_float_noise(value: Any) -> Decimal | None:
    """Decimal без хвоста float-шума: до SIGNIFICANT_DIGITS значащих цифр.

    Значения короче предела возвращаются без изменений (105.1 → 105.1),
    длиннее – обрезаются до значащих (105.1000000000000100 → 105.1).
    """
    dec = decimal_or_none(value)
    if dec is None:
        return None
    with localcontext() as ctx:
        ctx.prec = SIGNIFICANT_DIGITS
        ctx.rounding = ROUND_HALF_UP
        return +dec
