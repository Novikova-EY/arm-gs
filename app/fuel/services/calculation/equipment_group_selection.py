# -*- coding: utf-8 -*-
"""Отбор EquipmentGroup для этапов расчёта топлива (Коэфф / Распред / …)."""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.adapters.access_filter_adapter import AccessFilterAdapter


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
) -> list[int]:
    """
    Id групп по Access filter_text и версии БД.

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

    expr = AccessFilterAdapter.build_expression(filter_text or "")
    if expr is not None:
        query = query.filter(expr)

    rows = [(int(r[0]), r[1], r[2]) for r in query.order_by(EquipmentGroup.id).all()]
    if effective_db_version is None:
        return [gid for gid, _numb, _vid in rows]
    return dedupe_equipment_group_ids_prefer_version(rows, effective_db_version)
