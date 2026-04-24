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
from app.extensions import db
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    get_equipment_group_ids_for_fuel_params_filters,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    build_equipment_group_specific_fuel_consumption_hierarchy,
    get_equipment_groups_with_specific_fuel_consumption_data,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_write_services import (
    CONSUMPTION_EDITABLE_ATTRS,
)

_COPY_SPECIFIC_ATTRS = list(CONSUMPTION_EDITABLE_ATTRS)


class _MissingYearSpecificFuelParam:
    """Год из интервала без строки в gs_fue_equipment_group_specific_fuel_consumption."""

    __slots__ = ("year_number",)

    def __init__(self, year_number: int) -> None:
        self.year_number = int(year_number)

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


def get_specific_fuel_consumption_calculation_edit_data_view_model(
    filters: dict[str, Any],
    *,
    start_year: int,
    end_year: int,
    rounding_digits: int,
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

    def _row_sort_key(item: tuple) -> tuple:
        eg, param = item
        y = getattr(param, "year_number", None) if param is not None else None
        name = (eg.name or "") if eg else ""
        name_ext = (eg.name_ext or "") if eg else ""
        eid = eg.id if eg else 0
        return ((name or "").lower(), (name_ext or "").lower(), eid, y or 0)

    rows = sorted(rows, key=_row_sort_key)

    bulk_edit_equipment_group_ids = sorted(
        {int(eg.id) for eg, _ in rows if eg is not None and getattr(eg, "id", None) is not None}
    )

    row_groups = _group_specific_rows_by_equipment_group(rows)
    hierarchy = build_equipment_group_specific_fuel_consumption_hierarchy(rows)

    return {
        "equipment_group_specific_fuel_consumption_rows": rows,
        "equipment_group_specific_fuel_consumption_row_groups": row_groups,
        "equipment_group_specific_fuel_consumption_hierarchy": hierarchy,
        "total_count": len(rows),
        "start_year": start_year,
        "end_year": end_year,
        "rounding_digits": rounding_digits,
        "bulk_edit_equipment_group_ids": bulk_edit_equipment_group_ids,
    }


def _get_specific_consumption_for_group_year(
    equipment_group_id: int,
    year_number: int,
    version_id: int | None,
) -> EquipmentGroupSpecificFuelConsumption | None:
    q = EquipmentGroupSpecificFuelConsumption.query.filter_by(
        equipment_group_id=equipment_group_id,
        year_number=year_number,
    )
    if version_id is not None:
        q = q.filter(EquipmentGroupSpecificFuelConsumption.database_version_id == version_id)
    else:
        q = q.filter(EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None))
    return q.first()


def copy_specific_fuel_consumption_between_years_for_filters(
    filters: dict[str, Any],
    *,
    filter_start_year: int,
    filter_end_year: int,
    source_year: int,
    target_year: int,
) -> tuple[int, int, int]:
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
        copied += 1

    return copied, skipped, len(eg_ids)
