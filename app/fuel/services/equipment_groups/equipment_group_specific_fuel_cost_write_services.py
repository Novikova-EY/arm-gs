# -*- coding: utf-8 -*-
"""
Write/update-слой для EquipmentGroupSpecificFuelCost.

Список числовых полей согласован с SPECIFIC_FUEL_COST_COLUMNS в
equipment_group_specific_fuel_cost_services.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.common.services.help_services import (
    format_number_trim_trailing,
    values_equal_by_display_precision,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
    EquipmentGroupSpecificFuelCost,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_cost_services import (
    SPECIFIC_FUEL_COST_COLUMNS,
)

SPECIFIC_FUEL_COST_EDITABLE_ATTRS = [
    attr for attr, _, is_num in SPECIFIC_FUEL_COST_COLUMNS
    if is_num
]

NUMERIC_ATTRS = frozenset(SPECIFIC_FUEL_COST_EDITABLE_ATTRS)


def _format_val(value):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (Decimal, int, float)):
        return format_number_trim_trailing(value)
    if isinstance(value, str):
        return value.strip() or "—"
    return str(value)


def _parse_cost_value(attr_name: str, raw_value):
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            return None

    if attr_name in NUMERIC_ATTRS:
        try:
            return Decimal(str(raw_value).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return None

    return raw_value


def update_specific_fuel_cost_fields(
    *,
    row: EquipmentGroupSpecificFuelCost,
    values: dict,
    rounding_digits: int = 1,
) -> dict:
    change_details = {}

    for attr_name, raw_value in values.items():
        if attr_name not in NUMERIC_ATTRS:
            continue
        if not hasattr(row, attr_name):
            continue

        new_value = _parse_cost_value(attr_name, raw_value)
        old_value = getattr(row, attr_name, None)

        changed = not values_equal_by_display_precision(
            old_value,
            new_value,
            display_digits=rounding_digits,
        )

        if changed:
            setattr(row, attr_name, new_value)
            change_details[attr_name] = {
                "old": _format_val(old_value),
                "new": _format_val(new_value),
            }

    return change_details


def save_specific_fuel_cost_for_year(
    *,
    equipment_group_id: int,
    year_number: int,
    values: dict,
    database_version_id: int | None = None,
    commit: bool = False,
    rounding_digits: int = 1,
) -> tuple[EquipmentGroupSpecificFuelCost | None, dict]:
    effective_db_version = database_version_id
    if effective_db_version is None:
        effective_db_version = get_current_db_version_id()

    row = (
        EquipmentGroupSpecificFuelCost.query.filter_by(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        ).first()
    )

    filtered = {k: v for k, v in values.items() if k in NUMERIC_ATTRS}

    if row is None:
        has_any = False
        for attr in SPECIFIC_FUEL_COST_EDITABLE_ATTRS:
            if attr not in filtered:
                continue
            if _parse_cost_value(attr, filtered.get(attr)) is not None:
                has_any = True
                break
        if not has_any:
            return None, {}

        row = EquipmentGroupSpecificFuelCost(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
            database_version_id=effective_db_version,
        )
        set_db_version_on_create(row)
        db.session.add(row)
        db.session.flush()

    if (
        hasattr(row, "database_version_id")
        and row.database_version_id is None
        and effective_db_version is not None
    ):
        row.database_version_id = effective_db_version

    change_details = update_specific_fuel_cost_fields(
        row=row,
        values=filtered,
        rounding_digits=rounding_digits,
    )

    if commit:
        db.session.commit()

    return row, change_details


def save_specific_fuel_cost_bulk(
    *,
    equipment_group_id: int,
    values_by_year: dict[int, dict],
    database_version_id: int | None = None,
    commit: bool = False,
    rounding_digits: int = 1,
) -> dict[int, dict]:
    result = {}

    for year_number, values in values_by_year.items():
        row, change_details = save_specific_fuel_cost_for_year(
            equipment_group_id=equipment_group_id,
            year_number=int(year_number),
            values=values,
            database_version_id=database_version_id,
            commit=False,
            rounding_digits=rounding_digits,
        )
        if row is None and not change_details:
            continue
        result[int(year_number)] = {
            "row": row,
            "change_details": change_details,
        }

    if commit:
        db.session.commit()

    return result
