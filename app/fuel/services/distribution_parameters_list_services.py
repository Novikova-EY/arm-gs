# -*- coding: utf-8 -*-
"""Данные для страницы списка параметров распределения (/fuel/distribution_parameters)."""

from __future__ import annotations

from sqlalchemy import nullslast
from sqlalchemy.orm import aliased, joinedload, selectinload

from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.years.year_model import Year


def distribution_parameter_year_numbers_for_filter_dropdown() -> list[int]:
    """
    Номера годов из справочника Year и из фактических id_year в параметрах распределения.
    """
    from app.common.services.get_services.years.years_get_services import get_year_list_full

    base = {int(y.number) for y in get_year_list_full() if getattr(y, "number", None) is not None}

    extra_calc = (
        db.session.query(Year.number)
        .join(DistributionParameter, DistributionParameter.id_year == Year.id)
        .distinct()
        .all()
    )
    extra_base = (
        db.session.query(Year.number)
        .join(DistributionParameter, DistributionParameter.id_base_year == Year.id)
        .distinct()
        .all()
    )
    extra = {int(n) for (n,) in extra_calc if n is not None} | {
        int(n) for (n,) in extra_base if n is not None
    }
    return sorted(base | extra)


def get_distribution_parameters_list(
    *,
    year_numbers: list[int] | None = None,
    base_year_number: int | None = None,
    union_energy_system_ids: list[int] | None = None,
) -> list[DistributionParameter]:
    """
    Параметры распределения.

    - year_numbers: фильтр по расчитываемым годам (номера календарных лет, id_year); None или [] — все.
    - base_year_number: фильтр по базовому году (id_base_year / «Базовый год»); None — все.
    - union_energy_system_ids: необязательный фильтр по ОЭС.
    """
    YearCalc = aliased(Year)
    YearBase = aliased(Year)

    q = (
        DistributionParameter.query.outerjoin(
            YearCalc,
            DistributionParameter.id_year == YearCalc.id,
        )
        .outerjoin(
            YearBase,
            DistributionParameter.id_base_year == YearBase.id,
        )
        .outerjoin(
            UnionEnergySystem,
            DistributionParameter.id_union_energy_system == UnionEnergySystem.id,
        )
    )
    # Пока без фильтра по database_version_id — все версии (для отладки).
    if year_numbers:
        nums = sorted({int(n) for n in year_numbers})
        year_id_list = [
            row[0]
            for row in db.session.query(Year.id).filter(Year.number.in_(nums)).all()
        ]
        if not year_id_list:
            return []
        q = q.filter(DistributionParameter.id_year.in_(year_id_list))

    if base_year_number is not None:
        base_year_id_list = [
            row[0]
            for row in db.session.query(Year.id).filter(Year.number == base_year_number).all()
        ]
        if not base_year_id_list:
            return []
        q = q.filter(DistributionParameter.id_base_year.in_(base_year_id_list))

    if union_energy_system_ids:
        q = q.filter(
            DistributionParameter.id_union_energy_system.in_(union_energy_system_ids)
        )

    return (
        q.options(
            joinedload(DistributionParameter.union_energy_system),
            joinedload(DistributionParameter.year),
            selectinload(DistributionParameter.base_year),
        )
        .order_by(
            nullslast(UnionEnergySystem.display_order.asc()),
            nullslast(YearBase.number.asc()),
            nullslast(YearCalc.number.asc()),
            DistributionParameter.id.asc(),
        )
        .all()
    )
