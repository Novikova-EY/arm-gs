# -*- coding: utf-8 -*-
"""
Сохранение параметров таблиц Удельные показатели, Дополнительные параметры топлива,
Стоимость, Цена со страницы equipment_group_edit.
Ключи формы: extra_param_{year}_{attr}, consumption_param_{year}_{attr},
cost_param_{year}_{attr}, price_param_{year}_{attr}.
"""
from decimal import Decimal, InvalidOperation

from app.common.services.help_services import values_equal_by_display_precision
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
    EquipmentGroupSpecificFuelCost,
)
from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
    EquipmentGroupSpecificFuelPrice,
)
from app.fuel.services.equipment_group_extra_fuel_params_services import (
    EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS,
)
from app.fuel.services.equipment_group_details_specific_params_services import (
    COST_ATTRS,
    PRICE_ATTRS,
)
from app.fuel.services.equipment_group_specific_fuel_consumption_services import (
    SPECIFIC_FUEL_CONSUMPTION_COLUMNS,
)

# Все числовые параметры Consumption (включая y_calc, btp_calc и т.д.) редактируемы и сохраняются в БД
CONSUMPTION_EDITABLE_ATTRS = [
    attr for attr, _, is_num in SPECIFIC_FUEL_CONSUMPTION_COLUMNS
    if is_num
]


