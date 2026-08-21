# -*- coding: utf-8 -*-
"""Отбор EquipmentGroup для этапов расчёта топлива (Коэфф / Распред / …)."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.services.adapters.access_filter_adapter import AccessFilterAdapter
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_row_participates,
)


def dedupe_equipment_group_ids_prefer_version(
    rows: list[tuple[int, int | None, int | None]],
    effective_db_version: int,
) -> list[int]:
    """
    Убирает задвоение: одна и та же станция (numb) часто есть и в версии БД, и с
    database_version_id=NULL. Для сумм «Базовый год» / этапов расчёта оставляем
    строку текущей версии; NULL — только если для этого numb версии нет.

    rows: (id, numb, database_version_id)
    """
    by_numb: dict[int, tuple[int, int | None]] = {}
    no_numb_ids: list[int] = []

    for gid, numb, vid in rows:
        if numb is None:
            no_numb_ids.append(gid)
            continue
        prev = by_numb.get(numb)
        if prev is None:
            by_numb[numb] = (gid, vid)
            continue
        _prev_id, prev_vid = prev
        if prev_vid == effective_db_version:
            continue
        if vid == effective_db_version:
            by_numb[numb] = (gid, vid)

    result = [gid for gid, _vid in by_numb.values()]
    result.extend(no_numb_ids)
    return sorted(result)


def select_equipment_group_ids_for_calculation(
    session: Session,
    *,
    filter_text: object,
    effective_db_version: int | None,
    year_numbers: Sequence[int] | None = None,
) -> list[int]:
    """
    Id групп по Access filter_text и версии БД.

    Условие ved из фильтра Access применяется к EquipmentGroupFuelParam.ved
    (рабочая «Станции(Схема).VED»), а не к EquipmentGroup.vedomstvo.
    При наличии year_numbers строка параметров должна относиться к одному из этих лет
    (обычно base_year и/или расчётный year параметра распределения).

    Это отбор *группы*: ved>0 хотя бы в одном из лет. В циклах Коэфф/Распред/Топливо
    Access проверяет ved ещё раз на *строке года* (FindFirst filter1) — см.
    ``access_ved_filter_year_row_participates``.

    При заданной версии в выборку попадают и versioned, и NULL-группы (как раньше),
    но одинаковый numb не суммируется дважды — приоритет у строки effective_db_version.
    """
    query = session.query(
        EquipmentGroup.id,
        EquipmentGroup.numb,
        EquipmentGroup.database_version_id,
    )

    if effective_db_version is not None and hasattr(EquipmentGroup, "database_version_id"):
        query = query.filter(
            or_(
                EquipmentGroup.database_version_id == effective_db_version,
                EquipmentGroup.database_version_id.is_(None),
            )
        )

    group_expr = AccessFilterAdapter.build_expression(filter_text or "")
    if group_expr is not None:
        query = query.filter(group_expr)

    ved_expr = AccessFilterAdapter.build_ved_expression(filter_text or "")
    if ved_expr is not None:
        years = [int(y) for y in (year_numbers or ()) if y is not None]
        fp_pred = [
            EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
            ved_expr,
        ]
        if years:
            fp_pred.append(EquipmentGroupFuelParam.year_number.in_(years))
        if effective_db_version is not None and hasattr(
            EquipmentGroupFuelParam, "database_version_id"
        ):
            fp_pred.append(
                or_(
                    EquipmentGroupFuelParam.database_version_id == effective_db_version,
                    EquipmentGroupFuelParam.database_version_id.is_(None),
                )
            )
        query = query.filter(exists().where(and_(*fp_pred)))

    rows = [(int(r[0]), r[1], r[2]) for r in query.order_by(EquipmentGroup.id).all()]
    if effective_db_version is None:
        return [gid for gid, _numb, _vid in rows]
    return dedupe_equipment_group_ids_prefer_version(rows, effective_db_version)


def access_ved_filter_year_row_participates(param: EquipmentGroupFuelParam | None) -> bool:
    """
    Access: ``(ved>0)`` на конкретной строке года «Станции(Схема)».

    Строка с ved=0/NULL (оболочка родителя / выключенный ребёнок) не входит
    в FindFirst/FindNext filter1 — её не пишут Коэфф/Распред/Топливо.
    """
    return fuel_param_row_participates(param)


def _pick_best_fuel_param_row_for_year(
    existing: EquipmentGroupFuelParam | None,
    candidate: EquipmentGroupFuelParam,
    effective_db_version: int | None,
) -> EquipmentGroupFuelParam:
    def tier(r: EquipmentGroupFuelParam) -> int:
        vid = getattr(r, "database_version_id", None)
        if effective_db_version is None:
            return 2
        if vid == effective_db_version:
            return 3
        if vid is None:
            return 2
        return 1

    if existing is None or tier(candidate) > tier(existing):
        return candidate
    return existing


def participating_group_ids_for_year(
    session: Session,
    group_ids: Sequence[int],
    *,
    year_number: int,
    effective_db_version: int | None,
) -> list[int]:
    """
    Из уже отобранных групп оставить те, у кого FuelParam за year_number с ved>0.

    Access: count/цикл «Топливо» — ``filter1 and (year=cyear)``.
    """
    ids = [int(gid) for gid in group_ids if gid is not None]
    if not ids:
        return []
    rows = (
        session.query(EquipmentGroupFuelParam)
        .filter(
            EquipmentGroupFuelParam.equipment_group_id.in_(ids),
            EquipmentGroupFuelParam.year_number == int(year_number),
        )
        .all()
    )
    by_gid: dict[int, EquipmentGroupFuelParam] = {}
    for row in rows:
        gid = getattr(row, "equipment_group_id", None)
        if gid is None:
            continue
        key = int(gid)
        by_gid[key] = _pick_best_fuel_param_row_for_year(
            by_gid.get(key), row, effective_db_version
        )
    return [
        gid for gid in ids if access_ved_filter_year_row_participates(by_gid.get(gid))
    ]
