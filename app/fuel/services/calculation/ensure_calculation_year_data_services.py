# -*- coding: utf-8 -*-
"""
Автозаполнение расчётного года на /fuel/calculation.

Если для выбранного расчётного года ещё нет строк на страницах
«ТЭП» / «формулы» / «удельные показатели», копирует данные с базового года
той же логикой, что кнопки «Добавить год» на этих страницах.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import distinct

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    copy_heat_fuel_param_columns_for_filters,
)
from app.fuel.services.calculation.fuel_calculation_specific_consumption_edit_data_services import (
    copy_specific_fuel_consumption_between_years_for_filters,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_formula_write_services import (
    copy_fuel_formulas_between_years_for_filters,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    get_equipment_group_ids_for_fuel_params_filters,
)


def _eg_ids_with_year(
    model,
    eg_ids: list[int],
    year_number: int,
    version_id: int | None,
) -> set[int]:
    if not eg_ids:
        return set()
    q = db.session.query(distinct(model.equipment_group_id)).filter(
        model.equipment_group_id.in_(eg_ids),
        model.year_number == int(year_number),
    )
    if hasattr(model, "database_version_id"):
        if version_id is not None:
            q = q.filter(model.database_version_id == version_id)
        else:
            q = q.filter(model.database_version_id.is_(None))
    return {int(gid) for (gid,) in q.all() if gid is not None}


def _needs_year_copy(
    model,
    eg_ids: list[int],
    source_year: int,
    target_year: int,
    version_id: int | None,
) -> bool:
    """True, если есть группы с данными за базовый год без строки за расчётный."""
    with_source = _eg_ids_with_year(model, eg_ids, source_year, version_id)
    if not with_source:
        return False
    with_target = _eg_ids_with_year(model, eg_ids, target_year, version_id)
    return bool(with_source - with_target)


def ensure_calculation_year_data_from_base(
    filters: dict[str, Any] | None,
    *,
    base_year: int,
    calc_year: int,
) -> dict[str, Any]:
    """
    При необходимости копирует ТЭП / формулы / удельные показатели с base_year на calc_year.

    Возвращает словарь со счётчиками и флагом ``did_anything``.
    Коммит не выполняет — вызывающая сторона делает ``db.session.commit()``.
    """
    source = int(base_year)
    target = int(calc_year)
    empty = {
        "did_anything": False,
        "base_year": source,
        "calc_year": target,
        "heat": None,
        "formulas": None,
        "specific": None,
    }
    if source == target:
        return empty

    f = {**(filters or {})}
    f.pop("page", None)
    filter_start = min(source, target)
    filter_end = max(source, target)

    eg_ids = get_equipment_group_ids_for_fuel_params_filters(
        f, start_year=filter_start, end_year=filter_end
    )
    if not eg_ids:
        return empty

    version_id = get_current_db_version_id()
    result = {**empty, "heat": (0, 0, 0), "formulas": (0, 0, 0), "specific": (0, 0, 0)}

    if _needs_year_copy(
        EquipmentGroupFuelParam, eg_ids, source, target, version_id
    ):
        result["heat"] = copy_heat_fuel_param_columns_for_filters(
            f,
            filter_start_year=filter_start,
            filter_end_year=filter_end,
            source_year_number=source,
            target_year_numbers=[target],
        )
        if result["heat"][0]:
            result["did_anything"] = True

    if _needs_year_copy(
        EquipmentGroupFuelFormula, eg_ids, source, target, version_id
    ):
        result["formulas"] = copy_fuel_formulas_between_years_for_filters(
            f,
            filter_start_year=filter_start,
            filter_end_year=filter_end,
            source_year_number=source,
            target_year_numbers=[target],
        )
        if result["formulas"][0]:
            result["did_anything"] = True

    if _needs_year_copy(
        EquipmentGroupSpecificFuelConsumption, eg_ids, source, target, version_id
    ):
        result["specific"] = copy_specific_fuel_consumption_between_years_for_filters(
            f,
            filter_start_year=filter_start,
            filter_end_year=filter_end,
            source_year=source,
            target_year=target,
        )
        if result["specific"][0]:
            result["did_anything"] = True

    return result
