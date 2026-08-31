# -*- coding: utf-8 -*-
"""JSON-набор general_info: текущий год и период планирования версии.

Источник — блок «Периоды планирования» на /refdata/:
- «Текущий год» — YearFeature «текущий (оценка)»;
- «Начало периода» — year_sipr_start (как начало строки СиПР / ГС на странице);
- «Конец периода» — для версии СиПР: year_sipr_end; для ГС: конец Генеральной схемы (2042).

Не путать с границами фильтров страниц (там start = sipr_start − 2).
"""
from __future__ import annotations

from typing import Any

from config import Config
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.get_services.years.years_get_services import (
    _planning_scheme_from_version_number,
)
from app.extensions import db
from app.api.services.generation_objects_exchange_services import (
    dataset_envelope,
    resolve_database_version,
)
from app.refdata.services.year_management_services import get_current_year_info

DATASET_GENERAL_INFO = "general_info"

KEY_CURRENT_YEAR = "Текущий год"
KEY_PERIOD_START = "Начало периода"
KEY_PERIOD_END = "Конец периода"


def build_general_info_row(version_id: int | None) -> dict[str, int]:
    info = get_current_year_info(version_id) if version_id is not None else {}
    current = int(info.get("current_year") or 0)
    start = int(info.get("sipr_start") or 0)
    end = int(info.get("sipr_end") or 0)

    version_number = None
    if version_id is not None:
        row = db.session.get(DatabaseVersion, int(version_id))
        version_number = getattr(row, "version_number", None) if row is not None else None
    scheme = _planning_scheme_from_version_number(version_number)
    if scheme == "gs":
        end = int(getattr(Config, "END_YEAR_GENERAL_SCHEME", 2042))

    return {
        KEY_CURRENT_YEAR: current,
        KEY_PERIOD_START: start,
        KEY_PERIOD_END: end,
    }


def load_general_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    del year, start_year, end_year  # набор не зависит от фильтра лет
    resolved_id, version_number = resolve_database_version(version_id)
    rows = [build_general_info_row(resolved_id)] if resolved_id is not None else []
    return dataset_envelope(
        DATASET_GENERAL_INFO,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
    )


def planning_meta_for_version(
    version_id: int,
    version_number: str | None,
) -> dict[str, Any]:
    """Метаданные периода для списка /api/database_versions."""
    scheme = _planning_scheme_from_version_number(version_number)
    row = build_general_info_row(version_id)
    return {
        "planning_scheme": scheme,  # "sipr" | "gs" | None
        "current_year": row[KEY_CURRENT_YEAR],
        "period_start": row[KEY_PERIOD_START],
        "period_end": row[KEY_PERIOD_END],
    }
