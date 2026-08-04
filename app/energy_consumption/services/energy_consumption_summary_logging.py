# -*- coding: utf-8 -*-
"""Журнал изменений сводок потребления (ОЭС / ФО / энергозоны): типы сущностей Log и запись событий."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import or_

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

GAES_CHARGE_TABLE_LABEL = (
    "Потребление электрической энергии ГАЭС на заряд, млн кВтч"
)

def _is_gaes_charge_station_log(log: Log) -> bool:
    if (log.entity_type or "") != "station":
        return False
    action = (log.action or "").lower()
    return "гаэс на заряд" in action and "потребление" in action


def _is_gaes_charge_summary_log(log: Log) -> bool:
    et = log.entity_type or ""
    if et not in ENTITY_TYPE_BY_SCOPE.values():
        return False
    details = log.details or ""
    if GAES_CHARGE_TABLE_LABEL in details:
        return True
    if "таблица=" in details and "гаэс на заряд" in details.lower():
        return True
    return False


def _log_ts_bucket(log: Log) -> tuple[Any, str]:
    ts = log.timestamp
    if ts is not None:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts = ts.replace(microsecond=0)
    return ts, (log.username or "").lower()


def _dedupe_gaes_charge_log_pairs(logs: list[Log]) -> list[Log]:
    """Убирает дубли station+summary при перекрёстной записи (одно сохранение — две строки)."""
    summary_from_station_card: set[tuple[Any, str]] = set()
    for log in logs:
        if not _is_gaes_charge_summary_log(log):
            continue
        if "источник=карточка электростанции" in (log.details or ""):
            summary_from_station_card.add(_log_ts_bucket(log))

    out: list[Log] = []
    for log in logs:
        if (
            _is_gaes_charge_station_log(log)
            and _log_ts_bucket(log) in summary_from_station_card
        ):
            continue
        out.append(log)
    return out


def _merge_logs_by_timestamp(log_lists: Iterable[list[Log]]) -> list[Log]:
    seen_ids: set[int] = set()
    merged: list[Log] = []
    for chunk in log_lists:
        for log in chunk:
            if log.id in seen_ids:
                continue
            seen_ids.add(log.id)
            merged.append(log)
    merged.sort(
        key=lambda log: log.timestamp or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return _dedupe_gaes_charge_log_pairs(merged)


def _summary_logs_query_for_scope(scope: str, database_version_id: Optional[int]):
    et = ENTITY_TYPE_BY_SCOPE.get(scope)
    if not et:
        return None
    q = db.session.query(Log).filter(Log.entity_type == et)
    if database_version_id is not None:
        q = q.filter(Log.entity_id == int(database_version_id))
    return q.order_by(Log.timestamp.desc())


def _station_gaes_charge_logs_query(database_version_id: Optional[int]):
    q = db.session.query(Log).filter(
        Log.entity_type == "station",
        Log.action.ilike("%потребление%ГАЭС на заряд%"),
    )
    if database_version_id is not None:
        q = q.filter(Log.database_version_id == int(database_version_id))
    return q.order_by(Log.timestamp.desc())


def _station_gaes_charge_summary_logs_query(station_entity_ids: list[int]):
    if not station_entity_ids:
        return db.session.query(Log).filter(False)
    id_markers = [f"(id={eid})" for eid in station_entity_ids]
    station_match = or_(*[Log.details.contains(marker) for marker in id_markers])
    q = db.session.query(Log).filter(
        Log.entity_type.in_(list(ENTITY_TYPE_BY_SCOPE.values())),
        station_match,
    )
    q = q.filter(
        or_(
            Log.details.contains(GAES_CHARGE_TABLE_LABEL),
            Log.details.ilike("%таблица=%гаэс на заряд%"),
        )
    )
    return q.order_by(Log.timestamp.desc())


def _fmt_gaes_charge_log_value(value: Any) -> str:
    if value is None:
        return "не указано"
    try:
        return str(value).replace(".", ",").rstrip("0").rstrip(",") or "0"
    except Exception:
        return str(value).replace(".", ",")


def _log_gaes_charge_to_summary_scopes(
    user: Any,
    *,
    detail_chunks: list[str],
    database_version_id: Optional[int],
    scopes: Optional[list[str]] = None,
) -> None:
    """Дублирует запись в журналы сводок ОЭС / ФО / энергозон."""
    if not detail_chunks:
        return
    for scope in scopes or list(ENTITY_TYPE_BY_SCOPE):
        log_ec_summary_cell_change(
            user,
            scope,
            detail_chunks=detail_chunks,
            database_version_id=database_version_id,
        )


def log_gaes_charge_from_summary_table(
    user: Any,
    *,
    summary_log_scope: str,
    station_id: int,
    station_name: str,
    rd_name: str,
    year: int,
    old_val: Any,
    new_val: Any,
    database_version_id: Optional[int],
) -> None:
    """Журнал сводки потребления и карточки станции при правке ячейки на сводной таблице ГАЭС."""
    if summary_log_scope not in ENTITY_TYPE_BY_SCOPE:
        return
    change_line = (
        f"{year} г.: {_fmt_gaes_charge_log_value(old_val)} → "
        f"{_fmt_gaes_charge_log_value(new_val)}"
    )
    summary_chunks = [
        f"таблица={GAES_CHARGE_TABLE_LABEL}",
        f"электростанция={station_name} (id={station_id})",
        change_line,
    ]
    _log_gaes_charge_to_summary_scopes(
        user,
        detail_chunks=summary_chunks,
        database_version_id=database_version_id,
    )
    log_to_db(
        user,
        (
            f"Изменения в электростанции {station_name} ({rd_name}), "
            f"потребление электроэнергии ГАЭС на заряд (млн кВтч) "
            f"(со сводной таблицы потребления)"
        ),
        details=change_line,
        entity_type="station",
        entity_id=station_id,
    )


def log_gaes_charge_from_station_details(
    user: Any,
    *,
    station_id: int,
    station_name: str,
    change_lines: list[str],
    database_version_id: Optional[int],
) -> None:
    """Журнал сводок ОЭС / ФО / ЭЗ при правке таблицы ГАЭС на карточке электростанции."""
    if not change_lines:
        return
    details = "; ".join(change_lines)
    summary_chunks = [
        f"таблица={GAES_CHARGE_TABLE_LABEL}",
        f"электростанция={station_name} (id={station_id})",
        f"источник=карточка электростанции",
        details,
    ]
    _log_gaes_charge_to_summary_scopes(
        user,
        detail_chunks=summary_chunks,
        database_version_id=database_version_id,
    )


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


def load_ec_gaes_charge_logs_raw(
    scope: str,
    database_version_id: Optional[int],
    *,
    limit: int,
    offset: int = 0,
) -> list[Log]:
    """Журнал таблицы ГАЭС на заряд: сводка + карточки электростанций (текущая версия БД)."""
    fetch_n = max(limit + offset, limit)
    summary_q = _summary_logs_query_for_scope(scope, database_version_id)
    station_q = _station_gaes_charge_logs_query(database_version_id)
    summary_rows = summary_q.limit(fetch_n * 2).all() if summary_q is not None else []
    station_rows = station_q.limit(fetch_n * 2).all() if station_q is not None else []
    summary_rows = [log for log in summary_rows if _is_gaes_charge_summary_log(log)]
    station_rows = [log for log in station_rows if _is_gaes_charge_station_log(log)]
    merged = _merge_logs_by_timestamp([summary_rows, station_rows])
    return merged[offset : offset + limit]


def load_formatted_ec_summary_logs(
    scope: str, database_version_id: Optional[int], *, limit: int = 50
) -> list[dict]:
    logs = load_ec_summary_logs_raw(scope, database_version_id, limit=limit, offset=0)
    return format_logs_for_display(logs)


def load_formatted_ec_gaes_charge_logs(
    scope: str, database_version_id: Optional[int], *, limit: int = 50
) -> list[dict]:
    logs = load_ec_gaes_charge_logs_raw(
        scope, database_version_id, limit=limit, offset=0
    )
    return format_logs_for_display(logs)


def count_ec_summary_logs(scope: str, database_version_id: Optional[int]) -> int:
    et = ENTITY_TYPE_BY_SCOPE.get(scope)
    if not et:
        return 0
    q = db.session.query(Log).filter(Log.entity_type == et)
    if database_version_id is not None:
        q = q.filter(Log.entity_id == int(database_version_id))
    return int(q.count())


def count_ec_gaes_charge_logs(scope: str, database_version_id: Optional[int]) -> int:
    fetch_n = 10000
    return len(
        load_ec_gaes_charge_logs_raw(
            scope, database_version_id, limit=fetch_n, offset=0
        )
    )


def load_merged_station_gaes_charge_logs_raw(
    station_entity_ids: list[int],
    *,
    limit: int,
    offset: int = 0,
    station_logs_query,
) -> list[Log]:
    """Карточка станции: журнал станции + записи сводки по таблице ГАЭС на заряд."""
    fetch_n = max(limit + offset, limit)
    station_rows = station_logs_query.limit(fetch_n * 2).all()
    summary_rows = _station_gaes_charge_summary_logs_query(station_entity_ids).limit(
        fetch_n * 2
    ).all()
    summary_rows = [log for log in summary_rows if _is_gaes_charge_summary_log(log)]
    merged = _merge_logs_by_timestamp([station_rows, summary_rows])
    return merged[offset : offset + limit]


def count_merged_station_gaes_charge_logs(
    station_entity_ids: list[int],
    *,
    station_logs_query,
) -> int:
    return len(
        load_merged_station_gaes_charge_logs_raw(
            station_entity_ids,
            limit=10000,
            offset=0,
            station_logs_query=station_logs_query,
        )
    )


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
