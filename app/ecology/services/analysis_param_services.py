# -*- coding: utf-8 -*-
"""Общие операции параметров анализа (ПГ и ЗВ): seed из отчетов и правка ячеек."""
from __future__ import annotations

import logging
from typing import Any

from app.ecology.services.ecology_decimal_helpers import (
    decimal_from_loose_text as _as_decimal,
)
from app.ecology.services.ecology_logging_services import (
    analysis_field_label,
    change_lines,
    comparison_sheet_title,
    context_lines,
    log_changes,
)

_logger = logging.getLogger(__name__)


def values_payload(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Значения полей строки отчета/параметров (None для отсутствующей строки)."""
    return {field: getattr(row, field, None) for field in fields}


def seed_missing_params_from_reports(
    params_model: Any,
    reports_model: Any,
    *,
    sheet_slug: str,
    sheet_slugs: frozenset[str],
    fields: tuple[str, ...],
    label: str,
    station_numbs: set[int] | None = None,
    years: list[int] | None = None,
) -> int:
    """Создаёт отсутствующие строки параметров из отчетных данных (без перезаписи правок)."""
    slug = str(sheet_slug or "").strip()
    if slug not in sheet_slugs:
        return 0
    try:
        from flask import has_app_context

        from app.common.services.database_version_filter import get_current_db_version_id
        from app.extensions import db

        if not has_app_context():
            return 0
        version_id = get_current_db_version_id()
        report_q = reports_model.query
        param_q = params_model.query.filter_by(sheet_slug=slug)
        if version_id is not None:
            report_q = report_q.filter(reports_model.database_version_id == version_id)
            param_q = param_q.filter(params_model.database_version_id == version_id)
        if station_numbs:
            numb_list = list(station_numbs)
            report_q = report_q.filter(reports_model.station_numb.in_(numb_list))
            param_q = param_q.filter(params_model.station_numb.in_(numb_list))
        if years:
            report_q = report_q.filter(reports_model.year_number.in_(years))
            param_q = param_q.filter(params_model.year_number.in_(years))

        existing = {
            (row.station_numb, row.year_number)
            for row in param_q.with_entities(
                params_model.station_numb, params_model.year_number
            ).all()
        }
        created = 0
        for report in report_q.all():
            key = (report.station_numb, report.year_number)
            if key in existing:
                continue
            db.session.add(
                params_model(
                    sheet_slug=slug,
                    station_numb=report.station_numb,
                    year_number=report.year_number,
                    database_version_id=version_id,
                    **values_payload(report, fields),
                )
            )
            existing.add(key)
            created += 1
        if created:
            db.session.commit()
        return created
    except Exception:
        _logger.exception("ecology analysis %s seed failed (sheet=%s)", label, sheet_slug)
        try:
            from app.extensions import db

            db.session.rollback()
        except Exception:
            pass
        return 0


def upsert_param_values(
    params_model: Any,
    reports_model: Any,
    *,
    sheet_slug: str,
    sheet_slugs: frozenset[str],
    fields: tuple[str, ...],
    label: str,
    station_numb: int,
    year_number: int,
    values: dict[str, Any],
) -> Any:
    """Создаёт или обновляет параметры страницы анализа."""
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.extensions import db

    slug = str(sheet_slug or "").strip()
    if slug not in sheet_slugs:
        raise ValueError(f"Неизвестный sheet_slug для параметров {label}: {sheet_slug!r}")
    version_id = get_current_db_version_id()
    query = params_model.query.filter_by(
        sheet_slug=slug,
        station_numb=int(station_numb),
        year_number=int(year_number),
    )
    if version_id is not None:
        query = query.filter(params_model.database_version_id == version_id)
    row = query.first()
    if row is None:
        report_q = reports_model.query.filter_by(
            station_numb=int(station_numb),
            year_number=int(year_number),
        )
        if version_id is not None:
            report_q = report_q.filter(reports_model.database_version_id == version_id)
        row = params_model(
            sheet_slug=slug,
            station_numb=int(station_numb),
            year_number=int(year_number),
            database_version_id=version_id,
            **values_payload(report_q.first(), fields),
        )
        db.session.add(row)
    edited: list[tuple[str, Any, Any]] = []
    for field, raw in values.items():
        if field not in fields:
            continue
        previous_value = getattr(row, field, None)
        new_value = _as_decimal(raw)
        setattr(row, field, new_value)
        edited.append((analysis_field_label(field), previous_value, new_value))
    db.session.commit()
    log_changes(
        f"Анализ {label}, {comparison_sheet_title(slug)}",
        change_lines(edited),
        context=context_lines(
            ("год", int(year_number)),
            ("группа оборудования (numb1120)", int(station_numb)),
        ),
    )
    return row
