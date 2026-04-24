# -*- coding: utf-8 -*-
"""
Write/update-слой для EquipmentGroupFuelFormula.

Импорт Excel остаётся в import_equipment_group_fuel_formula_services.py; здесь —
единый create/update для UI и возможной унификации с импортом.

Выбор формулы для расчёта года — только в equipment_group_fuel_calculation_services.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.common.services.help_services import values_equal_by_display_precision
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_formula_model import (
    EquipmentGroupFuelFormula,
)

# Поля, которые могут приходить из формы / API (включая ключ строки)
FORMULA_EDITABLE_ATTRS = [
    "name",
    "formtxt",
    "numb1120",
    "numb1",
    "variant_number",
]

# Поля, допустимые для обновления уже существующей строки (год/вариант задают identity)
FORMULA_UPDATABLE_ATTRS = frozenset(["name", "formtxt", "numb1120", "numb1"])


def _format_val(value):
    if value is None:
        return "—"
    return str(value)


def _parse_int_field(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            return None
    try:
        return int(round(float(str(raw_value).replace(",", "."))))
    except (ValueError, TypeError):
        return None


def _parse_formula_value(attr_name: str, raw_value):
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            return None

    if attr_name in ("numb1120", "variant_number"):
        return _parse_int_field(raw_value)

    if attr_name == "numb1":
        try:
            return Decimal(str(raw_value).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return None

    if attr_name == "name":
        return None if raw_value is None else str(raw_value).strip() or None

    if attr_name == "formtxt":
        return None if raw_value is None else str(raw_value)

    return raw_value


def _field_values_equal(attr_name: str, old_val, new_val, display_digits: int = 6) -> bool:
    if attr_name in ("name", "formtxt"):
        o = None if old_val is None else str(old_val).strip()
        n = None if new_val is None else str(new_val).strip()
        if o == "":
            o = None
        if n == "":
            n = None
        return o == n
    if attr_name == "numb1120":
        return old_val == new_val
    if attr_name == "numb1":
        return values_equal_by_display_precision(old_val, new_val, display_digits)
    return old_val == new_val


def get_or_create_equipment_group_fuel_formula(
    *,
    equipment_group_id: int,
    year_number: int,
    variant_number: int = 0,
    database_version_id: int | None = None,
) -> EquipmentGroupFuelFormula:
    """
    Одна строка на (equipment_group_id, year_number, variant_number, database_version_id),
    как в import_equipment_group_fuel_formula_from_excel.
    """
    effective_db_version = database_version_id
    if effective_db_version is None:
        effective_db_version = get_current_db_version_id()

    vn = int(variant_number or 0)

    row = (
        EquipmentGroupFuelFormula.query.filter_by(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
            variant_number=vn,
            database_version_id=effective_db_version,
        ).first()
    )
    if row:
        return row

    row = EquipmentGroupFuelFormula(
        equipment_group_id=equipment_group_id,
        year_number=year_number,
        variant_number=vn,
        database_version_id=effective_db_version,
    )
    set_db_version_on_create(row)
    db.session.add(row)
    db.session.flush()
    return row


def update_equipment_group_fuel_formula_fields(
    *,
    row: EquipmentGroupFuelFormula,
    values: dict,
    display_digits: int = 6,
) -> dict:
    """
    Обновляет только FORMULA_UPDATABLE_ATTRS (год/вариант не меняются — это другая строка).
    """
    change_details = {}

    for attr_name, raw_value in values.items():
        if attr_name not in FORMULA_UPDATABLE_ATTRS:
            continue
        if not hasattr(row, attr_name):
            continue

        new_value = _parse_formula_value(attr_name, raw_value)
        old_value = getattr(row, attr_name, None)

        if _field_values_equal(attr_name, old_value, new_value, display_digits):
            continue

        setattr(row, attr_name, new_value)
        change_details[attr_name] = {
            "old": _format_val(old_value),
            "new": _format_val(new_value),
        }

    return change_details


def save_equipment_group_fuel_formula_for_year(
    *,
    equipment_group_id: int,
    year_number: int,
    values: dict,
    variant_number: int = 0,
    database_version_id: int | None = None,
    commit: bool = False,
) -> tuple[EquipmentGroupFuelFormula, dict]:
    vals = dict(values)
    vals.pop("year_number", None)

    vn_raw = vals.pop("variant_number", None)
    if vn_raw is not None:
        try:
            effective_variant = int(vn_raw)
        except (TypeError, ValueError):
            effective_variant = int(variant_number or 0)
    else:
        effective_variant = int(variant_number or 0)

    effective_db_version = database_version_id
    if effective_db_version is None:
        effective_db_version = get_current_db_version_id()

    row = get_or_create_equipment_group_fuel_formula(
        equipment_group_id=equipment_group_id,
        year_number=year_number,
        variant_number=effective_variant,
        database_version_id=effective_db_version,
    )

    if (
        hasattr(row, "database_version_id")
        and row.database_version_id is None
        and effective_db_version is not None
    ):
        row.database_version_id = effective_db_version

    change_details = update_equipment_group_fuel_formula_fields(
        row=row,
        values=vals,
    )

    if commit:
        db.session.commit()

    return row, change_details


def save_equipment_group_fuel_formula_bulk(
    *,
    equipment_group_id: int,
    values_by_year: dict[int, dict],
    database_version_id: int | None = None,
    commit: bool = False,
) -> dict[int, dict]:
    """
    values_by_year: { 2026: { "name": ..., "formtxt": ..., "variant_number": 0 }, ... }
    """
    result = {}

    for year_number, values in values_by_year.items():
        row, change_details = save_equipment_group_fuel_formula_for_year(
            equipment_group_id=equipment_group_id,
            year_number=int(year_number),
            values=values,
            database_version_id=database_version_id,
            commit=False,
        )
        result[int(year_number)] = {
            "row": row,
            "change_details": change_details,
        }

    if commit:
        db.session.commit()

    return result
