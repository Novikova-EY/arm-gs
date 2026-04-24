# -*- coding: utf-8 -*-
"""Данные для страницы «Ограничения» (/fuel/restrictions)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import nullslast

from app.common.services.database_version_filter import filter_by_db_version
from app.fuel.models.fue_restriction_model import FuelRestriction


def get_fuel_restrictions_list(
    *,
    year_number: int | None = None,
    union_energy_system_ids: list[int] | None = None,
) -> list[FuelRestriction]:
    """
    Список ограничений. Сортировка как в Access Form_Open: OrderBy = \"obl\".

    - year_number: фильтр по полю year (год расчёта); None — все.
    - union_energy_system_ids: фильтр по полю oes (как правило, код/id ОЭС); None — все.
    """
    q = filter_by_db_version(FuelRestriction.query, FuelRestriction)

    if year_number is not None:
        ydec = Decimal(year_number)
        q = q.filter(FuelRestriction.year == ydec)

    if union_energy_system_ids:
        oes_vals = [Decimal(int(x)) for x in union_energy_system_ids]
        q = q.filter(FuelRestriction.oes.in_(oes_vals))

    return (
        q.order_by(
            nullslast(FuelRestriction.obl.asc()),
            FuelRestriction.id.asc(),
        )
        .all()
    )
