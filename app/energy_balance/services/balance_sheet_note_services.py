# -*- coding: utf-8 -*-
"""CRUD столбца «Примечание» на листах баланса мощности и электрической энергии."""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.exc import ProgrammingError, OperationalError

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.balance_sheet_note_model import (
    BALANCE_KIND_EE,
    BALANCE_KIND_POWER,
    NOTE_MAX_LENGTH,
    ROW_KEY_MAX_LENGTH,
    BalanceSheetNote,
)
from app.extensions import db

__all__ = [
    "BALANCE_KIND_EE",
    "BALANCE_KIND_POWER",
    "NOTE_MAX_LENGTH",
    "ROW_KEY_MAX_LENGTH",
    "attach_balance_sheet_notes",
    "load_balance_sheet_notes",
    "update_balance_sheet_note",
]

_tables_ready = False


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        BalanceSheetNote.__table__.create(bind, checkfirst=True)
        _tables_ready = True
    except Exception:
        pass


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


def _note_query():
    return filter_by_db_version(BalanceSheetNote.query, BalanceSheetNote)


def _normalize_kind(kind: str) -> str:
    text = str(kind or "").strip()
    if text not in {BALANCE_KIND_POWER, BALANCE_KIND_EE}:
        raise ValueError("Неверный тип баланса")
    return text


def _normalize_row_key(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Не указана строка")
    if len(text) > ROW_KEY_MAX_LENGTH:
        text = text[:ROW_KEY_MAX_LENGTH]
    return text


def _normalize_note(raw: Any) -> str:
    text = "" if raw is None else str(raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > NOTE_MAX_LENGTH:
        text = text[:NOTE_MAX_LENGTH]
    return text


def load_balance_sheet_notes(
    kind: str,
    slugs: Iterable[str] | None = None,
) -> dict[str, dict[str, str]]:
    """{sheet_slug: {row_key: note_text}} для листов указанного вида баланса."""
    kind_norm = _normalize_kind(kind)
    _ensure_tables()
    try:
        query = _note_query().filter(BalanceSheetNote.balance_kind == kind_norm)
        rows = query.all()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return {}
    except Exception:
        return {}

    allowed = None
    if slugs is not None:
        allowed = {str(slug or "") for slug in slugs}

    notes: dict[str, dict[str, str]] = {}
    for row in rows:
        slug = str(row.sheet_slug or "")
        row_key = str(row.row_key or "")
        if not slug or not row_key:
            continue
        if allowed is not None and slug not in allowed:
            continue
        notes.setdefault(slug, {})[row_key] = str(row.note_text or "")
    return notes


def _note_for_row(
    row: dict[str, Any],
    notes_by_slug: dict[str, dict[str, str]],
    current_slug: str,
) -> str:
    origin_slug = str(row.get("custom_origin_slug") or "").strip()
    origin_key = str(row.get("custom_origin_key") or "").strip()
    if origin_slug and origin_key:
        return (notes_by_slug.get(origin_slug) or {}).get(origin_key) or ""
    key = str(row.get("key") or "")
    if not key:
        return ""
    return (notes_by_slug.get(current_slug) or {}).get(key) or ""


def attach_balance_sheet_notes(
    tables: dict[str, dict[str, Any]],
    kind: str,
) -> None:
    notes: dict[str, dict[str, str]] = {}
    try:
        notes = load_balance_sheet_notes(kind, tables.keys())
    except Exception:
        notes = {}
    for slug, payload in tables.items():
        for row in payload.get("rows") or []:
            row["note"] = _note_for_row(row, notes, slug)


def update_balance_sheet_note(
    kind: str,
    slug: str,
    row_key: Any,
    raw_note: Any,
) -> dict[str, Any]:
    kind_norm = _normalize_kind(kind)
    slug_norm = str(slug or "").strip()
    if not slug_norm:
        raise ValueError("Не указан лист баланса")
    key_norm = _normalize_row_key(row_key)
    note = _normalize_note(raw_note).strip()

    _ensure_tables()
    version_id = _version_id()
    existing = (
        _note_query()
        .filter(
            BalanceSheetNote.sheet_slug == slug_norm,
            BalanceSheetNote.balance_kind == kind_norm,
            BalanceSheetNote.row_key == key_norm,
        )
        .one_or_none()
    )
    if not note:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
        return {"note": "", "row_key": key_norm}
    if existing is None:
        existing = BalanceSheetNote(
            sheet_slug=slug_norm,
            balance_kind=kind_norm,
            row_key=key_norm,
            note_text=note,
            database_version_id=version_id,
        )
        db.session.add(existing)
    else:
        existing.note_text = note
    _commit_with_retry()
    return {"note": note, "row_key": key_norm}
