# -*- coding: utf-8 -*-
"""
Данные для страницы «Редактировать удельные показатели» из модуля расчёта
(/fuel/calculation/equipment_group_specific_fuel_consumption_edit_data).

Источники — как на /fuel/stations_equipment_group_specific_fuel_consumption:
иерархия групп и удельные показатели за интервал лет.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.common.services.get_services.years.year_feature_services import (
    get_year_feature_dict_for_version,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    _prefer_matching_db_version,
    build_fuel_param_row_warn_sets,
)
from app.fuel.services.calculation.specific_consumption_lookup import (
    specific_consumption_has_payload,
)
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_ved_participates,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    FUEL_PARAM_VED_DISPLAY,
    get_equipment_group_ids_for_fuel_params_filters,
    get_equipment_groups_with_fuel_params_data,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    build_equipment_group_specific_fuel_consumption_hierarchy,
    get_equipment_groups_with_specific_fuel_consumption_data,
    overlay_snk_calc_from_fuel_params,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_write_services import (
    CONSUMPTION_EDITABLE_ATTRS,
    _sync_numb1120_from_equipment_group,
)

# Как Access «Копирование_удельных» из архива: snk/btp/sntp/bk/y (+ поля VED), без k.
# k копируется только в сценарии станция→группа, не при добавлении расчётного года.
_COPY_SPECIFIC_ATTRS = [a for a in CONSUMPTION_EDITABLE_ATTRS if a != "k"]


def _year_numbers_with_feature(feature_name: str) -> frozenset[int]:
    """Годы с указанным признаком в текущей версии БД."""
    version_id = get_current_db_version_id()
    yf = get_year_feature_dict_for_version(version_id) or {}
    needle = str(feature_name or "").strip().casefold()
    return frozenset(
        int(year)
        for year, name in yf.items()
        if year is not None and str(name or "").strip().casefold() == needle
    )


def _fact_year_numbers_for_current_version() -> frozenset[int]:
    """Годы с признаком «факт» — входные y/btp/… только чтение."""
    return _year_numbers_with_feature("факт")


def _plan_year_numbers_for_current_version() -> frozenset[int]:
    """Годы с признаком «план» — *_calc только расчёт (не редактируются)."""
    return _year_numbers_with_feature("план")


class _MissingYearSpecificFuelParam:
    """Год из интервала без строки в gs_fue_equipment_group_specific_fuel_consumption."""

    __slots__ = ("year_number", "snk_calc", "ved")

    def __init__(self, year_number: int) -> None:
        self.year_number = int(year_number)
        self.snk_calc = None
        self.ved = None

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, name: str) -> None:
        return None


def _expand_specific_rows_for_year_interval(
    rows: list,
    start_year: int,
    end_year: int,
) -> list:
    years_range = range(start_year, end_year + 1)
    by_eg_order: list[int] = []
    by_eg_rows: dict[int, list] = defaultdict(list)

    for eg, param in rows or []:
        if not eg:
            continue
        eid = eg.id
        if eid not in by_eg_rows:
            by_eg_order.append(eid)
        by_eg_rows[eid].append((eg, param))

    out: list = []
    for eid in by_eg_order:
        eg_rows = by_eg_rows[eid]
        eg = eg_rows[0][0]
        year_to_param: dict[int, Any] = {}
        for _eg, param in eg_rows:
            if param is None:
                continue
            if isinstance(param, _MissingYearSpecificFuelParam):
                continue
            yn = getattr(param, "year_number", None)
            if yn is not None:
                year_to_param[int(yn)] = param
        for y in years_range:
            if y in year_to_param:
                out.append((eg, year_to_param[y]))
            else:
                out.append((eg, _MissingYearSpecificFuelParam(y)))
    return out


def _group_specific_rows_by_equipment_group(rows: list) -> list[list]:
    if not rows:
        return []
    from itertools import groupby

    def _key(item: tuple) -> int:
        eg = item[0]
        return int(eg.id) if eg is not None and getattr(eg, "id", None) is not None else 0

    return [list(g) for _, g in groupby(rows, key=_key)]


def group_matches_empty_specific_check(group_rows: list) -> bool:
    """Группа с ved > 0 и пустыми удельниками во всех отображаемых годах.

    ved — FuelParam.ved (есть и > 0 хотя бы в одном году интервала).
    Пустой удельник — нет полезной нагрузки y/snk/sntp/bk/btp/… (нули как пусто).
    """
    if not group_rows:
        return False
    has_ved_gt_zero = False
    for _eg, param in group_rows:
        ved = getattr(param, "ved", None) if param is not None else None
        if fuel_param_ved_participates(ved):
            has_ved_gt_zero = True
        if specific_consumption_has_payload(param):
            return False
    return has_ved_gt_zero


def filter_rows_empty_specific_with_ved(rows: list) -> list:
    """Оставить только группы, подходящие под кнопку «Проверка» на ТЭП edit_data."""
    keep_ids: set[int] = set()
    for group_rows in _group_specific_rows_by_equipment_group(rows):
        if not group_matches_empty_specific_check(group_rows):
            continue
        eg = group_rows[0][0]
        if eg is not None and getattr(eg, "id", None) is not None:
            keep_ids.add(int(eg.id))
    if not keep_ids:
        return []
    return [
        (eg, param)
        for eg, param in rows
        if eg is not None and getattr(eg, "id", None) is not None and int(eg.id) in keep_ids
    ]


def _overlay_ved_from_fuel_params(specific_rows: list, fuel_param_rows: list) -> None:
    """Подставляет FuelParam.ved на строки удельных (в т.ч. пустые годы интервала)."""
    ved_by_key: dict[tuple[int, int], Any] = {}
    for eg, fp in fuel_param_rows or []:
        if not eg or fp is None:
            continue
        gid = getattr(eg, "id", None)
        year = getattr(fp, "year_number", None)
        if gid is None or year is None:
            continue
        ved_by_key[(int(gid), int(year))] = getattr(fp, "ved", None)

    for eg, cons in specific_rows or []:
        if cons is None:
            continue
        gid = getattr(cons, "equipment_group_id", None) or (
            getattr(eg, "id", None) if eg else None
        )
        year = getattr(cons, "year_number", None)
        if gid is None or year is None:
            continue
        try:
            cons.ved = ved_by_key.get((int(gid), int(year)))
        except Exception:
            pass


def get_specific_fuel_consumption_calculation_edit_data_view_model(
    filters: dict[str, Any],
    *,
    start_year: int,
    end_year: int,
    rounding_digits: int,
    check_empty_specific: bool = False,
) -> dict[str, Any]:
    f = {**filters}
    f.pop("page", None)

    specific_data = get_equipment_groups_with_specific_fuel_consumption_data(
        filters=f,
        per_page="all",
        page=1,
        start_year=start_year,
        end_year=end_year,
        show_all=True,
    )
    rows = specific_data.get("rows") or []
    rows = _expand_specific_rows_for_year_interval(rows, start_year, end_year)
    overlay_snk_calc_from_fuel_params(rows)

    def _row_sort_key(item: tuple) -> tuple:
        eg, param = item
        y = getattr(param, "year_number", None) if param is not None else None
        name = (eg.name or "") if eg else ""
        name_ext = (eg.name_ext or "") if eg else ""
        eid = eg.id if eg else 0
        return ((name or "").lower(), (name_ext or "").lower(), eid, y or 0)

    rows = sorted(rows, key=_row_sort_key)

    # Жёлтая подсветка строк при изменении Nуст — как на equipment_group_fuel_params_edit_data
    fuel_params_data = get_equipment_groups_with_fuel_params_data(
        filters=f,
        per_page="all",
        page=1,
        start_year=start_year,
        end_year=end_year,
        show_all=True,
    )
    fuel_param_rows = fuel_params_data.get("rows") or []
    fuel_param_warn_sets = build_fuel_param_row_warn_sets(fuel_param_rows)
    _overlay_ved_from_fuel_params(rows, fuel_param_rows)

    if check_empty_specific:
        rows = filter_rows_empty_specific_with_ved(rows)

    bulk_edit_equipment_group_ids = sorted(
        {int(eg.id) for eg, _ in rows if eg is not None and getattr(eg, "id", None) is not None}
    )

    row_groups = _group_specific_rows_by_equipment_group(rows)
    hierarchy = build_equipment_group_specific_fuel_consumption_hierarchy(rows)
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        apply_suppress_aggregate_rows_to_hierarchy,
        should_suppress_aggregate_rows_for_filters,
    )
    if should_suppress_aggregate_rows_for_filters(f):
        apply_suppress_aggregate_rows_to_hierarchy(hierarchy)

    return {
        "equipment_group_specific_fuel_consumption_rows": rows,
        "equipment_group_specific_fuel_consumption_row_groups": row_groups,
        "equipment_group_specific_fuel_consumption_hierarchy": hierarchy,
        "nust_changed_from_prev_year_rows": fuel_param_warn_sets[
            "nust_changed_from_prev_year_rows"
        ],
        "fact_year_numbers": _fact_year_numbers_for_current_version(),
        "plan_year_numbers": _plan_year_numbers_for_current_version(),
        "total_count": len(rows),
        "start_year": start_year,
        "end_year": end_year,
        "rounding_digits": rounding_digits,
        "bulk_edit_equipment_group_ids": bulk_edit_equipment_group_ids,
        "numb1120_filter_choices": specific_data.get("numb1120_filter_choices") or [],
        "fuel_param_ved_labels": FUEL_PARAM_VED_DISPLAY,
    }


def _get_specific_consumption_for_group_year(
    equipment_group_id: int,
    year_number: int,
    version_id: int | None,
) -> EquipmentGroupSpecificFuelConsumption | None:
    rows = EquipmentGroupSpecificFuelConsumption.query.filter_by(
        equipment_group_id=equipment_group_id,
        year_number=year_number,
    ).all()
    return _prefer_matching_db_version(rows, version_id)


def copy_specific_fuel_consumption_between_years_for_filters(
    filters: dict[str, Any],
    *,
    filter_start_year: int,
    filter_end_year: int,
    source_year: int,
    target_year: int,
) -> tuple[int, int, int]:
    """Явное копирование года (coeff_copy_specific_consumption_year).

    «Добавить год/период» на странице удельных это не вызывает: Access U.Seek
    не требует строки расчётного года, без неё берётся последняя year ≤ цели.
    """
    if source_year == target_year:
        return 0, 0, 0

    f = {**filters}
    f.pop("page", None)

    eg_ids = get_equipment_group_ids_for_fuel_params_filters(
        f,
        start_year=filter_start_year,
        end_year=filter_end_year,
    )
    if not eg_ids:
        return 0, 0, 0

    version_id = get_current_db_version_id()
    copied = 0
    skipped = 0

    for eg_id in eg_ids:
        eg_id = int(eg_id)
        source = _get_specific_consumption_for_group_year(eg_id, source_year, version_id)
        if source is None:
            skipped += 1
            continue

        target = _get_specific_consumption_for_group_year(eg_id, target_year, version_id)
        if target is None:
            target = EquipmentGroupSpecificFuelConsumption(
                equipment_group_id=eg_id,
                year_number=target_year,
                database_version_id=version_id,
            )
            set_db_version_on_create(target)
            db.session.add(target)

        target.year_number = target_year
        target.equipment_group_id = eg_id
        if version_id is not None and getattr(target, "database_version_id", None) is None:
            target.database_version_id = version_id

        for key in _COPY_SPECIFIC_ATTRS:
            if hasattr(source, key):
                setattr(target, key, getattr(source, key))
        _sync_numb1120_from_equipment_group(target, eg_id)
        copied += 1

    return copied, skipped, len(eg_ids)
