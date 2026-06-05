# -*- coding: utf-8 -*-
"""Версии БД для импорта долгосрочного потребления из Excel."""

from __future__ import annotations

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import get_current_version


def all_database_version_ids_for_import() -> list[int]:
    """Все зарегистрированные версии БД (порядок — по номеру версии)."""
    rows = DatabaseVersion.query.order_by(DatabaseVersion.version_number.asc()).all()
    out = [int(v.id) for v in rows if v.id is not None]
    if out:
        return out
    cv = get_current_version()
    if cv is not None:
        return [int(cv)]
    return []
