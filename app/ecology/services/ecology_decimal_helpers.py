# -*- coding: utf-8 -*-
"""Общие helpers для парсинга Decimal в модуле экологии."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


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
