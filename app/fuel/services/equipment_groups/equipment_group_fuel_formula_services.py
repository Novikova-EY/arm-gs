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
    per_page=10,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Список (EquipmentGroup, EquipmentGroupFuelFormula) по фильтрам станций.
    Все годы из БД (ограничение по year_number не применяется).
    Для территориального отбора групп используется диапазон лет из справочника.
    """
    from app.common.services.get_services.years.years_get_services import (
        get_filter_end_year,
        get_filter_start_year,
    )
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from sqlalchemy.orm import selectinload

    _start = start_year if start_year is not None else get_filter_start_year()
    _end = end_year if end_year is not None else get_filter_end_year()
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
    join_cond = and_(
        EquipmentGroupFuelFormula.equipment_group_id == EquipmentGroup.id,
        version_match,
    )

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

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": total_count or 1,
    }


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
