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


def recalculate_all_specific_fuel_prices(
    year: int | None = None,
    *,
    equipment_group_id: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    commit: bool = True,
    all_versions: bool = False,
) -> int:
    """
    Пересчитывает поля xxx_c в EquipmentGroupSpecificFuelPrice
    по cost / объёмам топлива.

    Использование:
    - кнопка «Рассчитать цены топлива» на странице цены;
    - после импорта стоимости / топливных параметров.

    :param year: если задан — только этот год
    :param equipment_group_id: ограничить одну группу
    :param start_year, end_year: диапазон лет
    :param commit: False при вызове из orchestrator до общего commit
    :param all_versions: если True — без фильтра текущей версии БД
    :return: число обработанных строк цены
    """
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup

    _start = start_year
    _end = end_year
    if year is not None:
        _start = year
        _end = year
    if _start is None or _end is None:
        return 0

    allowed_eg_ids = None
    if equipment_group_id is not None or not all_versions:
        eg_query = EquipmentGroup.query
        if equipment_group_id is not None:
            eg_query = eg_query.filter(EquipmentGroup.id == equipment_group_id)
        if not all_versions:
            current_version_id = get_current_db_version_id()
            if current_version_id is not None:
                eg_query = eg_query.filter(
                    EquipmentGroup.database_version_id == current_version_id
                )
            else:
                eg_query = eg_query.filter(
                    EquipmentGroup.database_version_id.is_(None)
                )
        allowed_eg_ids = {
            row.id for row in eg_query.with_entities(EquipmentGroup.id).all()
        }
        if not allowed_eg_ids:
            return 0

    def _load(model):
        q = model.query.filter(
            model.year_number >= _start,
            model.year_number <= _end,
        )
        if allowed_eg_ids is not None:
            q = q.filter(model.equipment_group_id.in_(allowed_eg_ids))
        return {
            (r.equipment_group_id, r.year_number): r
            for r in q.all()
            if r.equipment_group_id is not None and r.year_number is not None
        }

    fuel_params = _load(EquipmentGroupFuelParam)
    extra_params = _load(EquipmentGroupExtraFuelParam)
    costs = _load(EquipmentGroupSpecificFuelCost)
    prices_existing = _load(EquipmentGroupSpecificFuelPrice)

    keys = sorted(
        set(fuel_params)
        | set(extra_params)
        | set(costs)
        | set(prices_existing)
    )
    if not keys:
        return 0

    version_id = get_current_db_version_id()
    updates_count = 0

    with db.session.no_autoflush:
        for eg_id, year_number in keys:
            price = prices_existing.get((eg_id, year_number))
            if price is None:
                price = EquipmentGroupSpecificFuelPrice(
                    equipment_group_id=eg_id,
                    year_number=year_number,
                    database_version_id=version_id,
                )
                set_db_version_on_create(price)
                db.session.add(price)
                prices_existing[(eg_id, year_number)] = price

            fill_specific_fuel_price_from_calc(
                price,
                fuel_params.get((eg_id, year_number)),
                extra_params.get((eg_id, year_number)),
                costs.get((eg_id, year_number)),
            )
            updates_count += 1

    if updates_count and commit:
        db.session.commit()

    return updates_count
