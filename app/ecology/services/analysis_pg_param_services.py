# -*- coding: utf-8 -*-
"""Параметры анализа ПГ: копия и правка отчетных данных ГИС ТЭК."""
from __future__ import annotations

from typing import Any

from app.ecology.services.ecology_decimal_helpers import decimal_from_loose_text as _as_decimal
from app.ecology.services.gis_tes_fuel_comparison_constants import (
    PG_ANALYSIS_SHEET_SLUGS,
    PG_ECOLOGY_VALUE_FIELDS,
)


def report_values_payload(report: Any) -> dict[str, Any]:
    return {field: getattr(report, field, None) for field in PG_ECOLOGY_VALUE_FIELDS}


def param_values_payload(param: Any) -> dict[str, Any]:
    return {field: getattr(param, field, None) for field in PG_ECOLOGY_VALUE_FIELDS}


def seed_missing_analysis_pg_params_from_reports(
    sheet_slug: str,
    *,
    station_numbs: set[int] | None = None,
    years: list[int] | None = None,
) -> int:
    """Создаёт отсутствующие строки параметров из отчетных ПГ (без перезаписи правок)."""
    slug = str(sheet_slug or "").strip()
    if slug not in PG_ANALYSIS_SHEET_SLUGS:
        return 0
    try:
        from flask import has_app_context

        from app.common.services.database_version_filter import get_current_db_version_id
        from app.ecology.models.pg_param_calc_model import PGParamCalc
        from app.ecology.models.pg_report_gis_tek_model import PGReportGisTek
        from app.extensions import db

        if not has_app_context():
            return 0
        version_id = get_current_db_version_id()
        report_q = PGReportGisTek.query
        param_q = PGParamCalc.query.filter_by(sheet_slug=slug)
        if version_id is not None:
            report_q = report_q.filter(
                PGReportGisTek.database_version_id == version_id
            )
            param_q = param_q.filter(PGParamCalc.database_version_id == version_id)
        if station_numbs:
            numb_list = list(station_numbs)
            report_q = report_q.filter(
                PGReportGisTek.station_numb.in_(numb_list)
            )
            param_q = param_q.filter(PGParamCalc.station_numb.in_(numb_list))
        if years:
            report_q = report_q.filter(PGReportGisTek.year_number.in_(years))
            param_q = param_q.filter(PGParamCalc.year_number.in_(years))

        existing = {
            (row.station_numb, row.year_number)
            for row in param_q.with_entities(
                PGParamCalc.station_numb, PGParamCalc.year_number
            ).all()
        }
        created = 0
        for report in report_q.all():
            key = (report.station_numb, report.year_number)
            if key in existing:
                continue
            payload = report_values_payload(report)
            db.session.add(
                PGParamCalc(
                    sheet_slug=slug,
                    station_numb=report.station_numb,
                    year_number=report.year_number,
                    database_version_id=version_id,
                    **payload,
                )
            )
            existing.add(key)
            created += 1
        if created:
            db.session.commit()
        return created
    except Exception:
        try:
            from app.extensions import db

            db.session.rollback()
        except Exception:
            pass
        return 0


def upsert_analysis_pg_param_values(
    sheet_slug: str,
    station_numb: int,
    year_number: int,
    values: dict[str, Any],
) -> Any:
    """Создаёт или обновляет параметры страницы анализа ПГ."""
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.ecology.models.pg_param_calc_model import PGParamCalc
    from app.ecology.models.pg_report_gis_tek_model import PGReportGisTek
    from app.extensions import db

    slug = str(sheet_slug or "").strip()
    if slug not in PG_ANALYSIS_SHEET_SLUGS:
        raise ValueError(f"Неизвестный sheet_slug для параметров ПГ: {sheet_slug!r}")
    version_id = get_current_db_version_id()
    query = PGParamCalc.query.filter_by(
        sheet_slug=slug,
        station_numb=int(station_numb),
        year_number=int(year_number),
    )
    if version_id is not None:
        query = query.filter(PGParamCalc.database_version_id == version_id)
    row = query.first()
    if row is None:
        report_q = PGReportGisTek.query.filter_by(
            station_numb=int(station_numb),
            year_number=int(year_number),
        )
        if version_id is not None:
            report_q = report_q.filter(
                PGReportGisTek.database_version_id == version_id
            )
        report = report_q.first()
        payload = report_values_payload(report) if report is not None else {}
        row = PGParamCalc(
            sheet_slug=slug,
            station_numb=int(station_numb),
            year_number=int(year_number),
            database_version_id=version_id,
            **payload,
        )
        db.session.add(row)
    for field, raw in values.items():
        if field not in PG_ECOLOGY_VALUE_FIELDS:
            continue
        setattr(row, field, _as_decimal(raw))
    db.session.commit()
    return row
