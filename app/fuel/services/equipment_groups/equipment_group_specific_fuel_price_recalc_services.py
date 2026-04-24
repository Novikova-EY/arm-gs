# -*- coding: utf-8 -*-
"""
Пересчёт полей xxx_c в EquipmentGroupSpecificFuelPrice по данным:
EquipmentGroupFuelParam, EquipmentGroupExtraFuelParam, EquipmentGroupSpecificFuelCost.

Формулы — в equipment_group_specific_fuel_price_calc_services (fill_specific_fuel_price_from_calc).
"""
from __future__ import annotations

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
    EquipmentGroupSpecificFuelCost,
)
from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
    EquipmentGroupSpecificFuelPrice,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_price_calc_services import (
    fill_specific_fuel_price_from_calc,
)


def recalculate_specific_fuel_prices_for_equipment_group(
    equipment_group_id: int,
    start_year: int,
    end_year: int,
    *,
    commit: bool = True,
) -> int:
    """
    Пересчитывает удельную цену (поля xxx_c) для одной группы оборудования
    за годы [start_year, end_year]. При отсутствии строки цены создаёт её.

    Возвращает число обработанных годов (строк price).
    """
    db.session.flush()

    version_id = get_current_db_version_id()

    def _year_filter(q, model):
        return q.filter(
            model.year_number >= start_year,
            model.year_number <= end_year,
        )

    fuel_params = {
        r.year_number: r
        for r in _year_filter(
            EquipmentGroupFuelParam.query.filter_by(
                equipment_group_id=equipment_group_id,
            ),
            EquipmentGroupFuelParam,
        ).all()
    }
    extra_params = {
        r.year_number: r
        for r in _year_filter(
            EquipmentGroupExtraFuelParam.query.filter_by(
                equipment_group_id=equipment_group_id,
            ),
            EquipmentGroupExtraFuelParam,
        ).all()
    }
    costs = {
        r.year_number: r
        for r in _year_filter(
            EquipmentGroupSpecificFuelCost.query.filter_by(
                equipment_group_id=equipment_group_id,
            ),
            EquipmentGroupSpecificFuelCost,
        ).all()
    }
    prices_existing = {
        r.year_number: r
        for r in _year_filter(
            EquipmentGroupSpecificFuelPrice.query.filter_by(
                equipment_group_id=equipment_group_id,
            ),
            EquipmentGroupSpecificFuelPrice,
        ).all()
    }

    years = sorted(
        set(fuel_params)
        | set(extra_params)
        | set(costs)
        | set(prices_existing)
    )
    years = [y for y in years if start_year <= y <= end_year]

    updates_count = 0
    for year in years:
        price = prices_existing.get(year)
        if price is None:
            price = EquipmentGroupSpecificFuelPrice(
                equipment_group_id=equipment_group_id,
                year_number=year,
                database_version_id=version_id,
            )
            set_db_version_on_create(price)
            db.session.add(price)
            db.session.flush()
            prices_existing[year] = price

        fill_specific_fuel_price_from_calc(
            price,
            fuel_params.get(year),
            extra_params.get(year),
            costs.get(year),
        )
        updates_count += 1

    if updates_count and commit:
        db.session.commit()

    return updates_count
