# -*- coding: utf-8 -*-
"""Журнал изменений сводок потребления (ОЭС / ФО / энергозоны): типы сущностей Log и запись событий."""
from __future__ import annotations

from typing import Any, Optional

from app.extensions import db
from app.logs.models.log_model import Log
from app.logs.services.log_display_utils import format_logs_for_display
from app.logs.services.logging_service import log_to_db

ENTITY_TYPE_BY_SCOPE = {
    "oes": "energy_consumption_summary_oes",
    "fo": "energy_consumption_summary_fo",
    "ez": "energy_consumption_summary_ez",
}

ACTION_TITLE_BY_SCOPE = {
    "oes": "сводка потребления по ОЭС",
    "fo": "сводка потребления по федеральным округам",
    "ez": "сводка потребления по энергозонам",
}


def entity_type_for_scope(scope: str) -> str:
    return ENTITY_TYPE_BY_SCOPE[scope]


def load_ec_summary_logs_raw(
    scope: str,
    database_version_id: Optional[int],
    *,
    limit: int,
    offset: int = 0,
) -> list[Any]:
    et = ENTITY_TYPE_BY_SCOPE.get(scope)
    if not et:
        return []
    q = db.session.query(Log).filter(Log.entity_type == et)
    if database_version_id is not None:
        q = q.filter(Log.entity_id == int(database_version_id))
    q = q.order_by(Log.timestamp.desc())
    if offset:
        q = q.offset(offset)
    return q.limit(limit).all()


def load_formatted_ec_summary_logs(
    scope: str, database_version_id: Optional[int], *, limit: int = 50
) -> list[dict]:
    logs = load_ec_summary_logs_raw(scope, database_version_id, limit=limit, offset=0)
    return format_logs_for_display(logs)


def count_ec_summary_logs(scope: str, database_version_id: Optional[int]) -> int:
    et = ENTITY_TYPE_BY_SCOPE.get(scope)
    if not et:
        return 0
    q = db.session.query(Log).filter(Log.entity_type == et)
    if database_version_id is not None:
        q = q.filter(Log.entity_id == int(database_version_id))
    return int(q.count())


def log_ec_summary_cell_change(
    user: Any,
    scope: str,
    *,
    detail_chunks: list[str],
    database_version_id: Optional[int],
) -> None:
    if scope not in ENTITY_TYPE_BY_SCOPE or not detail_chunks:
        return
    action_head = ACTION_TITLE_BY_SCOPE.get(scope, "сводка потребления")
    action = f"Изменение: {action_head}"
    details = "; ".join(detail_chunks)
    log_to_db(
        user,
        action,
        details,
        entity_type=ENTITY_TYPE_BY_SCOPE[scope],
        entity_id=database_version_id,
    )


def log_ec_summary_excel_import(user: Any, stats: dict[str, Any], *, database_version_id: Optional[int]) -> None:
    parts = [
        f"обработано_версий_БД={stats.get('database_versions_processed')}",
        f"записей_млн_кВтч={stats.get('cells_written_mln_kvt_ch')}",
        f"записей_СиПР={stats.get('cells_written_sipr')}",
    ]
    if stats.get("mln_sheet_absent"):
        parts.append("лист_млн_кВтч_отсутствует=1")
    if stats.get("sipr_sheet_absent"):
        parts.append("лист_СиПР_отсутствует=1")
    if stats.get("mln_sheet_skipped_no_data_grid"):
        parts.append("лист_млн_без_таблицы_заглушка=1")
    details = "; ".join(parts)
    action = "Импорт сводки потребления из Excel"
    for et in ENTITY_TYPE_BY_SCOPE.values():
        log_to_db(
            user,
            action,
            details,
            entity_type=et,
            entity_id=database_version_id,
        )
