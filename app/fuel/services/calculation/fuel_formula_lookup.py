# -*- coding: utf-8 -*-
"""Отбор формул топлива как Access topl.Seek (Кнопка49).

topl.Index = numb2; Seek \">=\", numb1120, v, byear; последняя year ≤ cyear.
Годы раньше byear не входят. Нет строк в окне → None (Skip / ошибка без записи на базовый год).
Пустая formtxt в окне — Match (как в таблице Access); разбор тогда не из чего делать.
"""
from __future__ import annotations

from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.services.calculation.specific_consumption_lookup import (
    pick_specific_consumption_access_seek,
)


def pick_fuel_formula_access_seek(rows, *, byear: int | None, cyear: int):
    """Последняя формула этой станции с byear ≤ year ≤ cyear. Без шага раньше byear."""
    return pick_specific_consumption_access_seek(rows, byear=byear, cyear=cyear)


def query_fuel_formula_access_seek(
    session,
    *,
    equipment_group_id: int,
    byear: int | None,
    cyear: int,
    variant_number: int = 0,
    database_version_id: int | None = None,
) -> EquipmentGroupFuelFormula | None:
    q = session.query(EquipmentGroupFuelFormula).filter(
        EquipmentGroupFuelFormula.equipment_group_id == int(equipment_group_id),
        EquipmentGroupFuelFormula.year_number <= int(cyear),
        EquipmentGroupFuelFormula.variant_number == int(variant_number),
    )
    if byear is not None:
        q = q.filter(EquipmentGroupFuelFormula.year_number >= int(byear))
    if database_version_id is not None:
        q = q.filter(
            (EquipmentGroupFuelFormula.database_version_id == database_version_id)
            | (EquipmentGroupFuelFormula.database_version_id.is_(None))
        )
    rows = q.all()
    return pick_fuel_formula_access_seek(rows, byear=byear, cyear=cyear)
