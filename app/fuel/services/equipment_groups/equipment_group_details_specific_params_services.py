# -*- coding: utf-8 -*-
"""
Спецификация и построение таблиц «Удельные показатели», «Стоимость», «Цена»
на странице equipment_group_details.
Отдельные таблицы по моделям: EquipmentGroupSpecificFuelConsumption,
EquipmentGroupSpecificFuelCost, EquipmentGroupSpecificFuelPrice.
"""
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    SPECIFIC_FUEL_CONSUMPTION_COLUMNS,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_write_services import (
    CONSUMPTION_FORM_INPUT_ATTRS,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_cost_services import (
    SPECIFIC_FUEL_COST_COLUMNS,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_price_services import (
    SPECIFIC_FUEL_PRICE_COLUMNS,
)

# Формулы расчета для отображения во всплывающей подсказке (attr -> формула)
CONSUMPTION_FORMULAS = {
    "snk_calc": "snk_calc = SNK из строки параметров топлива (EquipmentGroupFuelParam)",
    "y_calc": "y_calc = EWTP / QOTR * 1000",
    "btp_calc": (
        "btp_calc = EURT - K * (1 - EWTP / E) * 100"
    ),
    "sntp_calc": (
        "sntp_calc = [EOTP - (E - EWTP) * (1 - SNK / 100)] / EWTP"
    ),
    "bk_calc": (
        "bk_calc = [EUST - EWTP * sntp_calc * btp_calc / 1000] / "
        "[(E - EWTP) * (1 - SNK / 100)] * 1000"
    ),
}

# Consumption: сначала вводимые k, y, btp, sntp, bk, snk; затем расчётные *_calc (только просмотр в UI)
_INPUT_ATTR_SET = frozenset(CONSUMPTION_FORM_INPUT_ATTRS)
CONSUMPTION_INPUT_SPEC = [
    (attr, label)
    for attr, label, _is_num in SPECIFIC_FUEL_CONSUMPTION_COLUMNS
    if attr in _INPUT_ATTR_SET
]
CONSUMPTION_CALC_SPEC = [
    (attr, label)
    for attr, label, is_numeric in SPECIFIC_FUEL_CONSUMPTION_COLUMNS
    if is_numeric and attr.endswith("_calc")
]
CONSUMPTION_SPEC = CONSUMPTION_INPUT_SPEC + CONSUMPTION_CALC_SPEC
CONSUMPTION_ATTRS = [attr for attr, _ in CONSUMPTION_SPEC]

# Cost: только числовые параметры
COST_SPEC = [
    (attr, label) for attr, label, is_numeric in SPECIFIC_FUEL_COST_COLUMNS
    if is_numeric
]
COST_ATTRS = [attr for attr, _ in COST_SPEC]

# Price: только расчетные параметры (_calc)
PRICE_SPEC = [
    (attr, label) for attr, label, is_numeric in SPECIFIC_FUEL_PRICE_COLUMNS
    if is_numeric and attr.endswith("_calc")
]
PRICE_ATTRS = [attr for attr, _ in PRICE_SPEC]


def _build_grid(data_by_year, spec, years_range):
    """Строит grid: [(label, {year: value}), ...]."""
    result = []
    for attr, label in spec:
        values_by_year = {}
        for y in years_range:
            rec = data_by_year.get(y)
            values_by_year[y] = getattr(rec, attr, None) if rec else None
        result.append((label, values_by_year))
    return result


def build_table4_consumption_grid(
    consumption_by_year, years_range, fuel_params_by_year=None, group=None
):
    """
    Строит grid для EquipmentGroupSpecificFuelConsumption.
    Все значения (включая y_calc, btp_calc и т.д.) берутся из БД (consumption_by_year),
    без пересчета при загрузке страницы.
    Параметры fuel_params_by_year и group оставлены для обратной совместимости вызовов.
    """
    result = []
    for attr, label in CONSUMPTION_SPEC:
        values_by_year = {}
        for y in years_range:
            rec = consumption_by_year.get(y)
            values_by_year[y] = getattr(rec, attr, None) if rec else None
        # Жирным — примечание из модели (COLUMN_LABELS)
        display_label = EquipmentGroupSpecificFuelConsumption.COLUMN_LABELS.get(
            attr, label
        )
        result.append((display_label, values_by_year))
    return result


def build_table4_cost_grid(cost_by_year, years_range):
    """Строит grid для EquipmentGroupSpecificFuelCost."""
    return _build_grid(cost_by_year, COST_SPEC, years_range)


def build_table4_price_grid(price_by_year, years_range):
    """
    Строит grid для EquipmentGroupSpecificFuelPrice (только _calc).
    Значения берутся из rec._price_calc для _calc атрибутов.
    """
    result = []
    for attr, label in PRICE_SPEC:
        values_by_year = {}
        for y in years_range:
            rec = price_by_year.get(y)
            if rec and attr.endswith("_calc"):
                price_calc = getattr(rec, "_price_calc", None) or {}
                base_attr = attr[:-5]  # gaz_c_calc -> gaz_c
                values_by_year[y] = price_calc.get(base_attr)
            else:
                values_by_year[y] = getattr(rec, attr, None) if rec else None
        result.append((label, values_by_year))
    return result
