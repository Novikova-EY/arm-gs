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
from app.common.services.help_services import (
    format_number_trim_trailing,
    values_equal_by_display_precision,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_formula_model import (
    EquipmentGroupFuelFormula,
)
from app.fuel.models.fue_equipment_group_model import EquipmentGroup

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

# Годы с этими признаками — formtxt редактируется на странице формул
FORMULA_FORMTXT_EDITABLE_YEAR_FEATURES = frozenset(
    {
        "текущий",
        "текущий (оценка)",
        "план",
    }
)

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


def _sync_numb1120_from_equipment_group(
    row: EquipmentGroupFuelFormula,
    equipment_group_id: int,
) -> dict:
    """Подставляет numb1120 = EquipmentGroup.numb (как на странице ТЭП)."""
    eg = db.session.get(EquipmentGroup, equipment_group_id)
    if eg is None or eg.numb is None:
        return {}
    new_value = int(eg.numb)
    old_value = getattr(row, "numb1120", None)
    if old_value == new_value:
        return {}
    row.numb1120 = new_value
    return {
        "numb1120": {
            "old": _format_val(old_value),
            "new": _format_val(new_value),
        }
    }


def _year_feature_allows_formtxt_edit(feature_name: str | None) -> bool:
    raw = str(feature_name or "").strip().casefold()
    if not raw:
        return False
    if raw in {x.casefold() for x in FORMULA_FORMTXT_EDITABLE_YEAR_FEATURES}:
        return True
    # «текущий (…)» / «текущий(оценка)» и т.п.
    compact = raw.replace(" ", "")
    return compact.startswith("текущий")


def formtxt_editable_year_numbers_for_version(
    version_id: int | None = None,
) -> frozenset[int]:
    """Годы с признаком «текущий» / «текущий (оценка)» / «план»."""
    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict_for_version,
    )

    if version_id is None:
        version_id = get_current_db_version_id()
    yf = get_year_feature_dict_for_version(version_id) or {}
    return frozenset(
        int(year)
        for year, name in yf.items()
        if year is not None and _year_feature_allows_formtxt_edit(name)
    )


_FORMULA_COPY_ATTRS: tuple[str, ...] = ("name", "formtxt", "numb1120", "numb1")


def copy_fuel_formulas_between_years_for_filters(
    filters: dict,
    *,
    filter_start_year: int,
    filter_end_year: int,
    source_year_number: int,
    target_year_numbers: list[int],
) -> tuple[int, int, int]:
    """
    Копирует формулы топлива с базового года на целевые годы для групп по фильтрам страницы.

    Копируются все варианты (variant_number) за source_year_number: name, formtxt, numb1120, numb1.
    Возвращает (число операций записи, групп без данных за базовый год, всего групп в выборке).
    """
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        get_equipment_group_ids_for_fuel_params_filters,
    )

    targets = [int(y) for y in target_year_numbers if int(y) != int(source_year_number)]
    if not targets:
        return 0, 0, 0

    f = {**(filters or {})}
    f.pop("page", None)

    eg_ids = get_equipment_group_ids_for_fuel_params_filters(
        f,
        start_year=filter_start_year,
        end_year=filter_end_year,
    )
    if not eg_ids:
        return 0, 0, 0

    version_id = get_current_db_version_id()
    source_year = int(source_year_number)
    copied = 0
    skipped = 0

    for eg_id in eg_ids:
        eg_id = int(eg_id)
        q = EquipmentGroupFuelFormula.query.filter_by(
            equipment_group_id=eg_id,
            year_number=source_year,
        )
        if version_id is not None:
            q = q.filter(EquipmentGroupFuelFormula.database_version_id == version_id)
        else:
            q = q.filter(EquipmentGroupFuelFormula.database_version_id.is_(None))
        source_rows = q.all()
        if not source_rows:
            skipped += 1
            continue

        for target_year in targets:
            for source in source_rows:
                vn = int(getattr(source, "variant_number", None) or 0)
                values = {
                    attr: getattr(source, attr, None) for attr in _FORMULA_COPY_ATTRS
                }
                row, change_details = save_equipment_group_fuel_formula_for_year(
                    equipment_group_id=eg_id,
                    year_number=target_year,
                    values=values,
                    variant_number=vn,
                    database_version_id=version_id,
                    commit=False,
                )
                # Даже если значения совпали — считаем операцию (как «добавить год» на ТЭП)
                if change_details or row is not None:
                    copied += 1

    return copied, skipped, len(eg_ids)


def apply_fuel_formula_bulk_save_from_form(
    request_form,
    *,
    equipment_group_ids: list[int],
    start_year: int,
    end_year: int,
) -> tuple[int, list[str]]:
    """
    Массовое сохранение formtxt со страницы формул.
    Поля: g{id}_fuel_formula_{year}_v{variant}_formtxt.
    Редактируются только годы «текущий» / «план»; numb1120 ← EquipmentGroup.numb.
    """
    import re

    field_re = re.compile(r"^g(\d+)_fuel_formula_(\d+)_v(\d+)_formtxt$")
    errs: list[str] = []
    changed_groups = 0
    effective_db_version = get_current_db_version_id()
    editable_years = formtxt_editable_year_numbers_for_version(effective_db_version)
    allowed_ids = set(int(x) for x in equipment_group_ids)

    # Собрать поля по (eg_id, year, variant)
    by_eg: dict[int, dict[tuple[int, int], str]] = {}
    for key in request_form:
        m = field_re.match(key)
        if not m:
            continue
        eg_id = int(m.group(1))
        year = int(m.group(2))
        variant = int(m.group(3))
        if eg_id not in allowed_ids:
            continue
        if year < start_year or year > end_year:
            continue
        if year not in editable_years:
            continue
        by_eg.setdefault(eg_id, {})[(year, variant)] = request_form.get(key)

    for eg_id, year_variant_values in by_eg.items():
        group_changed = False
        try:
            eg = db.session.get(EquipmentGroup, eg_id)
            for (year, variant), formtxt_raw in year_variant_values.items():
                formtxt_stripped = (
                    formtxt_raw.strip() if isinstance(formtxt_raw, str) else formtxt_raw
                )
                existing = (
                    EquipmentGroupFuelFormula.query.filter_by(
                        equipment_group_id=eg_id,
                        year_number=year,
                        variant_number=variant,
                        database_version_id=effective_db_version,
                    ).first()
                )
                # Не создаём пустые формулы «с нуля» при сохранении без текста
                if existing is None and not formtxt_stripped:
                    continue

                values: dict = {"formtxt": formtxt_raw}
                row, change_details = save_equipment_group_fuel_formula_for_year(
                    equipment_group_id=eg_id,
                    year_number=year,
                    values=values,
                    variant_number=variant,
                    database_version_id=effective_db_version,
                    commit=False,
                )
                if eg is not None and not (row.name or "").strip() and eg.name:
                    old_name = row.name
                    row.name = eg.name
                    if old_name != row.name:
                        change_details["name"] = {
                            "old": _format_val(old_name),
                            "new": _format_val(row.name),
                        }
                change_details.update(
                    _sync_numb1120_from_equipment_group(row, eg_id)
                )
                if change_details:
                    group_changed = True
        except Exception as exc:
            errs.append(f"Группа оборудования id={eg_id}: {exc}")
            continue
        if group_changed:
            changed_groups += 1

    return changed_groups, errs
