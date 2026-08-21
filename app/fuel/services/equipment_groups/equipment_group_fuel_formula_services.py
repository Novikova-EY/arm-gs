#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Read/query/display для страницы «Формулы для расчета топлива по группам оборудования».

Запись в EquipmentGroupFuelFormula — в equipment_group_fuel_formula_write_services.py;
импорт Excel — в import_equipment_group_fuel_formula_services.py.
"""

from sqlalchemy import and_, or_

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_model import EquipmentGroup


def get_equipment_groups_with_fuel_formula_data(
    filters=None,
    per_page=25,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Список (EquipmentGroup, EquipmentGroupFuelFormula) по фильтрам станций.
    Строки формул ограничиваются year_number в [start_year, end_year];
    для территориального отбора групп используется тот же диапазон лет.
    """
    from app.common.services.get_services.years.years_get_services import (
        get_filter_end_year,
        get_filter_start_year,
    )
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from sqlalchemy.orm import selectinload

    _start = start_year if start_year is not None else get_filter_start_year()
    _end = end_year if end_year is not None else get_filter_end_year()
    if _start is not None and _end is not None and int(_start) > int(_end):
        _start, _end = _end, _start
    current_version_id = get_current_db_version_id()

    version_match = or_(
        and_(
            EquipmentGroupFuelFormula.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupFuelFormula.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_parts = [
        EquipmentGroupFuelFormula.equipment_group_id == EquipmentGroup.id,
        version_match,
    ]
    if _start is not None and _end is not None:
        join_parts.append(
            and_(
                EquipmentGroupFuelFormula.year_number >= int(_start),
                EquipmentGroupFuelFormula.year_number <= int(_end),
            )
        )
    join_cond = and_(*join_parts)

    base_query = db.session.query(EquipmentGroup, EquipmentGroupFuelFormula).outerjoin(
        EquipmentGroupFuelFormula,
        join_cond,
    )

    if hasattr(EquipmentGroup, "database_version_id"):
        if current_version_id is not None:
            base_query = base_query.filter(
                EquipmentGroup.database_version_id == current_version_id
            )
        else:
            base_query = base_query.filter(EquipmentGroup.database_version_id.is_(None))

    territorial_keys = (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    )
    _filters = {
        k: v
        for k, v in (filters or {}).items()
        if k not in ("page", "start_year", "end_year")
    }
    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    if any(_filters.get(k) for k in territorial_keys) or equipment_group_name_filter:
        from app.fuel.services.stations.stations_equipment_groups_services import (
            get_filtered_equipment_group_ids,
            get_filtered_standalone_equipment_group_ids,
        )

        filtered_ids = (
            get_filtered_equipment_group_ids(
                _filters, start_year=_start, end_year=_end
            )
            | get_filtered_standalone_equipment_group_ids(
                _filters,
                version_id=current_version_id,
                strict_version=True,
            )
        )
        if filtered_ids:
            base_query = base_query.filter(EquipmentGroup.id.in_(filtered_ids))
        else:
            base_query = base_query.filter(EquipmentGroup.id != EquipmentGroup.id)

    total_count = base_query.count()

    rows = (
        base_query.options(
            selectinload(EquipmentGroup.regional_energy_system).selectinload(
                RegionalEnergySystem.union_energy_system
            ),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.regional_district).selectinload(
                RegionalDistrict.regional_energy_systems
            ),
        )
        .order_by(
            EquipmentGroup.name,
            EquipmentGroup.name_ext,
            EquipmentGroup.id,
            EquipmentGroupFuelFormula.year_number,
            EquipmentGroupFuelFormula.variant_number,
        )
        .all()
    )

    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        apply_numb1120_filter_to_eg_param_rows,
    )

    rows, numb1120_filter_choices = apply_numb1120_filter_to_eg_param_rows(
        rows, _filters
    )
    total_count = len(rows)

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": total_count or 1,
        "numb1120_filter_choices": numb1120_filter_choices,
    }


class _MissingYearFuelFormula:
    """Год из интервала без строки в gs_fue_equipment_group_fuel_formula."""

    __slots__ = ("year_number",)

    def __init__(self, year_number: int) -> None:
        self.year_number = int(year_number)

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, name: str):
        return None


def expand_formula_rows_for_year_interval(rows, start_year, end_year):
    """
    Как на ТЭП edit_data: для каждой группы — строки на каждый год интервала.
    Если за год есть несколько формул (variant) — все сохраняются; иначе — пустая заглушка.
    """
    from collections import defaultdict

    if start_year is None or end_year is None:
        return list(rows or [])

    sy, ey = int(start_year), int(end_year)
    if sy > ey:
        sy, ey = ey, sy
    years_range = range(sy, ey + 1)

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
        year_to_params: dict[int, list] = defaultdict(list)
        for _eg, param in eg_rows:
            if not param or isinstance(param, _MissingYearFuelFormula):
                continue
            yn = getattr(param, "year_number", None)
            if yn is not None:
                year_to_params[int(yn)].append(param)
        for y in years_range:
            params = year_to_params.get(y) or []
            if params:
                for p in params:
                    out.append((eg, p))
            else:
                out.append((eg, _MissingYearFuelFormula(y)))
    return out


def _numb1120_merge_key(param):
    if param is None:
        return None
    return getattr(param, "numb1120", None)


def annotate_formula_rows_numb1120_merge(rows, *, include_eg_in_key: bool = True):
    """
    Для подряд идущих строк с одинаковым numb1120 (и при include_eg_in_key — с одной группой ОБ)
    задает numb1120_merge_rowspan на первой строке группы; на остальных — None (ячейки не рисуются).

    rows: list[tuple[EquipmentGroup, EquipmentGroupFuelFormula | None]]
    """
    if not rows:
        return []

    out = []
    i = 0
    n = len(rows)
    while i < n:
        eg, p = rows[i]
        if include_eg_in_key:
            key = (getattr(eg, "id", None), _numb1120_merge_key(p))
        else:
            key = _numb1120_merge_key(p)
        j = i + 1
        while j < n:
            eg2, p2 = rows[j]
            if include_eg_in_key:
                key2 = (getattr(eg2, "id", None), _numb1120_merge_key(p2))
            else:
                key2 = _numb1120_merge_key(p2)
            if key2 != key:
                break
            j += 1
        span = j - i
        for idx in range(i, j):
            eg_r, param = rows[idx]
            out.append(
                {
                    "equipment_group": eg_r,
                    "param": param,
                    "numb1120_merge_rowspan": span if idx == i else None,
                }
            )
        i = j
    return out


def apply_numb1120_merge_to_formula_hierarchy(hierarchy_flat):
    """Проставляет в group_blocks объединение по numb1120 для колонок группы и numb1120."""
    for est in hierarchy_flat or []:
        for ues in est.get("ues_list") or []:
            for res in ues.get("res_list") or []:
                for sb in res.get("station_blocks") or []:
                    for gb in sb.get("group_blocks") or []:
                        raw_rows = gb.get("rows") or []
                        gb["rows"] = annotate_formula_rows_numb1120_merge(
                            raw_rows, include_eg_in_key=False
                        )
    return hierarchy_flat
