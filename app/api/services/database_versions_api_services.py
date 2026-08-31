# -*- coding: utf-8 -*-
"""Независимый API сведений о версиях БД АРМ (без datasets)."""
from __future__ import annotations

from typing import Any

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db


class UnknownDatabaseVersionError(LookupError):
    """Версия БД с таким id не найдена."""


def _version_row(row: DatabaseVersion) -> dict[str, Any]:
    from app.api.services.general_info_exchange_services import (
        planning_meta_for_version,
    )

    payload = {
        "database_version": int(row.id),
        "version_number": row.version_number,
        "description": row.description or "",
    }
    payload.update(
        planning_meta_for_version(int(row.id), row.version_number)
    )
    return payload


def list_database_versions() -> dict[str, Any]:
    """Список версий БД для выбора среза на стороне клиента."""
    rows = (
        db.session.query(DatabaseVersion)
        .order_by(DatabaseVersion.is_active.desc(), DatabaseVersion.id.desc())
        .all()
    )
    return {"rows": [_version_row(row) for row in rows]}


def get_database_version(version_id: int) -> dict[str, Any]:
    """Одна версия БД по id."""
    row = db.session.get(DatabaseVersion, int(version_id))
    if row is None:
        raise UnknownDatabaseVersionError(version_id)
    return _version_row(row)


def ensure_database_version_exists(version_id: int) -> int:
    """Проверка, что id версии есть в справочнике; иначе LookupError."""
    vid = int(version_id)
    exists = (
        db.session.query(DatabaseVersion.id)
        .filter(DatabaseVersion.id == vid)
        .first()
    )
    if exists is None:
        raise UnknownDatabaseVersionError(vid)
    return vid
