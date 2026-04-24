# -*- coding: utf-8 -*-
"""
Write/update-слой для EquipmentGroupSpecificFuelConsumption.

Ручной ввод только полей k, y, btp, sntp, bk, snk (consumption_param_{year}_{attr}).
Расчётные y_calc, btp_calc, sntp_calc, bk_calc, snk_calc не принимаются из формы —
только пересчёт (equipment_group_specific_fuel_consumption_recalc_services).

Справочно: полный список колонок таблицы — SPECIFIC_FUEL_CONSUMPTION_COLUMNS в
equipment_group_specific_fuel_consumption_services.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.common.services.help_services import values_equal_by_display_precision
from app.extensions import db
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    SPECIFIC_FUEL_CONSUMPTION_COLUMNS,
)

# Ручной ввод с equipment_group_details / equipment_group_edit (только эти поля; не *_calc).
CONSUMPTION_EDITABLE_ATTRS = ["k", "y", "btp", "sntp", "bk", "snk", "numb1120"]
CONSUMPTION_FORM_INPUT_ATTRS = CONSUMPTION_EDITABLE_ATTRS
SPECIFIC_FUEL_CONSUMPTION_EDITABLE_ATTRS = CONSUMPTION_EDITABLE_ATTRS

SPECIFIC_FUEL_CONSUMPTION_CALC_ATTRS = [
    attr for attr, _, is_num in SPECIFIC_FUEL_CONSUMPTION_COLUMNS
    if is_num and attr.endswith("_calc")
]

INTEGER_ATTRS = frozenset(["k", "numb1120"])

NUMERIC_DECIMAL_ATTRS = frozenset(
    a for a in CONSUMPTION_FORM_INPUT_ATTRS if a not in INTEGER_ATTRS
)


def _format_val(value):
    if value is None:
        return "—"
    return str(value)


def _parse_int_for_k(value):
    """Парсит значение для поля k."""
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


def _parse_specific_fuel_consumption_value(attr_name: str, raw_value):
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            return None

    if attr_name in INTEGER_ATTRS:
        return _parse_int_for_k(raw_value)

    if attr_name in NUMERIC_DECIMAL_ATTRS:
        try:
            return Decimal(str(raw_value).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return None

    return raw_value


def get_or_create_specific_fuel_consumption(
    *,
    equipment_group_id: int,
    year_number: int,
    database_version_id: int | None = None,
) -> EquipmentGroupSpecificFuelConsumption:
    """
    Одна строка на (equipment_group_id, year_number); поиск без фильтра по версии.
    """
    effective_db_version = database_version_id
    if effective_db_version is None:
        effective_db_version = get_current_db_version_id()

    row = (
        EquipmentGroupSpecificFuelConsumption.query.filter_by(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        ).first()
    )
    if row:
        return row

    row = EquipmentGroupSpecificFuelConsumption(
        equipment_group_id=equipment_group_id,
        year_number=year_number,
        database_version_id=effective_db_version,
    )
    set_db_version_on_create(row)
    db.session.add(row)
    db.session.flush()
    return row


def update_specific_fuel_consumption_fields(
    *,
    row: EquipmentGroupSpecificFuelConsumption,
    values: dict,
    rounding_digits: int = 1,
) -> dict:
    """
    Обновляет поля строки и возвращает change_details {attr: {old, new}}.
    Учитываются только ключи из CONSUMPTION_FORM_INPUT_ATTRS.
    """
    change_details = {}

    for attr_name in CONSUMPTION_FORM_INPUT_ATTRS:
        if attr_name not in values:
            continue
        if not hasattr(row, attr_name):
            continue

        raw_value = values[attr_name]
        new_value = _parse_specific_fuel_consumption_value(attr_name, raw_value)
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


def save_specific_fuel_consumption_for_year(
    *,
    equipment_group_id: int,
    year_number: int,
    values: dict,
    database_version_id: int | None = None,
    commit: bool = False,
    rounding_digits: int = 1,
) -> tuple[EquipmentGroupSpecificFuelConsumption | None, dict]:
    """
    Создаёт/обновляет строку за год.
    Новая строка не создаётся, если записи нет и все входные значения пустые.
    """
    effective_db_version = database_version_id
    if effective_db_version is None:
        effective_db_version = get_current_db_version_id()

    row = (
        EquipmentGroupSpecificFuelConsumption.query.filter_by(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        ).first()
    )

    filtered = {k: v for k, v in values.items() if k in CONSUMPTION_FORM_INPUT_ATTRS}

    if row is None:
        has_any = False
        for attr in CONSUMPTION_FORM_INPUT_ATTRS:
            if attr not in filtered:
                continue
            if _parse_specific_fuel_consumption_value(attr, filtered.get(attr)) is not None:
                has_any = True
                break
        if not has_any:
            return None, {}

        row = EquipmentGroupSpecificFuelConsumption(
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

    change_details = update_specific_fuel_consumption_fields(
        row=row,
        values=filtered,
        rounding_digits=rounding_digits,
    )

    if commit:
        db.session.commit()

    return row, change_details


def save_specific_fuel_consumption_bulk(
    *,
    equipment_group_id: int,
    values_by_year: dict[int, dict],
    database_version_id: int | None = None,
    commit: bool = False,
    rounding_digits: int = 1,
) -> dict[int, dict]:
    result = {}

    for year_number, values in values_by_year.items():
        row, change_details = save_specific_fuel_consumption_for_year(
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


def apply_specific_fuel_consumption_bulk_save_from_form(
    request_form,
    *,
    equipment_group_ids: list[int],
    start_year: int,
    end_year: int,
    rounding_digits: int = 1,
) -> tuple[int, list[str]]:
    """
    Массовое сохранение удельных показателей (k, y, btp, sntp, bk, snk) с страницы расчётного модуля.
    Поля формы: g{id}_specific_fc_{year}_{attr}.
    """
    errs: list[str] = []
    changed_groups = 0
    effective_db_version = get_current_db_version_id()

    for eg_id in equipment_group_ids:
        group_changed = False
        try:
            for year in range(start_year, end_year + 1):
                values: dict = {}
                for attr in CONSUMPTION_FORM_INPUT_ATTRS:
                    key = f"g{eg_id}_specific_fc_{year}_{attr}"
                    if key in request_form:
                        values[attr] = request_form.get(key)
                if not values:
                    continue
                _row, change_details = save_specific_fuel_consumption_for_year(
                    equipment_group_id=eg_id,
                    year_number=year,
                    values=values,
                    database_version_id=effective_db_version,
                    commit=False,
                    rounding_digits=rounding_digits,
                )
                if change_details:
                    group_changed = True
        except Exception as exc:
            errs.append(f"Группа оборудования id={eg_id}: {exc}")
            continue
        if group_changed:
            changed_groups += 1

    return changed_groups, errs
