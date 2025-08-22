# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Sequence

from app.logs.services.logging_service import log_to_db

# Глобальный флаг — можно выключить детальные логи централизованно
AUDIT_DEBUG = True

def dbg(user: Any, action: str, details: Optional[str] = None) -> None:
    """Единая точка для подробных логов."""
    if AUDIT_DEBUG:
        log_to_db(user, action, details)

def format_ids(ids: Iterable[int]) -> str:
    ids = sorted(set(int(i) for i in ids))
    return f"ids={ids}"

def map_names(id_list: Iterable[int], names: Dict[int, str]) -> str:
    ids = sorted(set(int(i) for i in id_list))
    labels = [names.get(i, str(i)) for i in ids]
    return f"ids={ids}, names={labels}"

def diff_sets(old: Iterable[int], new: Iterable[int]) -> tuple[list[int], list[int]]:
    s_old, s_new = set(int(i) for i in old), set(int(i) for i in new)
    added = sorted(s_new - s_old)
    removed = sorted(s_old - s_new)
    return added, removed

def diff_field(old: Any, new: Any, title: str) -> Optional[str]:
    if old != new:
        return f"{title}: {old!r} → {new!r}"
    return None

def summarize_changes(title: str, changes: Sequence[str]) -> str:
    if not changes:
        return f"{title}: нет изменений"
    return f"{title}:\n - " + "\n - ".join(changes)