def _parse_int_for_k(value):
    """Парсит значение для поля k (Integer)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "—", "-", "–"):
        return None
    try:
        return int(round(float(s.replace(",", "."))))
    except (ValueError, TypeError, InvalidOperation):
        return None


def _parse_decimal(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "—", "-", "–"):
        return None
    try:
        return Decimal(s.replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _format_val(v):
    """Приведение значения к строке для лога."""
    if v is None:
        return "—"
    return str(v)


def _update_params_from_form(
    equipment_group_id,
    form_data,
    start_year,
    end_year,
    prefix,
    model_class,
    attrs_list,
    table_name,
    rounding_digits=1,
):
    """Обновляет записи из формы. Возвращает (count, [(table, year, attr, old, new), ...])."""
    version_id = get_current_db_version_id()
    # Ищем по (equipment_group_id, year_number): у Price/Cost/Consumption/Extra
    # один UniqueConstraint на эту пару, без database_version_id — не фильтруем по версии,
    # иначе записи с database_version_id=NULL не найдём и получим IntegrityError при создании дубликата.
    existing = {
        r.year_number: r
        for r in model_class.query.filter_by(equipment_group_id=equipment_group_id).all()
    }
    change_details = []
    for year in range(start_year, end_year + 1):
        rec = existing.get(year)
        for attr in attrs_list:
            if not hasattr(model_class, attr):
                continue
            key = f"{prefix}_{year}_{attr}"
            raw = form_data.get(key)
            if attr == "k":
                val = _parse_int_for_k(raw)
            else:
                val = _parse_decimal(raw)
            if rec is None:
                if val is not None:
                    rec = model_class(
                        equipment_group_id=equipment_group_id,
                        year_number=year,
                        database_version_id=version_id,
                    )
                    set_db_version_on_create(rec)
                    db.session.add(rec)
                    existing[year] = rec
            if rec is not None:
                # Обновить database_version_id при необходимости (миграция записей с NULL)
                if (
                    hasattr(rec, "database_version_id")
                    and rec.database_version_id is None
                    and version_id is not None
                ):
                    rec.database_version_id = version_id
                old_val = getattr(rec, attr, None)
                is_unchanged = values_equal_by_display_precision(old_val, val, rounding_digits)
                if not is_unchanged:
                    setattr(rec, attr, val)
                    change_details.append(
                        (table_name, year, attr, _format_val(old_val), _format_val(val))
                    )
    return len(change_details), change_details


TABLE_EXTRA = "Дополнительные параметры топлива"
TABLE_CONSUMPTION = "Удельные показатели"
TABLE_COST = "Стоимость"
TABLE_PRICE = "Цена"


def update_equipment_group_extra_params_from_form(
    equipment_group_id, form_data, start_year, end_year,
    rounding_digits_table3=1,
):
    """Обновляет EquipmentGroupExtraFuelParam. Ключи: extra_param_{year}_{attr}."""
    count, details = _update_params_from_form(
        equipment_group_id, form_data, start_year, end_year,
        "extra_param", EquipmentGroupExtraFuelParam, EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS,
        TABLE_EXTRA,
        rounding_digits=rounding_digits_table3,
    )
    return True, "Доп. параметры топлива сохранены." if count else "Изменений нет.", details


def update_equipment_group_consumption_from_form(
    equipment_group_id, form_data, start_year, end_year,
    rounding_digits_table4=1,
):
    """Обновляет EquipmentGroupSpecificFuelConsumption (y, btp, sntp, bk, snk)."""
    count, details = _update_params_from_form(
        equipment_group_id, form_data, start_year, end_year,
        "consumption_param", EquipmentGroupSpecificFuelConsumption, CONSUMPTION_EDITABLE_ATTRS,
        TABLE_CONSUMPTION,
        rounding_digits=rounding_digits_table4,
    )
    return True, "Удельные показатели сохранены." if count else "Изменений нет.", details


def update_equipment_group_cost_from_form(
    equipment_group_id, form_data, start_year, end_year,
    rounding_digits_table4=1,
):
    """Обновляет EquipmentGroupSpecificFuelCost. Ключи: cost_param_{year}_{attr}."""
    count, details = _update_params_from_form(
        equipment_group_id, form_data, start_year, end_year,
        "cost_param", EquipmentGroupSpecificFuelCost, COST_ATTRS,
        TABLE_COST,
        rounding_digits=rounding_digits_table4,
    )
    return True, "Стоимость сохранена." if count else "Изменений нет.", details


def update_equipment_group_price_from_form(
    equipment_group_id, form_data, start_year, end_year,
    rounding_digits_table4=1,
):
    """Обновляет EquipmentGroupSpecificFuelPrice. Ключи: price_param_{year}_{attr}."""
    count, details = _update_params_from_form(
        equipment_group_id, form_data, start_year, end_year,
        "price_param", EquipmentGroupSpecificFuelPrice, PRICE_ATTRS,
        TABLE_PRICE,
        rounding_digits=rounding_digits_table4,
    )
    return True, "Цена сохранена." if count else "Изменений нет.", details


def recalculate_specific_fuel_prices_for_equipment_group(
    equipment_group_id, start_year, end_year,
):
    """
    Пересчитывает поля xxx_c в EquipmentGroupSpecificFuelPrice по формулам
    (cost / quantity) для всех лет в диапазоне.
    Вызывать после изменения cost, fuel_param или extra_fuel_param.
    """
    from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
        EquipmentGroupExtraFuelParam,
    )
    from app.fuel.models.fue_equipment_group_fuel_param_model import (
        EquipmentGroupFuelParam,
    )
    from app.fuel.services.equipment_group_specific_fuel_price_calc_services import (
        fill_specific_fuel_price_from_calc,
    )

    fuel_params = {
        r.year_number: r
        for r in EquipmentGroupFuelParam.query.filter_by(
            equipment_group_id=equipment_group_id,
        ).filter(
            EquipmentGroupFuelParam.year_number >= start_year,
            EquipmentGroupFuelParam.year_number <= end_year,
        ).all()
    }
    extra_params = {
        r.year_number: r
        for r in EquipmentGroupExtraFuelParam.query.filter_by(
            equipment_group_id=equipment_group_id,
        ).filter(
            EquipmentGroupExtraFuelParam.year_number >= start_year,
            EquipmentGroupExtraFuelParam.year_number <= end_year,
        ).all()
    }
    costs = {
        r.year_number: r
        for r in EquipmentGroupSpecificFuelCost.query.filter_by(
            equipment_group_id=equipment_group_id,
        ).filter(
            EquipmentGroupSpecificFuelCost.year_number >= start_year,
            EquipmentGroupSpecificFuelCost.year_number <= end_year,
        ).all()
    }

    price_list = EquipmentGroupSpecificFuelPrice.query.filter_by(
        equipment_group_id=equipment_group_id,
    ).filter(
        EquipmentGroupSpecificFuelPrice.year_number >= start_year,
        EquipmentGroupSpecificFuelPrice.year_number <= end_year,
    ).all()

    for price_rec in price_list:
        year = price_rec.year_number
        if year is None:
            continue
        fill_specific_fuel_price_from_calc(
            price_rec,
            fuel_params.get(year),
            extra_params.get(year),
            costs.get(year),
        )
