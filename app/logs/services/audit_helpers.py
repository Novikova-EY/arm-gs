# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Sequence

from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import (
    get_field_name_ru,
    format_field_change,
    format_field_value,
)

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
    return f"ids={ids}, наименования={labels}"

def diff_sets(old: Iterable[int], new: Iterable[int]) -> tuple[list[int], list[int]]:
    s_old, s_new = set(int(i) for i in old), set(int(i) for i in new)
    added = sorted(s_new - s_old)
    removed = sorted(s_old - s_new)
    return added, removed

def diff_field(old: Any, new: Any, field_name: str, entity_type: str = None) -> Optional[str]:
    """
    Возвращает строку с описанием изменения поля на русском языке.
    
    Args:
        old: Старое значение
        new: Новое значение
        field_name: Техническое название поля
        entity_type: Тип сущности (опционально)
    
    Returns:
        Строка с описанием изменения или None, если значения совпадают
    """
    if old != new:
        return format_field_change(field_name, old, new, entity_type)
    return None

def summarize_changes(title: str, changes: Sequence[str]) -> str:
    """
    Формирует итоговое сообщение об изменениях.
    
    Args:
        title: Заголовок сообщения
        changes: Список строк с описанием изменений
    
    Returns:
        Строка с итоговым сообщением
    """
    if not changes:
        return f"{title}: нет изменений"
    return f"{title}:\n - " + "\n - ".join(changes)

def format_changes_list(changes: list[str]) -> str:
    """
    Форматирует список изменений в строку для логирования.
    
    Args:
        changes: Список строк с описанием изменений
    
    Returns:
        Строка с перечислением изменений
    """
    if not changes:
        return "нет изменений"
    return "; ".join(changes)
