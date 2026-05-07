# -*- coding: utf-8 -*-
"""Форматирование записей Log для отображения в шаблонах (МСК, версии БД)."""
from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo

from app.extensions import db

MOSCOW = ZoneInfo("Europe/Moscow")


def format_logs_for_display(logs):
    """
    Предварительное форматирование логов для оптимизации рендеринга шаблона.
    Даты в Europe/Moscow; lower() для сортировки/фильтра в JS.
    """
    if not logs:
        return []

    from app.common.models.database_version_model import DatabaseVersion

    version_ids = {log.database_version_id for log in logs if log.database_version_id}
    versions_map: dict[int, str] = {}
    if version_ids:
        try:
            versions = (
                db.session.query(DatabaseVersion.id, DatabaseVersion.version_number)
                .filter(DatabaseVersion.id.in_(version_ids))
                .all()
            )
            versions_map = {v.id: v.version_number for v in versions}
        except Exception:
            versions_map = {vid: str(vid) for vid in version_ids}

    def _suppress_noop_changes(details_text: str) -> str:
        if not details_text:
            return ""

        def _norm(s: str) -> str:
            if s is None:
                return ""
            s2 = s.replace("\u00A0", " ").replace("\xa0", " ").strip().lower()
            while "  " in s2:
                s2 = s2.replace("  ", " ")
            return s2

        parts = [p.strip() for p in details_text.split(";")]
        filtered: list[str] = []
        for p in parts:
            if not p:
                continue
            if "→" in p:
                left, right = p.split("→", 1)
                if _norm(left) == _norm(right):
                    continue
                left_value = left.rsplit("-", 1)[-1].strip() if "-" in left else left
                right_value = right
                if _norm(left_value) == _norm(right_value):
                    continue
            filtered.append(p)
        return "; ".join(filtered)

    formatted_logs: list[dict] = []
    for log in logs:
        details_clean = _suppress_noop_changes(log.details or "")
        ts = log.timestamp
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_msk = ts.astimezone(MOSCOW)
        else:
            ts_msk = None
        formatted_logs.append(
            {
                "date": ts_msk.strftime("%Y-%m-%d") if ts_msk else "",
                "time": ts_msk.strftime("%H:%M:%S") if ts_msk else "",
                "username": log.username or "",
                "username_lower": (log.username or "").lower(),
                "action": log.action or "",
                "action_lower": (log.action or "").lower(),
                "details": details_clean,
                "details_lower": details_clean.lower(),
                "database_version": versions_map.get(log.database_version_id, "—")
                if log.database_version_id
                else "—",
            }
        )
    return formatted_logs
