# -*- coding: utf-8 -*-
"""Журнал изменений сводок нагрузок (ОЭС / ФО / энергозоны): типы сущностей Log и запись событий."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import or_

from app.extensions import db
from app.logs.models.log_model import Log
from app.logs.services.log_display_utils import format_logs_for_display
from app.logs.services.logging_service import log_to_db

ENTITY_TYPE_BY_SCOPE = {
    "oes": "power_demand_summary_oes",
    "fo": "power_demand_summary_fo",
    "ez": "power_demand_summary_ez",
}

ACTION_TITLE_BY_SCOPE = {
    "oes": "сводка нагрузок по ОЭС",
    "fo": "сводка нагрузок по федеральным округам",
    "ez": "сводка нагрузок по энергозонам",
}

# Журнал на сводках: первая порция и шаг «Показать ещё».
PD_SUMMARY_LOGS_INITIAL_LIMIT = 10
PD_SUMMARY_LOGS_LOAD_MORE_LIMIT = 20


def entity_type_for_scope(scope: str) -> str:
    return ENTITY_TYPE_BY_SCOPE[scope]


def pd_summary_logs_version_filter(database_version_id: int):
    """Записи журнала сводки: entity_id=версия или database_version_id=версия.

    При записи entity_id берётся из строки параметров и может быть NULL, тогда
    версия остаётся только в database_version_id (log_to_db). Фильтр только по
    entity_id тогда даёт пустой журнал.
    """
    vid = int(database_version_id)
    return or_(Log.entity_id == vid, Log.database_version_id == vid)


def _pd_summary_logs_query(scope: str, database_version_id: Optional[int]):
    et = ENTITY_TYPE_BY_SCOPE.get(scope)
    if not et:
        return None
    q = db.session.query(Log).filter(Log.entity_type == et)
    if database_version_id is not None:
        q = q.filter(pd_summary_logs_version_filter(database_version_id))
    return q.order_by(Log.timestamp.desc())


def load_pd_summary_logs_raw(
    scope: str,
    database_version_id: Optional[int],
    *,
    limit: int,
    offset: int = 0,
) -> list[Any]:
    q = _pd_summary_logs_query(scope, database_version_id)
    if q is None:
        return []
    if offset:
        q = q.offset(offset)
    return q.limit(limit).all()


def load_formatted_pd_summary_logs(
    scope: str, database_version_id: Optional[int], *, limit: int | None = None
) -> list[dict]:
    if limit is None:
        limit = PD_SUMMARY_LOGS_INITIAL_LIMIT
    logs = load_pd_summary_logs_raw(scope, database_version_id, limit=limit, offset=0)
    return format_logs_for_display(logs)


def count_pd_summary_logs(scope: str, database_version_id: Optional[int]) -> int:
    q = _pd_summary_logs_query(scope, database_version_id)
    if q is None:
        return 0
    return int(q.count())


def log_pd_summary_cell_change(
    user: Any,
    scope: str,
    *,
    detail_chunks: list[str],
    database_version_id: Optional[int],
) -> None:
    if scope not in ENTITY_TYPE_BY_SCOPE or not detail_chunks:
        return
    action_head = ACTION_TITLE_BY_SCOPE.get(scope, "сводка нагрузок")
    action = f"Изменение: {action_head}"
    details = "; ".join(detail_chunks)
    log_to_db(
        user,
        action,
        details,
        entity_type=ENTITY_TYPE_BY_SCOPE[scope],
        entity_id=database_version_id,
    )
