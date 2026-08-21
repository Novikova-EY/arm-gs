# -*- coding: utf-8 -*-
"""CRUD пользовательских строк «Получение/Передача электрической энергии»."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, inspect, text
from sqlalchemy.exc import ProgrammingError, OperationalError

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.ee_balance_custom_flow_model import (
    CUSTOM_FLOW_DIRECTIONS,
    EeBalanceCustomFlowRow,
    EeBalanceCustomFlowValue,
)
from app.extensions import db

__all__ = [
    "CUSTOM_FLOW_DIRECTIONS",
    "add_custom_flow_row",
    "custom_flow_row_key",
    "delete_custom_flow_row",
    "load_ee_balance_custom_flows",
    "parse_custom_flow_row_id",
    "update_custom_flow_label",
    "update_custom_flow_value",
]

_tables_ready = False


def custom_flow_row_key(direction: str, row_id: int) -> str:
    return f"{direction}_custom_{int(row_id)}"


def parse_custom_flow_row_id(row_key: str) -> int | None:
    text_value = str(row_key or "")
    for direction in CUSTOM_FLOW_DIRECTIONS:
        prefix = f"{direction}_custom_"
        if text_value.startswith(prefix):
            try:
                return int(text_value[len(prefix) :])
            except (TypeError, ValueError):
                return None
    return None


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        EeBalanceCustomFlowRow.__table__.create(bind, checkfirst=True)
        EeBalanceCustomFlowValue.__table__.create(bind, checkfirst=True)
        _ensure_parent_key_column(bind)
        _tables_ready = True
    except Exception:
        pass


def _ensure_parent_key_column(bind) -> None:
    try:
        inspector = inspect(bind)
        schema = EeBalanceCustomFlowRow.__table__.schema
        table = EeBalanceCustomFlowRow.__tablename__
        columns = {col["name"] for col in inspector.get_columns(table, schema=schema)}
        if "parent_key" in columns:
            return
        db.session.execute(
            text(f'ALTER TABLE "{schema}"."{table}" ADD COLUMN parent_key VARCHAR(128)')
        )
        db.session.execute(
            text(
                f'UPDATE "{schema}"."{table}" '
                "SET parent_key = direction "
                "WHERE parent_key IS NULL OR parent_key = ''"
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


def _version_id() -> int | None:
    try:
        raw = get_current_db_version_id()
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _row_query():
    return filter_by_db_version(EeBalanceCustomFlowRow.query, EeBalanceCustomFlowRow)


def _serialize_row(row: EeBalanceCustomFlowRow) -> dict[str, Any]:
    values: dict[int, Any] = {}
    for item in row.values or []:
        if item.year_number is None or item.value_mln_kvtch is None:
            continue
        try:
            year = int(item.year_number)
        except (TypeError, ValueError):
            continue
        values[year] = item.value_mln_kvtch
    return {
        "id": int(row.id),
        "direction": str(row.direction),
        "parent_key": str(getattr(row, "parent_key", None) or row.direction or ""),
        "label": str(row.label or ""),
        "sort_order": int(row.sort_order or 0),
        "values": values,
        "key": custom_flow_row_key(str(row.direction), int(row.id)),
    }


def load_ee_balance_custom_flows(sheets=None) -> dict[str, list[dict[str, Any]]]:
    """{sheet_slug: [{id, direction, label, sort_order, values, key}, ...]}."""
    _ensure_tables()
    _ensure_vostok_layout_defaults(sheets)
    try:
        rows = (
            _row_query()
            .order_by(
                EeBalanceCustomFlowRow.sheet_slug,
                EeBalanceCustomFlowRow.direction,
                EeBalanceCustomFlowRow.sort_order,
                EeBalanceCustomFlowRow.id,
            )
            .all()
        )
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return {}
    except Exception:
        return {}

    from app.energy_balance.services.power_balance_page_services import (
        VOSTOK_LAYOUT_SEED_PARENT,
    )

    allowed = None
    if sheets is not None:
        allowed = {str(sheet.get("slug") or "") for sheet in sheets}

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        slug = str(row.sheet_slug or "")
        if allowed is not None and slug not in allowed:
            continue
        if row.direction not in CUSTOM_FLOW_DIRECTIONS:
            continue
        if str(getattr(row, "parent_key", None) or "") == VOSTOK_LAYOUT_SEED_PARENT:
            continue
        grouped.setdefault(slug, []).append(_serialize_row(row))
    return grouped


def _ensure_vostok_layout_defaults(sheets) -> None:
    if not sheets:
        return
    from app.energy_balance.services.power_balance_page_services import (
        VOSTOK_DEFAULT_CUSTOM_FLOWS,
        VOSTOK_LAYOUT_SEED_PARENT,
        resolve_custom_flow_parent_key,
    )

    slugs = [
        str(sheet.get("slug") or "").strip()
        for sheet in sheets
        if sheet.get("layout") == "oes_vostok" and str(sheet.get("slug") or "").strip()
    ]
    if not slugs:
        return
    changed = False
    try:
        version_id = _version_id()
        for slug in slugs:
            existing = (
                _row_query()
                .filter(EeBalanceCustomFlowRow.sheet_slug == slug)
                .all()
            )
            seeded = False
            labels: set[tuple[str, str]] = set()
            for row in existing:
                parent = str(row.parent_key or row.direction or "")
                if parent == VOSTOK_LAYOUT_SEED_PARENT:
                    seeded = True
                resolved = resolve_custom_flow_parent_key(parent, str(row.direction or ""))
                if resolved != parent:
                    row.parent_key = resolved
                    changed = True
                    parent = resolved
                if parent in CUSTOM_FLOW_DIRECTIONS:
                    labels.add((str(row.direction), str(row.label or "")))
            if seeded:
                continue
            for direction, label in VOSTOK_DEFAULT_CUSTOM_FLOWS:
                if (direction, label) in labels:
                    continue
                db.session.add(
                    EeBalanceCustomFlowRow(
                        sheet_slug=slug,
                        direction=direction,
                        parent_key=direction,
                        label=label,
                        sort_order=len(labels),
                        database_version_id=version_id,
                    )
                )
                labels.add((direction, label))
                changed = True
            db.session.add(
                EeBalanceCustomFlowRow(
                    sheet_slug=slug,
                    direction="flow_in",
                    parent_key=VOSTOK_LAYOUT_SEED_PARENT,
                    label="",
                    sort_order=-1,
                    database_version_id=version_id,
                )
            )
            changed = True
        if changed:
            _commit_with_retry()
    except Exception:
        db.session.rollback()


def _get_row(slug: str, row_id: int) -> EeBalanceCustomFlowRow | None:
    _ensure_tables()
    try:
        return (
            _row_query()
            .filter(
                EeBalanceCustomFlowRow.id == int(row_id),
                EeBalanceCustomFlowRow.sheet_slug == str(slug),
            )
            .one_or_none()
        )
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return None


def add_custom_flow_row(
    slug: str,
    direction: str,
    label: str = "",
    parent_key: str | None = None,
) -> dict[str, Any]:
    from app.energy_balance.services.power_balance_page_services import (
        resolve_custom_flow_parent_key,
    )

    direction = str(direction or "").strip()
    parent_key = resolve_custom_flow_parent_key(parent_key, direction)
    if direction not in CUSTOM_FLOW_DIRECTIONS:
        if parent_key.startswith("flow_out"):
            direction = "flow_out"
        elif parent_key.startswith("flow_in"):
            direction = "flow_in"
        else:
            raise ValueError("Неверное направление строки")
    if direction not in CUSTOM_FLOW_DIRECTIONS:
        raise ValueError("Неверное направление строки")
    slug = str(slug or "").strip()
    if not slug:
        raise ValueError("Не указан лист баланса")
    parent_id = parse_custom_flow_row_id(parent_key)
    if parent_id is not None:
        parent_row = _get_row(slug, parent_id)
        if parent_row is None:
            raise ValueError("Родительская строка не найдена")
        parent_of_parent = str(parent_row.parent_key or parent_row.direction or "")
        if parent_of_parent not in CUSTOM_FLOW_DIRECTIONS:
            raise ValueError("Можно добавить только два уровня строк")
        direction = str(parent_row.direction)
        parent_key = custom_flow_row_key(direction, int(parent_row.id))
    _ensure_tables()
    version_id = _version_id()
    max_order = db.session.query(
        func.coalesce(func.max(EeBalanceCustomFlowRow.sort_order), -1)
    ).filter(
        EeBalanceCustomFlowRow.sheet_slug == slug,
        EeBalanceCustomFlowRow.direction == direction,
        func.coalesce(EeBalanceCustomFlowRow.parent_key, EeBalanceCustomFlowRow.direction)
        == parent_key,
    )
    max_order = filter_by_db_version(max_order, EeBalanceCustomFlowRow).scalar()
    next_order = int(max_order) + 1 if max_order is not None else 0
    row = EeBalanceCustomFlowRow(
        sheet_slug=slug,
        direction=direction,
        parent_key=parent_key,
        label=str(label or "").strip(),
        sort_order=next_order,
        database_version_id=version_id,
    )
    db.session.add(row)
    _commit_with_retry()
    db.session.refresh(row)
    return _serialize_row(row)


def _descendant_rows(slug: str, parent_key: str) -> list[EeBalanceCustomFlowRow]:
    try:
        rows = (
            _row_query()
            .filter(EeBalanceCustomFlowRow.sheet_slug == str(slug))
            .all()
        )
    except Exception:
        return []
    by_parent: dict[str, list[EeBalanceCustomFlowRow]] = {}
    for item in rows:
        key = str(item.parent_key or item.direction or "")
        by_parent.setdefault(key, []).append(item)
    collected: list[EeBalanceCustomFlowRow] = []
    stack = list(by_parent.get(parent_key, []))
    while stack:
        current = stack.pop()
        collected.append(current)
        child_key = custom_flow_row_key(str(current.direction), int(current.id))
        stack.extend(by_parent.get(child_key, []))
    return collected


def delete_custom_flow_row(slug: str, row_id: int) -> bool:
    row = _get_row(slug, row_id)
    if row is None:
        return False
    key = custom_flow_row_key(str(row.direction), int(row.id))
    for child in _descendant_rows(slug, key):
        db.session.delete(child)
    db.session.delete(row)
    _commit_with_retry()
    return True


def update_custom_flow_label(slug: str, row_id: int, label: str) -> dict[str, Any] | None:
    row = _get_row(slug, row_id)
    if row is None:
        return None
    row.label = str(label or "").strip()
    _commit_with_retry()
    return _serialize_row(row)


def update_custom_flow_value(
    slug: str,
    row_id: int,
    year: int,
    raw_value: Any,
) -> dict[str, Any]:
    row = _get_row(slug, row_id)
    if row is None:
        raise KeyError("Строка не найдена")
    try:
        year_int = int(year)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверный год") from exc
    try:
        parsed = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверное число") from exc

    version_id = _version_id()
    existing = next(
        (
            item
            for item in (row.values or [])
            if int(item.year_number) == year_int
            and (
                (item.database_version_id is None and version_id is None)
                or (
                    item.database_version_id is not None
                    and version_id is not None
                    and int(item.database_version_id) == int(version_id)
                )
            )
        ),
        None,
    )
    if parsed is None:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
        return {"year": year_int, "value": None}
    if existing is None:
        existing = EeBalanceCustomFlowValue(
            id_row=row.id,
            year_number=year_int,
            value_mln_kvtch=parsed,
            database_version_id=version_id,
        )
        db.session.add(existing)
    else:
        existing.value_mln_kvtch = parsed
    _commit_with_retry()
    return {"year": year_int, "value": parsed}
