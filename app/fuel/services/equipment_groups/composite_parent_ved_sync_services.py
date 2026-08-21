# -*- coding: utf-8 -*-
"""
После импорта/перезагрузки Access: выставить FuelParam.ved=0 у родителя составной
станции за годы, где есть дочерние строки с ved>0 (антидубль как в Access VBA).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_ved_participates,
    is_composite_child_group,
    is_composite_parent_group,
)


def sync_composite_parent_ved_zero(
    session: Session | None = None,
    *,
    database_version_id: int | None = None,
    year_numbers: list[int] | None = None,
) -> int:
    """
    Для каждой пары (родитель COMP=1, дети MAIN=parent.numb):
    если за год у ребёнка ved>0, у родителя за тот же год ставим ved=0.

    Возвращает число обновлённых строк FuelParam родителя.
    """
    sess = session or db.session
    q = sess.query(EquipmentGroup)
    if database_version_id is not None and hasattr(EquipmentGroup, "database_version_id"):
        q = q.filter(
            (EquipmentGroup.database_version_id == database_version_id)
            | (EquipmentGroup.database_version_id.is_(None))
        )
    groups = q.all()
    parents = [g for g in groups if is_composite_parent_group(g) and g.numb is not None]
    children_by_main: dict[int, list[EquipmentGroup]] = {}
    for g in groups:
        if is_composite_child_group(g) and g.main is not None:
            children_by_main.setdefault(int(g.main), []).append(g)

    updated = 0
    for parent in parents:
        kids = children_by_main.get(int(parent.numb), [])
        if not kids:
            continue
        kid_ids = [k.id for k in kids]
        parent_params_q = sess.query(EquipmentGroupFuelParam).filter(
            EquipmentGroupFuelParam.equipment_group_id == parent.id
        )
        child_params_q = sess.query(EquipmentGroupFuelParam).filter(
            EquipmentGroupFuelParam.equipment_group_id.in_(kid_ids)
        )
        if year_numbers:
            parent_params_q = parent_params_q.filter(
                EquipmentGroupFuelParam.year_number.in_(year_numbers)
            )
            child_params_q = child_params_q.filter(
                EquipmentGroupFuelParam.year_number.in_(year_numbers)
            )
        active_years = {
            int(p.year_number)
            for p in child_params_q.all()
            if p.year_number is not None and fuel_param_ved_participates(p.ved)
        }
        if not active_years:
            continue
        for pp in parent_params_q.all():
            if pp.year_number is None or int(pp.year_number) not in active_years:
                continue
            if pp.ved is not None and int(pp.ved) == 0:
                continue
            pp.ved = 0
            sess.add(pp)
            updated += 1
    if updated:
        sess.flush()
    return updated
