# -*- coding: utf-8 -*-
"""Общая инфраструктура JSON-наборов обмена (envelope, версия, годы, заглушки)."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.refdata.models.years.year_model import Year

EXCHANGE_YEARS_BEFORE_CURRENT = 6

# Общий comment для stub-наборов без данных в АРМ (ручное заполнение).
MANUAL_FILL_EXCHANGE_COMMENT = (
    "Данных параметров нет в АРМ, поэтому они заполняются вручную."
)


def clip_years(
    years: Iterable[int],
    *,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[int]:
    selected = sorted({int(y) for y in years})
    if year is not None:
        return [int(year)]
    if start_year is not None:
        selected = [y for y in selected if y >= int(start_year)]
    if end_year is not None:
        selected = [y for y in selected if y <= int(end_year)]
    return selected


def dataset_envelope(
    dataset: str,
    *,
    database_version: int | None,
    rows: list[dict[str, Any]],
    comment: str = "",
    version_number: str | None = None,
) -> dict[str, Any]:
    """Оболочка набора: срез всегда привязан к версии БД АРМ.

    ``database_version`` — PK ``gs_sys.gs_database_versions.id`` (числовой id версии).
    ``version_number`` — человекочитаемый номер (например «ГС 2023-2042 (утвержденная)»).
    ``version`` — то же значение, что ``database_version``; это не ISO-дата.
    """
    label = version_number
    if label is None and database_version is not None:
        row = db.session.get(DatabaseVersion, int(database_version))
        label = row.version_number if row is not None else None
    return {
        "dataset": dataset,
        "database_version": database_version,
        "version_number": label or "",
        "version": database_version,
        "comment": comment,
        "rows": rows,
    }


def version_filter(model, version_id: int | None):
    if version_id is None:
        return model.database_version_id.is_(None)
    return model.database_version_id == int(version_id)


# Совместимость с прежним приватным именем.
_version_filter = version_filter


def resolve_database_version(version_id: int | None) -> tuple[int | None, str | None]:
    vid = int(version_id) if version_id is not None else get_current_db_version_id()
    if vid is None:
        return None, None
    row = db.session.get(DatabaseVersion, vid)
    if row is None:
        return None, None
    return row.id, row.version_number


def exchange_years_bounds(version_id: int) -> tuple[int, int] | None:
    """Границы выгрузки: current_year − 6 … period_end из /api/database_versions."""
    from app.api.services.general_info_exchange_services import planning_meta_for_version

    row = db.session.get(DatabaseVersion, int(version_id))
    if row is None:
        return None
    meta = planning_meta_for_version(int(row.id), row.version_number)
    try:
        current = int(meta.get("current_year") or 0)
    except (TypeError, ValueError):
        current = 0
    try:
        period_end = int(meta.get("period_end") or 0)
    except (TypeError, ValueError):
        period_end = 0
    if current <= 0:
        return None
    start = current - EXCHANGE_YEARS_BEFORE_CURRENT
    end = period_end if period_end > 0 else current
    if end < start:
        return None
    return start, end


def load_exchange_years(version_id: int | None) -> list[int]:
    """Годы набора: от current_year − 6 до period_end, только годы справочника версии."""
    if version_id is None:
        return []
    bounds = exchange_years_bounds(int(version_id))
    if bounds is None:
        return []
    start, end = bounds
    consecutive = list(range(start, end + 1))
    catalog = {
        int(n)
        for (n,) in db.session.query(Year.number)
        .filter(version_filter(Year, version_id))
        .all()
        if n is not None
    }
    if not catalog:
        return consecutive
    return [year for year in consecutive if year in catalog]


def load_stub_exchange_dataset(
    dataset: str,
    *,
    comment: str,
    row_factory: Callable[[], dict[str, Any]],
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    """Заглушка набора: одна нулевая строка; фильтр лет в сигнатуре игнорируется."""
    del year, start_year, end_year
    resolved_id, version_number = resolve_database_version(version_id)
    return dataset_envelope(
        dataset,
        database_version=resolved_id,
        version_number=version_number,
        comment=comment,
        rows=[row_factory()],
    )
