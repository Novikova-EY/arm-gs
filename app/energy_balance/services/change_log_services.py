# -*- coding: utf-8 -*-
"""Журнал изменений раздела «Балансы электрической энергии и мощности».

Строки изменений повторяют формат карточки агрегата:
«<что>: было <старое> → стало <новое>».
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from app.logs.services.logging_service import log_to_db

# Тип сущности в журнале: события всего раздела энергобалансов.
ENTITY_TYPE = "energy_balance"
NOT_SET = "не указано"


def format_change_number(value: Any) -> str:
    """Число как на страницах: «1234,5» — запятая и без лишних нулей."""
    if value is None or value == "":
        return NOT_SET
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value).strip() or NOT_SET
    if not number.is_finite():
        return str(value)
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".") or "0"
    return text.replace(".", ",")


def format_change_text(value: Any) -> str:
    if value is None:
        return NOT_SET
    return str(value).strip() or NOT_SET


def values_equal(left: Any, right: Any) -> bool:
    """Сравнивает значения ячеек: пустое и отсутствующее считаются одним и тем же."""
    empty = (None, "")
    if left in empty and right in empty:
        return True
    if left in empty or right in empty:
        return False
    left_number = _as_decimal(left)
    right_number = _as_decimal(right)
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return str(left).strip() == str(right).strip()


def _as_decimal(value: Any) -> Decimal | None:
    """Число из Decimal, int, float или строки с точкой/запятой."""
    text = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def value_change(label: str, old_value: Any, new_value: Any, *, number: bool = True) -> str:
    """Строка «было → стало» для журнала."""
    format_value = format_change_number if number else format_change_text
    return f"{label}: было {format_value(old_value)} → стало {format_value(new_value)}"


def log_energy_balance_change(
    user: Any,
    action: str,
    changes: Iterable[str],
    *,
    context: Optional[str] = None,
) -> None:
    """Пишет запись журнала, если есть хотя бы одна строка изменений."""
    lines = [str(line) for line in changes if line]
    if not lines:
        return
    details_parts = [context] if context else []
    details_parts.extend(lines)
    log_to_db(
        user if user is not None else _current_user_or_none(),
        action,
        details="\n".join(details_parts),
        entity_type=ENTITY_TYPE,
    )


def log_cell_change(
    user: Any,
    action: str,
    label: str,
    old_value: Any,
    new_value: Any,
    *,
    context: Optional[str] = None,
    number: bool = True,
) -> None:
    """Пишет изменение одной ячейки; совпадающие значения не логирует."""
    if values_equal(old_value, new_value):
        return
    log_energy_balance_change(
        user,
        action,
        [value_change(label, old_value, new_value, number=number)],
        context=context,
    )


def _current_user_or_none() -> Any:
    try:
        from flask_login import current_user

        return current_user
    except Exception:
        return None
