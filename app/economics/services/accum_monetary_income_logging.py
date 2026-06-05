# -*- coding: utf-8 -*-
"""Журнал изменений накопленных денежных доходов населения."""

from __future__ import annotations

from typing import Any, Optional

from app.common.services.help_services import format_decimal_trim_for_display
from app.extensions import db
from app.logs.models.log_model import Log
from app.logs.services.log_display_utils import format_logs_for_display
from app.logs.services.logging_service import log_to_db

ENTITY_TYPE = "long_term_accum_monetary_income"
ACTION_TITLE = "накопленные денежные доходы населения (долгосрочный прогноз)"


def _fmt_log_value(value: Any) -> str:
    if value is None:
        return "—"
    s = format_decimal_trim_for_display(value, digits=0)
    return s if s else "—"


def load_accum_monetary_income_logs_raw(
    database_version_id: Optional[int],
    *,
    limit: int,
    offset: int = 0,
) -> list[Log]:
    q = db.session.query(Log).filter(Log.entity_type == ENTITY_TYPE)
    if database_version_id is not None:
        q = q.filter(Log.entity_id == int(database_version_id))
    q = q.order_by(Log.timestamp.desc())
    if offset:
        q = q.offset(offset)
    return q.limit(limit).all()


def load_formatted_accum_monetary_income_logs(
    database_version_id: Optional[int], *, limit: int = 50
) -> list[dict]:
    logs = load_accum_monetary_income_logs_raw(database_version_id, limit=limit, offset=0)
    return format_logs_for_display(logs)


def count_accum_monetary_income_logs(database_version_id: Optional[int]) -> int:
    q = db.session.query(Log).filter(Log.entity_type == ENTITY_TYPE)
    if database_version_id is not None:
        q = q.filter(Log.entity_id == int(database_version_id))
    return int(q.count())


def log_accum_monetary_income_cell_change(
    user: Any,
    *,
    detail_chunks: list[str],
    database_version_id: Optional[int],
) -> None:
    if not detail_chunks:
        return
    action = f"Изменение: {ACTION_TITLE}"
    details = "; ".join(detail_chunks)
    log_to_db(
        user,
        action,
        details,
        entity_type=ENTITY_TYPE,
        entity_id=database_version_id,
    )


def log_accum_monetary_income_excel_import(
    user: Any,
    stats: dict[str, Any],
    *,
    database_version_id: Optional[int],
) -> None:
    parts = [
        f"территорий={stats.get('territories')}",
        f"строк={stats.get('rows_processed')}",
        f"записано_ячеек={stats.get('cells_written')}",
        f"пропущено_ячеек={stats.get('cells_skipped')}",
    ]
    warnings = stats.get("warnings") or []
    if warnings:
        parts.append(f"предупреждений={len(warnings)}")
    details = "; ".join(parts)
    log_to_db(
        user,
        f"Импорт: {ACTION_TITLE} из Excel",
        details,
        entity_type=ENTITY_TYPE,
        entity_id=database_version_id,
    )
