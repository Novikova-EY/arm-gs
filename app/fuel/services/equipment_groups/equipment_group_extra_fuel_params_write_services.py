# -*- coding: utf-8 -*-
"""
Write/update-слой для EquipmentGroupExtraFuelParam.

Вынесено из equipment_group_details_params_update_services.py и отделено от
equipment_group_extra_fuel_params_services.py, чтобы:
- display/query-сервис не содержал логику записи;
- форма equipment_group_edit и будущий импорт могли использовать единый write-layer.

Списки колонок (`EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS`) — единый источник в
`equipment_group_extra_fuel_params_services`; константа импортируется сюда для
write-слоя и re-export в orchestration (`equipment_group_details_params_update_services`).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.common.services.help_services import values_equal_by_display_precision
from app.extensions import db
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_services import (
    EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS,
)

NUMERIC_EXTRA_ATTRS = frozenset(EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS)


def _format_val(value):
    if value is None:
        return "—"
    return str(value)


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


def _parse_extra_fuel_param_value(attr_name: str, raw_value):
    """Разбор значения формы / импорта для поля EquipmentGroupExtraFuelParam."""
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            return None

    if attr_name in NUMERIC_EXTRA_ATTRS:
        try:
            return Decimal(str(raw_value).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return None

    return raw_value


def get_or_create_equipment_group_extra_fuel_param(
    *,
    equipment_group_id: int,
    year_number: int,
    database_version_id: int | None = None,
) -> EquipmentGroupExtraFuelParam:
    """
    Получает или создаёт строку EquipmentGroupExtraFuelParam для пары группа + год.

    Семантика как у сохранения формы: одна строка на (equipment_group_id, year_number),
    без дополнительного фильтра по database_version_id при поиске.
    """
    effective_db_version = database_version_id
    if effective_db_version is None:
        effective_db_version = get_current_db_version_id()

    row = (
        EquipmentGroupExtraFuelParam.query.filter_by(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        ).first()
    )
    if row:
        return row

    row = EquipmentGroupExtraFuelParam(
        equipment_group_id=equipment_group_id,
        year_number=year_number,
        database_version_id=effective_db_version,
    )
    set_db_version_on_create(row)
    db.session.add(row)
    db.session.flush()
    return row


def update_equipment_group_extra_fuel_param_fields(
    *,
    row: EquipmentGroupExtraFuelParam,
    values: dict,
    rounding_digits: int = 1,
) -> dict:
    """
    Обновляет поля строки EquipmentGroupExtraFuelParam и возвращает change_details.

    values: {attr_name: raw_value}
    """
    change_details = {}

    for attr_name, raw_value in values.items():
        if not hasattr(row, attr_name):
            continue

        new_value = _parse_extra_fuel_param_value(attr_name, raw_value)
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


def save_equipment_group_extra_fuel_params_for_year(
    *,
    equipment_group_id: int,
    year_number: int,
    values: dict,
    database_version_id: int | None = None,
    commit: bool = False,
    rounding_digits: int = 1,
) -> tuple[EquipmentGroupExtraFuelParam | None, dict]:
    """
    Создаёт/обновляет EquipmentGroupExtraFuelParam за один год.
    Новая строка не создаётся, если в БД нет записи и все значения пустые.
    """
    effective_db_version = database_version_id
    if effective_db_version is None:
        effective_db_version = get_current_db_version_id()

    row = (
        EquipmentGroupExtraFuelParam.query.filter_by(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        ).first()
    )

    filtered = {
        k: v for k, v in values.items() if k in NUMERIC_EXTRA_ATTRS
    }

    if row is None:
        has_any = False
        for attr in EQUIPMENT_GROUP_DETAILS_EXTRA_ATTRS:
            if attr not in filtered:
                continue
            if _parse_extra_fuel_param_value(attr, filtered.get(attr)) is not None:
                has_any = True
                break
        if not has_any:
            return None, {}

        row = EquipmentGroupExtraFuelParam(
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

    change_details = update_equipment_group_extra_fuel_param_fields(
        row=row,
        values=filtered,
        rounding_digits=rounding_digits,
    )

    if commit:
        db.session.commit()

    return row, change_details


def save_equipment_group_extra_fuel_params_bulk(
    *,
    equipment_group_id: int,
    values_by_year: dict[int, dict],
    database_version_id: int | None = None,
    commit: bool = False,
    rounding_digits: int = 1,
) -> dict[int, dict]:
    """
    Массовое сохранение дополнительных параметров топлива по нескольким годам.

    values_by_year:
        {
            2026: {"gaz_prir": "10", "maztop": "2.5", ...},
            2027: {"gaz_prir": "11", ...},
        }
    """
    result = {}

    for year_number, values in values_by_year.items():
        row, change_details = save_equipment_group_extra_fuel_params_for_year(
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
