# -*- coding: utf-8 -*-
"""
Пересчет расчетных (_calc) полей EquipmentGroupSpecificFuelConsumption
по данным EquipmentGroupFuelParam.

Вынесено из equipment_group_fuel_params_services.py, чтобы:
- display/query service не содержал write/recalc logic;
- пересчет удельных был отдельным maintenance/calculation service.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_calc_services import (
    calc_y_calc,
    calc_btp_calc,
    calc_sntp_calc,
    calc_bk_calc,
)


def recalculate_all_specific_fuel_consumption_calc(
    year: int | None = None,
    *,
    equipment_group_id: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    commit: bool = True,
) -> int:
    """
    Пересчитывает y_calc, btp_calc, sntp_calc, bk_calc, snk_calc
    для EquipmentGroupSpecificFuelConsumption по данным EquipmentGroupFuelParam.

    Использование:
    - после импорта fuel params;
    - после импорта/обновления данных БД Топливо;
    - при необходимости сервисного пересчета.

    :param year: если задан, пересчитывать только этот год (глобальный режим)
    :param equipment_group_id: если задан, ограничить группу оборудования
        (year не должен быть задан; можно задать start_year/end_year)
    :param start_year, end_year: вместе с equipment_group_id — диапазон лет
    :param commit: False при вызове из orchestrator до общего commit
    :return: количество созданных/обновленных записей
    """
    current_version_id = get_current_db_version_id()

    query = EquipmentGroupFuelParam.query
    if year is not None:
        query = query.filter(EquipmentGroupFuelParam.year_number == year)
    else:
        if equipment_group_id is not None:
            query = query.filter(
                EquipmentGroupFuelParam.equipment_group_id == equipment_group_id
            )
        if start_year is not None:
            query = query.filter(EquipmentGroupFuelParam.year_number >= start_year)
        if end_year is not None:
            query = query.filter(EquipmentGroupFuelParam.year_number <= end_year)

    if current_version_id is not None:
        query = query.filter(
            EquipmentGroupFuelParam.database_version_id == current_version_id
        )
    else:
        query = query.filter(
            EquipmentGroupFuelParam.database_version_id.is_(None)
        )

    params = query.all()
    if not params:
        return 0

    # Группировка по ключу записи удельных
    by_key = defaultdict(list)
    for p in params:
        key = (p.equipment_group_id, p.year_number, p.database_version_id)
        by_key[key].append(p)

    updates_count = 0
    Q6 = Decimal("0.000001")

    def q6(val):
        if val is None:
            return None
        try:
            d = Decimal(str(val))
            return d.quantize(Q6)
        except (InvalidOperation, TypeError):
            return val

    for (equipment_group_id, year_number, version_id), param_list in by_key.items():
        # По uq дубликатов быть не должно, берем первую запись
        param = param_list[0]

        consumption = EquipmentGroupSpecificFuelConsumption.query.filter_by(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
            database_version_id=version_id,
        ).first()

        coeff_k = (
            consumption.k
            if (consumption is not None and consumption.k is not None)
            else None
        )

        y_calc_val = calc_y_calc(param)
        btp_calc_val = calc_btp_calc(param, coeff_k)
        sntp_calc_val = calc_sntp_calc(param)
        bk_calc_val = calc_bk_calc(param, btp_calc_val, sntp_calc_val)
        snk_calc_val = getattr(param, "snk", None)

        y_calc_val = q6(y_calc_val)
        btp_calc_val = q6(btp_calc_val)
        sntp_calc_val = q6(sntp_calc_val)
        bk_calc_val = q6(bk_calc_val)
        snk_calc_val = q6(snk_calc_val) if snk_calc_val is not None else None

        if consumption is None:
            consumption = EquipmentGroupSpecificFuelConsumption(
                equipment_group_id=equipment_group_id,
                year_number=year_number,
                database_version_id=version_id,
                y_calc=y_calc_val,
                btp_calc=btp_calc_val,
                sntp_calc=sntp_calc_val,
                bk_calc=bk_calc_val,
                snk_calc=snk_calc_val,
            )
            set_db_version_on_create(consumption)
            db.session.add(consumption)
            updates_count += 1
        else:
            changed = False

            if consumption.y_calc != y_calc_val:
                consumption.y_calc = y_calc_val
                changed = True
            if consumption.btp_calc != btp_calc_val:
                consumption.btp_calc = btp_calc_val
                changed = True
            if consumption.sntp_calc != sntp_calc_val:
                consumption.sntp_calc = sntp_calc_val
                changed = True
            if consumption.bk_calc != bk_calc_val:
                consumption.bk_calc = bk_calc_val
                changed = True
            if consumption.snk_calc != snk_calc_val:
                consumption.snk_calc = snk_calc_val
                changed = True

            if changed:
                updates_count += 1

    if updates_count and commit:
        db.session.commit()

    return updates_count
