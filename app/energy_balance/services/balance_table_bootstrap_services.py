# -*- coding: utf-8 -*-
"""Общая инициализация таблиц и фильтрация по версии БД для EE/PB twin-модулей."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.extensions import db

_tables_ready: set[str] = set()


def version_id() -> int | None:
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


def version_filtered_query(model):
    return filter_by_db_version(model.query, model)


def ensure_table(model) -> None:
    key = model.__tablename__
    if key in _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        model.__table__.create(bind, checkfirst=True)
        _tables_ready.add(key)
    except Exception:
        pass


def ensure_custom_flow_tables(row_model, value_model) -> None:
    key = row_model.__tablename__
    if key in _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        row_model.__table__.create(bind, checkfirst=True)
        value_model.__table__.create(bind, checkfirst=True)
        _ensure_parent_key_column(row_model, bind)
        _tables_ready.add(key)
    except Exception:
        pass


def _ensure_parent_key_column(row_model, bind) -> None:
    try:
        inspector = inspect(bind)
        schema = row_model.__table__.schema
        table = row_model.__tablename__
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
