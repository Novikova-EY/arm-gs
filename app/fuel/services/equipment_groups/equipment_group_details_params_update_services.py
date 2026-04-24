# -*- coding: utf-8 -*-
"""
Orchestration layer: сохранение таблиц со страницы equipment_group_edit.

Собирает form_data, вызывает write-services и recalc-сервисы;
возвращает (success, message, change_details) для UI и журнала.

Удельные: в форму попадают только CONSUMPTION_EDITABLE_ATTRS (k, y, btp, sntp, bk, snk),
без *_calc. После изменения входных полей — recalculate_all_specific_fuel_consumption_calc.

Цена: поля xxx_c не вводятся с формы; после сохранения прочих таблиц в общем потоке
вызывается recalculate_specific_fuel_prices_for_equipment_group.
"""
from __future__ import annotations

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_write_services import (
    EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS,
    save_equipment_group_extra_fuel_params_bulk,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_recalc_services import (
    recalculate_all_specific_fuel_consumption_calc,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_write_services import (
    CONSUMPTION_EDITABLE_ATTRS,
    save_specific_fuel_consumption_bulk,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_cost_write_services import (
    SPECIFIC_FUEL_COST_EDITABLE_ATTRS,
    save_specific_fuel_cost_bulk,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_price_recalc_services import (
    recalculate_specific_fuel_prices_for_equipment_group,
)

TABLE_EXTRA = "Дополнительные параметры топлива"
TABLE_CONSUMPTION = "Удельные показатели"
TABLE_COST = "Стоимость"
TABLE_PRICE = "Цена"


def _extract_values_by_year(
    form_data,
    *,
    prefix: str,
    attrs: list[str],
    start_year: int,
    end_year: int,
) -> dict[int, dict]:
    """Собирает сырые значения формы по годам (только перечисленные attrs)."""
    values_by_year: dict[int, dict] = {}
    for year in range(start_year, end_year + 1):
        year_values: dict = {}
        for attr in attrs:
            key = f"{prefix}_{year}_{attr}"
            year_values[attr] = form_data.get(key)
        values_by_year[year] = year_values
    return values_by_year


def _convert_bulk_result_to_details(
    result: dict[int, dict],
    table_name: str,
) -> tuple[int, list[tuple]]:
    """Преобразует change_details write-слоя в список кортежей для журнала."""
    details: list[tuple] = []
    changed_count = 0

    for year, payload in sorted(result.items()):
        change_details = payload.get("change_details") or {}
        for attr, diff in change_details.items():
            details.append(
                (
                    table_name,
                    year,
                    attr,
                    diff.get("old"),
                    diff.get("new"),
                )
            )
            changed_count += 1

    return changed_count, details


def update_equipment_group_extra_params_from_form(
    equipment_group_id,
    form_data,
    start_year,
    end_year,
    rounding_digits_table3=1,
):
    values_by_year = _extract_values_by_year(
        form_data,
        prefix="extra_param",
        attrs=EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS,
        start_year=start_year,
        end_year=end_year,
    )

    result = save_equipment_group_extra_fuel_params_bulk(
        equipment_group_id=equipment_group_id,
        values_by_year=values_by_year,
        database_version_id=get_current_db_version_id(),
        commit=False,
        rounding_digits=rounding_digits_table3,
    )

    count, details = _convert_bulk_result_to_details(result, TABLE_EXTRA)
    return (
        True,
        "Доп. параметры топлива сохранены." if count else "Изменений нет.",
        details,
    )


def update_equipment_group_consumption_from_form(
    equipment_group_id,
    form_data,
    start_year,
    end_year,
    rounding_digits_table4=1,
):
    values_by_year = _extract_values_by_year(
        form_data,
        prefix="consumption_param",
        attrs=CONSUMPTION_EDITABLE_ATTRS,
        start_year=start_year,
        end_year=end_year,
    )

    result = save_specific_fuel_consumption_bulk(
        equipment_group_id=equipment_group_id,
        values_by_year=values_by_year,
        database_version_id=get_current_db_version_id(),
        commit=False,
        rounding_digits=rounding_digits_table4,
    )

    count, details = _convert_bulk_result_to_details(result, TABLE_CONSUMPTION)

    if count > 0:
        db.session.flush()
        recalculate_all_specific_fuel_consumption_calc(
            equipment_group_id=equipment_group_id,
            start_year=start_year,
            end_year=end_year,
            commit=False,
        )
    return (
        True,
        "Удельные показатели сохранены." if count else "Изменений нет.",
        details,
    )


def update_equipment_group_cost_from_form(
    equipment_group_id,
    form_data,
    start_year,
    end_year,
    rounding_digits_table4=1,
):
    values_by_year = _extract_values_by_year(
        form_data,
        prefix="cost_param",
        attrs=SPECIFIC_FUEL_COST_EDITABLE_ATTRS,
        start_year=start_year,
        end_year=end_year,
    )

    result = save_specific_fuel_cost_bulk(
        equipment_group_id=equipment_group_id,
        values_by_year=values_by_year,
        database_version_id=get_current_db_version_id(),
        commit=False,
        rounding_digits=rounding_digits_table4,
    )

    count, details = _convert_bulk_result_to_details(result, TABLE_COST)
    return (
        True,
        "Стоимость сохранена." if count else "Изменений нет.",
        details,
    )


def recalculate_prices_for_equipment_group(
    equipment_group_id: int,
    start_year: int,
    end_year: int,
    *,
    commit: bool = False,
) -> tuple[bool, str, list]:
    """
    Пересчёт удельной цены (xxx_c) для группы за диапазон лет.
    Не читает price_param_* с формы.
    """
    db.session.flush()
    n = recalculate_specific_fuel_prices_for_equipment_group(
        equipment_group_id,
        start_year,
        end_year,
        commit=commit,
    )
    msg = "Цена пересчитана по формулам." if n else "Изменений нет."
    return True, msg, []


def update_equipment_group_price_from_form(
    equipment_group_id,
    form_data,
    start_year,
    end_year,
    rounding_digits_table4=1,
):
    """
    Поля цены из формы не сохраняем: xxx_c пересчитываются по cost и количествам
    топлива (см. equipment_group_specific_fuel_price_calc_services).
    """
    _ = (form_data, rounding_digits_table4)
    return recalculate_prices_for_equipment_group(
        equipment_group_id,
        start_year,
        end_year,
        commit=False,
    )


def update_equipment_group_all_details_params(
    equipment_group_id,
    form_data,
    start_year,
    end_year,
    *,
    rounding_digits_table3=1,
    rounding_digits_table4=1,
):
    """
    Единая точка orchestration для доп. параметров, удельных, стоимости и цены
    (без EquipmentGroupFuelParam — тот блок через update_equipment_group_fuel_params_from_form).
    Возвращает список нетривиальных сообщений для объединения с flash.
    """
    messages: list[str] = []
    details: list[tuple] = []
    all_ok = True

    ok1, msg1, det1 = update_equipment_group_extra_params_from_form(
        equipment_group_id,
        form_data,
        start_year,
        end_year,
        rounding_digits_table3=rounding_digits_table3,
    )
    all_ok = all_ok and ok1
    if ok1 and msg1 != "Изменений нет.":
        messages.append(msg1)
    details.extend(det1)

    ok2, msg2, det2 = update_equipment_group_consumption_from_form(
        equipment_group_id,
        form_data,
        start_year,
        end_year,
        rounding_digits_table4=rounding_digits_table4,
    )
    all_ok = all_ok and ok2
    if ok2 and msg2 != "Изменений нет.":
        messages.append(msg2)
    details.extend(det2)

    ok3, msg3, det3 = update_equipment_group_cost_from_form(
        equipment_group_id,
        form_data,
        start_year,
        end_year,
        rounding_digits_table4=rounding_digits_table4,
    )
    all_ok = all_ok and ok3
    if ok3 and msg3 != "Изменений нет.":
        messages.append(msg3)
    details.extend(det3)

    ok4, msg4, det4 = update_equipment_group_price_from_form(
        equipment_group_id,
        form_data,
        start_year,
        end_year,
        rounding_digits_table4=rounding_digits_table4,
    )
    all_ok = all_ok and ok4
    if ok4 and msg4 != "Изменений нет.":
        messages.append(msg4)
    details.extend(det4)

    return all_ok, messages, details
