# -*- coding: utf-8 -*-
"""Журнал модуля «Экология»: посещение страниц и вкладок, правки, файлы.

Строки изменений повторяют формат карточки агрегата:
«<что>: было <старое> → стало <новое>».
Все события пишутся с entity_type=ENTITY_TYPE, чтобы журнал фильтровался по модулю.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from flask import has_request_context, request, session
from flask_login import current_user

from app.common.services.help_services import format_decimal_trim_for_display
from app.ecology.services.ecology_decimal_helpers import (
    decimal_from_loose_text,
    drop_float_noise,
)
from app.ecology.services.gis_tes_fuel_comparison_constants import (
    COMPARISON_SHEETS,
    KEY_LABELS,
    PG_ECOLOGY_OVERLAY_BY_KEY,
    ZV_ECOLOGY_OVERLAY_BY_KEY,
)
from app.ecology.services.new_tes_constants import (
    CAPACITY_GT100_KEY,
    CAPACITY_LE100_KEY,
    NORM_COLUMNS,
)
from app.ecology.services.operating_tes_constants import (
    CHAR_COLUMNS,
    CHAR_HEADER_GROUPS,
    COEFF_KINDS,
    COEFFICIENT_AFFILIATIONS,
    COEFFICIENT_TERRITORIES,
    FUEL_ROWS,
    TERRITORIES,
)
from app.logs.services.logging_service import PAGE_VIEW_ACTION_PREFIX, log_to_db

ENTITY_TYPE = "ecology"
MODULE_TITLE = "Экология"
NOT_SET = "не указано"

# Текст формулы целиком в журнал не пишем: он длинный и повторяется в /ecology/formulas/.
MAX_TEXT_IN_LOG = 500
# Пакет из модуля «Топливо» может менять сотни ячеек – журнал не должен расти без предела.
MAX_CHANGES_IN_LOG = 100

_TERRITORY_LABELS = {
    item["slug"]: item["sheet_name"]
    for item in (*TERRITORIES, *COEFFICIENT_TERRITORIES)
}
_AFFILIATION_LABELS = {
    **{item["slug"]: item["label"] for item in COEFFICIENT_AFFILIATIONS},
    "all": "Все принадлежности",
}
_COEFFICIENT_LABELS = {item["key"]: item["label"] for item in COEFF_KINDS}
_CHARACTERISTIC_SHORTS = dict(CHAR_COLUMNS)
_CHARACTERISTIC_TITLES = {
    key: group["title"] for group in CHAR_HEADER_GROUPS for key in group["keys"]
}
_FUEL_LABELS = {item["key"]: item["label"] for item in FUEL_ROWS}
_NORM_LABELS = {key: label for key, label in NORM_COLUMNS}
_NORM_LABELS.update(co="CO", pg="ПГ")
_CAPACITY_LABELS = {
    CAPACITY_LE100_KEY: "до 100 МВт",
    CAPACITY_GT100_KEY: "более 100 МВт",
}
_ANALYSIS_FIELD_LABELS = {
    field: KEY_LABELS.get(excel_key, field)
    for overlay in (PG_ECOLOGY_OVERLAY_BY_KEY, ZV_ECOLOGY_OVERLAY_BY_KEY)
    for excel_key, field in overlay.items()
}
_COMPARISON_SHEET_TITLES = {
    item["slug"]: item["page_title"] for item in COMPARISON_SHEETS
}


def territory_label(slug: Any) -> str:
    return _TERRITORY_LABELS.get(str(slug or ""), str(slug or "")) or NOT_SET


def affiliation_label(slug: Any) -> str:
    return _AFFILIATION_LABELS.get(str(slug or ""), str(slug or "")) or NOT_SET


def coefficient_label(kind: Any) -> str:
    return _COEFFICIENT_LABELS.get(str(kind or ""), str(kind or ""))


def characteristic_label(field: Any) -> str:
    key = str(field or "")
    short = _CHARACTERISTIC_SHORTS.get(key, key)
    title = _CHARACTERISTIC_TITLES.get(key)
    return f"{title} ({short})" if title else short


def fuel_label(key: Any) -> str:
    return _FUEL_LABELS.get(str(key or ""), str(key or ""))


def norm_label(kind: Any, capacity_class: Any) -> str:
    label = _NORM_LABELS.get(str(kind or ""), str(kind or ""))
    capacity = _CAPACITY_LABELS.get(str(capacity_class or ""))
    return f"{label} ({capacity})" if capacity else label


def analysis_field_label(field: Any) -> str:
    key = str(field or "")
    return _ANALYSIS_FIELD_LABELS.get(key, key)


def comparison_sheet_title(slug: Any) -> str:
    return _COMPARISON_SHEET_TITLES.get(str(slug or ""), str(slug or "")) or NOT_SET


def context_lines(*pairs: tuple[str, Any]) -> list[str]:
    """Детали журнала «ключ=значение»; пустые значения не пишем."""
    return [
        f"{name}={value}"
        for name, value in pairs
        if value is not None and str(value).strip() != ""
    ]


def format_change_number(value: Any) -> str:
    """Число как на страницах: «1234,5» – запятая, группировка тысяч, без лишних нулей."""
    if value is None or value == "":
        return NOT_SET
    # digits=0 – без округления: в журнале нужно само значение, а не округлённое.
    # drop_float_noise убирает хвост double (1,1000000000000001 → 1,1), как на страницах.
    number = drop_float_noise(value)
    text = format_decimal_trim_for_display(
        number if number is not None else value, digits=0
    )
    if text and text != "–":
        return text
    return str(value).strip() or NOT_SET


def format_change_text(value: Any) -> str:
    if value is None:
        return NOT_SET
    text = str(value).strip()
    if not text:
        return NOT_SET
    if len(text) > MAX_TEXT_IN_LOG:
        return f"{text[:MAX_TEXT_IN_LOG]}… (символов: {len(text)})"
    return text


def values_equal(left: Any, right: Any) -> bool:
    """Сравнивает значения ячеек: пустое и отсутствующее считаются одним и тем же."""
    empty = (None, "")
    if left in empty and right in empty:
        return True
    if left in empty or right in empty:
        return False
    left_number = drop_float_noise(decimal_from_loose_text(left))
    right_number = drop_float_noise(decimal_from_loose_text(right))
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return str(left).strip() == str(right).strip()


def value_change(label: str, old_value: Any, new_value: Any, *, number: bool = True) -> str:
    """Строка «было → стало» для журнала."""
    format_value = format_change_number if number else format_change_text
    return (
        f"{label}: было {format_value(old_value)} → стало {format_value(new_value)}"
    )


def change_lines(
    changes: Iterable[tuple[str, Any, Any]], *, number: bool = True
) -> list[str]:
    """Строки «было → стало» только для реально изменившихся значений."""
    return [
        value_change(label, old_value, new_value, number=number)
        for label, old_value, new_value in changes
        if not values_equal(old_value, new_value)
    ]


def log_page_visit(
    page_title: str,
    *,
    tab: Optional[str] = None,
    details: Optional[Iterable[str]] = None,
) -> None:
    """Открытие страницы или вкладки модуля (дубль middleware подавляется)."""
    action = f"{PAGE_VIEW_ACTION_PREFIX}: {MODULE_TITLE} – {page_title}"
    if tab:
        action += f", вкладка «{tab}»"
    parts: list[str] = []
    if has_request_context():
        parts.append(f"url={request.full_path}")
    parts.append(f"раздел={MODULE_TITLE}")
    if tab:
        parts.append(f"вкладка={tab}")
    parts.extend(item for item in (details or ()) if item)
    log_to_db(_actor(), action, "; ".join(parts), entity_type=ENTITY_TYPE)


def log_changes(
    action_title: str,
    changes: Iterable[str],
    *,
    context: Optional[Iterable[str]] = None,
) -> None:
    """Изменения полей модуля; без изменений запись не создаётся."""
    lines = [str(item) for item in changes if item]
    if not lines:
        return
    parts = [item for item in (context or ()) if item]
    if len(lines) > MAX_CHANGES_IN_LOG:
        parts.append(f"показаны первые {MAX_CHANGES_IN_LOG} из {len(lines)} изменений")
        lines = lines[:MAX_CHANGES_IN_LOG]
    parts.extend(lines)
    log_to_db(
        _actor(),
        f"Изменение: {MODULE_TITLE} – {action_title}",
        "; ".join(parts),
        entity_type=ENTITY_TYPE,
    )


def log_cell_change(
    action_title: str,
    label: str,
    old_value: Any,
    new_value: Any,
    *,
    context: Optional[Iterable[str]] = None,
    number: bool = True,
) -> None:
    """Правка одной ячейки; совпадающие значения не логируются."""
    if values_equal(old_value, new_value):
        return
    log_changes(
        action_title,
        [value_change(label, old_value, new_value, number=number)],
        context=context,
    )


def log_event(action_title: str, details: Optional[Iterable[str]] = None) -> None:
    """Событие модуля без «до/после»: решение по пакету, импорт и т.п."""
    parts = [item for item in (details or ()) if item]
    log_to_db(
        _actor(),
        f"{MODULE_TITLE} – {action_title}",
        "; ".join(parts),
        entity_type=ENTITY_TYPE,
    )


def log_file_upload(
    page_title: str,
    filename: str,
    *,
    size_bytes: Optional[int] = None,
    details: Optional[Iterable[str]] = None,
) -> None:
    parts = [f"файл={filename}"]
    if size_bytes:
        parts.append(f"размер={_format_size(size_bytes)}")
    parts.extend(item for item in (details or ()) if item)
    log_to_db(
        _actor(),
        f"Загружен файл: {MODULE_TITLE} – {page_title}",
        "; ".join(parts),
        entity_type=ENTITY_TYPE,
    )


def log_file_download(
    page_title: str,
    filename: str,
    *,
    details: Optional[Iterable[str]] = None,
) -> None:
    parts = [f"файл={filename}"]
    parts.extend(item for item in (details or ()) if item)
    log_to_db(
        _actor(),
        f"Скачан файл: {MODULE_TITLE} – {page_title}",
        "; ".join(parts),
        entity_type=ENTITY_TYPE,
    )


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{int(size_bytes)} Б"
    return f"{round(int(size_bytes) / 1024)} КБ"


def _actor() -> Any:
    """Пользователь для журнала: логин из сессии, иначе текущий пользователь."""
    try:
        username = session.get("username")
    except Exception:
        username = None
    if username:
        return username
    try:
        return current_user if getattr(current_user, "is_authenticated", False) else None
    except Exception:
        return None
