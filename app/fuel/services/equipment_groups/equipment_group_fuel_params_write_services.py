# -*- coding: utf-8 -*-
"""
Write/update-слой для EquipmentGroupFuelParam.

Вынесено из equipment_group_fuel_params_services.py, чтобы витрина оставалась
только read/query/hierarchy.

Здесь:
- нормализация FK (external_id) и sanitize перед сохранением — для импорта Excel
  и форм (`import_equipment_group_fuel_params_services`, `fuel_routes`);
- `update_equipment_group_fuel_params_from_form` — сохранение по годам с
  `fuel_param_{year}_{attr}`, change_details и `database_version_id`.

Списки колонок (`EQUIPMENT_GROUP_DETAILS_*`) и INTEGER/STRING/NUMERIC_ATTRS
согласованы с `equipment_group_fuel_params_services` (единый источник колонок
для таблиц; типы полей для парсинга — в этом модуле).

Не подменять этот файл упрощёнными заготовками: нужна двухаргументная
нормализация FK с запросами к таблицам маппинга и текущая семантика
sanitize / сохранения формы.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.common.services.database_version_filter import get_current_db_version_id, set_db_version_on_create
from app.common.services.help_services import (
    format_number_trim_trailing,
    values_equal_by_display_precision,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.external_mapping.fue_em_business_unit_model import BusinessUnitExternalMapping
from app.fuel.models.external_mapping.fue_em_department_model import DepartmentExternalMapping
from app.fuel.models.external_mapping.fue_em_economic_region_model import EconomicRegionExternalMapping
from app.fuel.models.external_mapping.fue_em_gen_company_model import GenCompanyExternalMapping
from app.fuel.models.external_mapping.fue_em_territories_energy_model import TerritoriesEnergyExternalMapping
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import UnionEnergySystemExternalMapping
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS,
    EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS,
    EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS,
)

# Типы полей для парсинга формы / импорта (только write-слой)
INTEGER_ATTRS = frozenset([
    "obor", "ved", "ved_cyrillic", "ees", "numb1120", "numb1", "hfix",
])
STRING_ATTRS = frozenset(["obl", "dep", "oes", "er", "gk", "be"])
NUMERIC_ATTRS = frozenset(
    a
    for a in (EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS + EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS)
    if a not in INTEGER_ATTRS
)

EXTERNAL_MAPPING_MODELS = {
    "obl": TerritoriesEnergyExternalMapping,
    "dep": DepartmentExternalMapping,
    "oes": UnionEnergySystemExternalMapping,
    "er": EconomicRegionExternalMapping,
    "gk": GenCompanyExternalMapping,
    "be": BusinessUnitExternalMapping,
}
_EXTERNAL_MAPPING_VALUE_CACHE: dict[str, dict[str, str | None]] = {
    attr: {} for attr in EXTERNAL_MAPPING_MODELS
}


def normalize_fuel_param_external_mapping_value(attr, value):
    """
    Нормализует значение FK-поля к expected external_id.

    Исторически в топливные параметры местами попадал внутренний `id`
    таблицы маппинга вместо `external_id`. Для строковых FK-полей пытаемся:
    1) принять значение как корректный external_id;
    2) если пришел числовой id записи маппинга — заменить на ее external_id;
    3) если сопоставление не найдено — очистить значение, чтобы не ломать FK.
    """
    if value is None:
        return None

    raw = str(value).strip()
    if not raw or raw.lower() in ("nan", "—", "-", "–"):
        return None

    model = EXTERNAL_MAPPING_MODELS.get(attr)
    if model is None:
        return raw

    cache = _EXTERNAL_MAPPING_VALUE_CACHE.setdefault(attr, {})
    if raw in cache:
        return cache[raw]

    resolved = None
    with db.session.no_autoflush:
        by_external = model.query.filter(model.external_id == raw).first()
        if by_external is not None and getattr(by_external, "external_id", None):
            resolved = str(by_external.external_id).strip()
        else:
            mapping_id = None
            try:
                mapping_id = int(Decimal(raw))
            except (InvalidOperation, ValueError, TypeError):
                mapping_id = None

            if mapping_id is not None:
                by_id = db.session.get(model, mapping_id)
                external_id = getattr(by_id, "external_id", None) if by_id else None
                if external_id is not None and str(external_id).strip():
                    resolved = str(external_id).strip()

    cache[raw] = resolved
    return resolved


def sanitize_equipment_group_fuel_param_foreign_keys(param):
    """Исправляет legacy-значения FK-полей на корректные external_id."""
    changes = []
    if param is None:
        return changes

    for attr in STRING_ATTRS:
        old_val = getattr(param, attr, None)
        new_val = normalize_fuel_param_external_mapping_value(attr, old_val)
        if old_val != new_val:
            setattr(param, attr, new_val)
            changes.append((attr, old_val, new_val))
    return changes


def _parse_fuel_param_value(attr, value):
    """Парсит значение из формы для атрибута EquipmentGroupFuelParam."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "—", "-", "–"):
        return None
    if attr in INTEGER_ATTRS:
        try:
            return int(Decimal(s))
        except (InvalidOperation, ValueError, TypeError):
            return None
    if attr in STRING_ATTRS:
        return normalize_fuel_param_external_mapping_value(attr, s)
    if attr in NUMERIC_ATTRS:
        try:
            return Decimal(s.replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            return None
    return None


TABLE_FUEL_PARAM = "Параметры группы оборудования"
TABLE_FUEL_MAIN = "Основные параметры"
TABLE_FUEL_TABLE2 = "Основные параметры топлива"
TABLE_CONSUMPTION_CALC = "Удельные показатели (расчетные)"


def _fuel_param_table_name(attr):
    if attr in EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS:
        return TABLE_FUEL_MAIN
    if attr in EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS:
        return TABLE_FUEL_PARAM
    if attr in EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS:
        return TABLE_FUEL_TABLE2
    return "Параметры топлива"


def _format_val(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (Decimal, int, float)):
        return format_number_trim_trailing(v)
    if isinstance(v, str):
        return v.strip() or "—"
    return str(v)


class _BulkFuelParamFormAdapter:
    """
    Адаптер POST-данных массового редактирования: поля вида
    g{equipment_group_id}_fuel_param_{year}_{attr} → как fuel_param_{year}_{attr}
    для update_equipment_group_fuel_params_from_form.
    (numb1120 на массовой странице не редактируется — передаётся skip_attrs.)
    """

    __slots__ = ("_form", "_gid", "_prefix")

    def __init__(self, form_data, equipment_group_id: int) -> None:
        self._form = form_data
        self._gid = int(equipment_group_id)
        self._prefix = f"g{self._gid}_"

    def _bulk_key_for_logical(self, key: str) -> str | None:
        """Ключ в POST для логического fuel_param_{year}_{attr}."""
        if not isinstance(key, str) or not key.startswith("fuel_param_"):
            return None
        m = re.match(r"fuel_param_(\d+)_(.+)\Z", key)
        if not m:
            return self._prefix + key
        return f"{self._prefix}fuel_param_{m.group(1)}_{m.group(2)}"

    def __contains__(self, key) -> bool:
        if not isinstance(key, str):
            return False
        bk = self._bulk_key_for_logical(key)
        if bk is None:
            return key in self._form
        return bk in self._form

    def get(self, key):
        if not isinstance(key, str) or not key.startswith("fuel_param_"):
            return self._form.get(key)
        m = re.match(r"fuel_param_(\d+)_(.+)\Z", key)
        if not m:
            return self._form.get(self._prefix + key)
        return self._form.get(f"{self._prefix}fuel_param_{m.group(1)}_{m.group(2)}")


def apply_equipment_group_fuel_params_bulk_save_from_form(
    request_form,
    *,
    equipment_group_ids: list[int],
    start_year: int,
    end_year: int,
    rounding_digits_table1: int = 1,
    rounding_digits_table2: int = 1,
) -> tuple[int, list[str], dict[int, list[tuple]]]:
    """
    Сохраняет основные топливные параметры для набора групп (страница расчётного модуля).
    Возвращает (
      число групп, в которых были изменения,
      список сообщений об ошибках,
      словарь change_details по id группы: (table, year, attr, old, new),
    ).
    """
    errs: list[str] = []
    changed_groups = 0
    details_by_group: dict[int, list[tuple]] = {}
    for eg_id in equipment_group_ids:
        try:
            adapter = _BulkFuelParamFormAdapter(request_form, eg_id)
            _ok, _msg, details = update_equipment_group_fuel_params_from_form(
                eg_id,
                adapter,
                start_year,
                end_year,
                rounding_digits_table1=rounding_digits_table1,
                rounding_digits_table2=rounding_digits_table2,
                skip_attrs=frozenset({"numb1120"}),
                partial=True,
            )
            if details:
                changed_groups += 1
                details_by_group[int(eg_id)] = list(details)
        except Exception as exc:
            errs.append(f"Группа оборудования id={eg_id}: {exc}")
    return changed_groups, errs, details_by_group


def update_equipment_group_fuel_params_from_form(
    equipment_group_id, form_data, start_year, end_year,
    rounding_digits_table1=1, rounding_digits_table2=1,
    skip_attrs: frozenset[str] | None = None,
    partial: bool = False,
):
    """
    Обновляет EquipmentGroupFuelParam из данных формы.
    Ожидает ключи вида: fuel_param_{year}_{attr}
    rounding_digits_table1/table2 — точность отображения для сравнения (избегаем ложных «изменений»).
    skip_attrs — не обновлять эти атрибуты (например numb1120 на массовой странице расчёта).
    partial=True — обрабатывать только ключи, присутствующие в form_data (массовая страница:
    не сбрасывать в NULL поля, не переданные в POST).
    Возвращает (success: bool, message: str, change_details: list).
    """
    version_id = get_current_db_version_id()
    all_attrs = (
        EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS
        + EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS
        + EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS
    )
    params_list = EquipmentGroupFuelParam.query.filter_by(
        equipment_group_id=equipment_group_id
    ).all()
    existing_params = {}
    for p in params_list:
        if p.year_number not in existing_params or p.database_version_id == version_id:
            existing_params[p.year_number] = p
    change_details = []
    for year in range(start_year, end_year + 1):
        param = existing_params.get(year)
        if param is not None:
            for attr, old_val, new_val in sanitize_equipment_group_fuel_param_foreign_keys(param):
                change_details.append(
                    (_fuel_param_table_name(attr), year, attr, _format_val(old_val), _format_val(new_val))
                )
        for attr in all_attrs:
            if skip_attrs and attr in skip_attrs:
                continue
            key = f"fuel_param_{year}_{attr}"
            if partial and key not in form_data:
                continue
            raw = form_data.get(key)
            val = _parse_fuel_param_value(attr, raw)
            if param is None:
                if val is not None:
                    param = EquipmentGroupFuelParam(
                        equipment_group_id=equipment_group_id,
                        year_number=year,
                        database_version_id=version_id,
                    )
                    set_db_version_on_create(param)
                    db.session.add(param)
                    existing_params[year] = param
            if param is not None:
                if (
                    hasattr(param, "database_version_id")
                    and param.database_version_id is None
                    and version_id is not None
                ):
                    param.database_version_id = version_id
                old_val = getattr(param, attr, None)
                digits = rounding_digits_table2 if attr in EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS else rounding_digits_table1
                is_unchanged = (
                    attr in NUMERIC_ATTRS
                    and values_equal_by_display_precision(old_val, val, digits)
                ) or (attr not in NUMERIC_ATTRS and old_val == val)
                if not is_unchanged:
                    setattr(param, attr, val)
                    change_details.append(
                        (_fuel_param_table_name(attr), year, attr, _format_val(old_val), _format_val(val))
                    )

    return True, "Параметры успешно сохранены." if change_details else "Изменений нет.", change_details
