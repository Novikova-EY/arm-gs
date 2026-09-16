# -*- coding: utf-8 -*-
"""Формулы макета «Воздух новые»: М = В × У."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ecology.services.ecology_decimal_helpers import decimal_or_none as _d


def zv_mass_tonnes(b_tce: Any, u_kg_per_tce: Any) -> Decimal | None:
    """М, т = В, тыс. тут × У, кг/тут."""
    b = _d(b_tce)
    u = _d(u_kg_per_tce)
    if b is None or u is None:
        return None
    return b * u


def zv_mass_thousand_tonnes(b_tce: Any, u_kg_per_tce: Any) -> Decimal | None:
    """М, тыс. т = (В, тыс. тут × У, кг/тут) / 1000."""
    tonnes = zv_mass_tonnes(b_tce, u_kg_per_tce)
    if tonnes is None:
        return None
    return tonnes / Decimal("1000")


def pg_mass_thousand_tonnes(b_tce: Any, u_t_per_tce: Any) -> Decimal | None:
    """М CO2, тыс. т = В, тыс. тут × У, т/тут."""
    b = _d(b_tce)
    u = _d(u_t_per_tce)
    if b is None or u is None:
        return None
    return b * u
