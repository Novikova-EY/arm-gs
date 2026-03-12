#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сервисы для страницы «Топливные параметры групп оборудования (доп.)» (v2)."""

from collections import defaultdict

from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)


def _safe_int(value):
    try:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def attach_extra_fuel_params_to_station_groups(stations, selected_year=None):
    """
    Вешает extra_fuel_params на элементы group в station.equipment_group_v2_groups.
    Сопоставление по EquipmentGroup.id (equipment_group_id).
    При загрузке из Excel: EquipmentGroup.numb == EquipmentGroupExtraFuelParam.numb1120.
    """
    if not stations:
        return
    version_id = get_current_db_version_id()

    equipment_group_ids = set()
    for station in stations:
        for group in getattr(station, "equipment_group_v2_groups", []) or []:
            eg = group.get("equipment_group")
            if eg and getattr(eg, "id", None):
                equipment_group_ids.add(eg.id)

    if not equipment_group_ids:
        return

    query = EquipmentGroupExtraFuelParam.query.filter(
        EquipmentGroupExtraFuelParam.equipment_group_id.in_(list(equipment_group_ids))
    )
    if selected_year is not None:
        query = query.filter(EquipmentGroupExtraFuelParam.year_number == selected_year)
    if version_id is None:
        query = query.filter(EquipmentGroupExtraFuelParam.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroupExtraFuelParam.database_version_id == version_id)

    params = query.all()
    params_by_group = defaultdict(list)
    for p in params:
        if p.equipment_group_id is not None:
            params_by_group[p.equipment_group_id].append(p)

    for station in stations:
        for group in getattr(station, "equipment_group_v2_groups", []) or []:
            eg = group.get("equipment_group")
            eg_id = getattr(eg, "id", None) if eg else None
            group["extra_fuel_params"] = (
                sorted(params_by_group.get(eg_id, []), key=lambda p: p.year_number or 0)
                if eg_id is not None
                else []
            )
