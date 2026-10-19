# -*- coding: utf-8 -*-
"""Параметры анализа ПГ: копия и правка отчетных данных ГИС ТЭК."""
from __future__ import annotations

from typing import Any

from app.ecology.services.analysis_param_services import (
    seed_missing_params_from_reports,
    upsert_param_values,
    values_payload,
)
from app.ecology.services.gis_tes_fuel_comparison_constants import (
    PG_ANALYSIS_SHEET_SLUGS,
    PG_ECOLOGY_VALUE_FIELDS,
)

_LABEL = "ПГ"


def report_values_payload(report: Any) -> dict[str, Any]:
    return values_payload(report, PG_ECOLOGY_VALUE_FIELDS)


def param_values_payload(param: Any) -> dict[str, Any]:
    return values_payload(param, PG_ECOLOGY_VALUE_FIELDS)


def seed_missing_analysis_pg_params_from_reports(
    sheet_slug: str,
    *,
    station_numbs: set[int] | None = None,
    years: list[int] | None = None,
) -> int:
    """Создаёт отсутствующие строки параметров из отчетных ПГ (без перезаписи правок)."""
    from app.ecology.models.pg_param_calc_model import PGParamCalc
    from app.ecology.models.pg_report_gis_tek_model import PGReportGisTek

    return seed_missing_params_from_reports(
        PGParamCalc,
        PGReportGisTek,
        sheet_slug=sheet_slug,
        sheet_slugs=PG_ANALYSIS_SHEET_SLUGS,
        fields=PG_ECOLOGY_VALUE_FIELDS,
        label=_LABEL,
        station_numbs=station_numbs,
        years=years,
    )


def upsert_analysis_pg_param_values(
    sheet_slug: str,
    station_numb: int,
    year_number: int,
    values: dict[str, Any],
) -> Any:
    """Создаёт или обновляет параметры страницы анализа ПГ."""
    from app.ecology.models.pg_param_calc_model import PGParamCalc
    from app.ecology.models.pg_report_gis_tek_model import PGReportGisTek

    return upsert_param_values(
        PGParamCalc,
        PGReportGisTek,
        sheet_slug=sheet_slug,
        sheet_slugs=PG_ANALYSIS_SHEET_SLUGS,
        fields=PG_ECOLOGY_VALUE_FIELDS,
        label=_LABEL,
        station_numb=station_numb,
        year_number=year_number,
        values=values,
    )
