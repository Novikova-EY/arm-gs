# -*- coding: utf-8 -*-
"""EWTP со строки станции — вход расчёта, не результат Коэфф/Распред/Топливо."""
from __future__ import annotations

from decimal import Decimal

_Y_SCALE = Decimal("1000")


def _d0(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def formula_ewtp(qotr, y) -> Decimal:
    """Access: EWTP = QOTR · y / 1000."""
    return _d0(qotr) * _d0(y) / _Y_SCALE


def apply_access_coeff_ewtp(fuel_param, y) -> bool:
    """Кнопка5: ``w!EWTP = QOTR * U!y / 1000`` — пишется всегда, не только в пустое."""
    if fuel_param is None:
        return False
    new = formula_ewtp(getattr(fuel_param, "qotr", None), y)
    old = getattr(fuel_param, "ewtp", None)
    fuel_param.ewtp = new
    return old != new


def resolve_station_ewtp(fuel_param, y=None) -> Decimal:
    """
    Уже заданный ewtp (импорт «Станции(Схема)» / ручная правка) не трогаем.
    Формула — только если ewtp пустой и есть y.
    """
    if fuel_param is None:
        return Decimal("0")
    existing = getattr(fuel_param, "ewtp", None)
    if existing is not None:
        return _d0(existing)
    if y is None:
        return Decimal("0")
    return formula_ewtp(getattr(fuel_param, "qotr", None), y)


def fill_ewtp_if_empty(fuel_param, y) -> bool:
    """Пишет формулу только в пустой ewtp. True, если значение изменили."""
    if fuel_param is None or getattr(fuel_param, "ewtp", None) is not None:
        return False
    if y is None:
        return False
    fuel_param.ewtp = formula_ewtp(getattr(fuel_param, "qotr", None), y)
    return True
