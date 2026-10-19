# -*- coding: utf-8 -*-
"""Параметры анализа ЗВ: копия и правка отчетных данных ГИС ТЭК."""
from __future__ import annotations

from typing import Any

from app.ecology.services.analysis_param_services import (
    seed_missing_params_from_reports,
    upsert_param_values,
    values_payload,
)
from app.ecology.services.gis_tes_fuel_comparison_constants import (
    ZV_ANALYSIS_SHEET_SLUGS,
    ZV_ECOLOGY_VALUE_FIELDS,
)

_LABEL = "ЗВ"


def report_values_payload(report: Any) -> dict[str, Any]:
    return values_payload(report, ZV_ECOLOGY_VALUE_FIELDS)


def seed_missing_analysis_zv_params_from_reports(
    sheet_slug: str,
    *,
    station_numbs: set[int] | None = None,
    years: list[int] | None = None,
) -> int:
    """Создаёт отсутствующие строки параметров из отчетных ЗВ (без перезаписи правок)."""
    from app.ecology.models.zv_param_calc_model import ZVParamCalc
    from app.ecology.models.zv_report_gis_tek_model import ZVReportGisTek

    return seed_missing_params_from_reports(
        ZVParamCalc,
        ZVReportGisTek,
        sheet_slug=sheet_slug,
        sheet_slugs=ZV_ANALYSIS_SHEET_SLUGS,
        fields=ZV_ECOLOGY_VALUE_FIELDS,
        label=_LABEL,
        station_numbs=station_numbs,
        years=years,
    )


def upsert_analysis_zv_param_values(
    sheet_slug: str,
    station_numb: int,
    year_number: int,
    values: dict[str, Any],
) -> Any:
    """Создаёт или обновляет параметры страницы анализа ЗВ."""
    from app.ecology.models.zv_param_calc_model import ZVParamCalc
    from app.ecology.models.zv_report_gis_tek_model import ZVReportGisTek

    return upsert_param_values(
        ZVParamCalc,
        ZVReportGisTek,
        sheet_slug=sheet_slug,
        sheet_slugs=ZV_ANALYSIS_SHEET_SLUGS,
        fields=ZV_ECOLOGY_VALUE_FIELDS,
        label=_LABEL,
        station_numb=station_numb,
        year_number=year_number,
        values=values,
    )
