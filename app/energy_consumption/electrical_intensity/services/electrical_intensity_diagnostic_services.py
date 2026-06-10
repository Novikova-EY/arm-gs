# -*- coding: utf-8 -*-
"""Диагностическая разметка строки «Характерные точки графика» (по данным электроёмкости)."""

from __future__ import annotations

import math
import statistics
from decimal import Decimal
from typing import Any

from app.common.services.help_services import format_decimal_trim_for_display
from app.energy_consumption.long_term_consumption.services.electrical_intensity_constants import (
    REF_ROW_ACCUM_FIXED_CAPITAL,
    REF_ROW_ACCUM_MONETARY_INCOME,
    REF_ROW_FD_ACCUM_FIXED_CAPITAL,
    ROW_KIND_GRAPH_POINT,
    ROW_KIND_INTENSITY,
)

MIN_INVESTMENT_SHARE = Decimal("0.15")
EXCLUDE_Z_THRESHOLD = 3.5
ABS_LOCAL_X_LIMIT = 2.5
MAD_SCALE = 1.4826

_DIAG_HEADER = (
    "Значение не рекомендуется использовать в расчете коэффициента Х."
)


def _format_num_ru(value: Decimal | float, *, digits: int = 2) -> str:
    if isinstance(value, Decimal):
        s = format_decimal_trim_for_display(value, digits=digits)
    else:
        s = format_decimal_trim_for_display(Decimal(str(value)), digits=digits)
    return (s or "0").replace(".", ",")


def _format_pct_ru(share: Decimal) -> str:
    pct = share * Decimal("100")
    return f"{_format_num_ru(pct, digits=1)}%"


def _investment_cells_from_section(section: dict[str, Any]) -> dict[int, Decimal | None]:
    for ref_row in section.get("reference_rows") or []:
        if ref_row.get("row_kind") in (
            REF_ROW_ACCUM_FIXED_CAPITAL,
            REF_ROW_FD_ACCUM_FIXED_CAPITAL,
            REF_ROW_ACCUM_MONETARY_INCOME,
        ):
            return dict(ref_row.get("cells") or {})
    return {}


def _reason_low_investment(
    *,
    year: int,
    investment_share: Decimal,
) -> str:
    return (
        f"Накопленные инвестиции составляют {_format_pct_ru(investment_share)} "
        f"от уровня последнего фактического года ({year}), "
        f"что ниже установленного порога {_format_pct_ru(MIN_INVESTMENT_SHARE)}.\n"
        "Такие значения относятся к начальному нестабильному участку ряда "
        "и могут искажать расчет степенной зависимости."
    )


def _reason_z_outlier(
    *,
    year_prev: int,
    year_curr: int,
    local_x: Decimal,
    median_x: float,
    z_x: float,
) -> str:
    return (
        f"Локальный коэффициент Х между {year_prev} и {year_curr} годами "
        "является статистическим выбросом.\n"
        f"Xлок = {_format_num_ru(local_x, digits=2)}\n"
        f"Медианное значение X по блоку = {_format_num_ru(median_x, digits=2)}\n"
        f"Робастное отклонение z = {_format_num_ru(z_x, digits=2)}\n"
        f"Порог исключения = {_format_num_ru(EXCLUDE_Z_THRESHOLD, digits=2)}\n"
        "Такое значение может существенно исказить средний коэффициент Х "
        "и форму расчетного графика."
    )


def _reason_extreme_local_x(*, local_x: Decimal) -> str:
    return (
        "Локальный коэффициент Х имеет экстремальное значение.\n"
        f"Xлок = {_format_num_ru(local_x, digits=2)}\n"
        f"Допустимый ориентировочный предел: |Xлок| <= {_format_num_ru(ABS_LOCAL_X_LIMIT, digits=1)}\n"
        "Такой скачок указывает на резкое нарушение зависимости между "
        "электроёмкостью и накопленными инвестициями."
    )


def _compose_diagnostic_comment(reasons: list[str]) -> str:
    if not reasons:
        return ""
    if len(reasons) == 1:
        return f"{_DIAG_HEADER}\n\nПричина:\n{reasons[0]}"
    numbered = "\n".join(f"{i}. {r}" for i, r in enumerate(reasons, start=1))
    return (
        f"{_DIAG_HEADER}\n\nПричины:\n{numbered}\n\n"
        "Рекомендация:\n"
        "исключить данное значение из расчета среднего коэффициента Х."
    )


def _local_x(
    y_cur: Decimal | None,
    y_prev: Decimal | None,
    inv_cur: Decimal | None,
    inv_prev: Decimal | None,
) -> Decimal | None:
    """LN(Yt/Yt-1) / LN(It/It-1) — локальный коэффициент X между соседними годами."""
    if (
        y_cur is None
        or y_prev is None
        or inv_cur is None
        or inv_prev is None
        or y_prev <= 0
        or inv_prev <= 0
        or y_cur <= 0
        or inv_cur <= 0
    ):
        return None
    try:
        num = math.log(float(y_cur / y_prev))
        den = math.log(float(inv_cur / inv_prev))
        if den == 0:
            return None
        return Decimal(str(num / den))
    except (ValueError, OverflowError, ZeroDivisionError):
        return None


def _find_ei_row(rows: list[dict[str, Any]], row_kind: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("row_kind") == row_kind:
            return row
    return None


def compute_intensity_cell_diagnostics(
    *,
    display_years: list[int],
    intensity_cells: dict[int, Decimal | None],
    investment_cells: dict[int, Decimal | None],
    current_year: int | None,
) -> dict[int, str]:
    """
    Подозрительные годы для строки «Характерные точки графика» → текст подсказки.
    Расчёт по электроёмкости и инвестициям; значения в ячейках не изменяются.
    """
    if not display_years or current_year is None:
        return {}

    inv_last = investment_cells.get(current_year)
    if inv_last is None or inv_last <= 0:
        inv_last = None

    sorted_years = sorted(display_years)
    local_x_by_year: dict[int, Decimal] = {}
    local_x_meta: dict[int, tuple[int, Decimal]] = {}

    for idx in range(1, len(sorted_years)):
        year_prev = sorted_years[idx - 1]
        year_curr = sorted_years[idx]
        y_prev = intensity_cells.get(year_prev)
        y_cur = intensity_cells.get(year_curr)
        inv_prev = investment_cells.get(year_prev)
        inv_cur = investment_cells.get(year_curr)
        lx = _local_x(y_cur, y_prev, inv_cur, inv_prev)
        if lx is None:
            continue
        local_x_by_year[year_curr] = lx
        local_x_meta[year_curr] = (year_prev, lx)

    median_x: float | None = None
    sigma_x: float | None = None
    if local_x_by_year:
        floats = [float(v) for v in local_x_by_year.values()]
        median_x = statistics.median(floats)
        deviations = [abs(x - median_x) for x in floats]
        mad_x = statistics.median(deviations) if deviations else 0.0
        sigma_x = MAD_SCALE * mad_x

    reasons_by_year: dict[int, list[str]] = {}

    for year in sorted_years:
        year_reasons: list[str] = []
        inv_cur = investment_cells.get(year)
        if inv_last is not None and inv_cur is not None and inv_cur > 0:
            share = inv_cur / inv_last
            if share < MIN_INVESTMENT_SHARE:
                year_reasons.append(
                    _reason_low_investment(year=current_year, investment_share=share)
                )

        if year in local_x_meta:
            year_prev, lx = local_x_meta[year]
            if abs(float(lx)) > ABS_LOCAL_X_LIMIT:
                year_reasons.append(_reason_extreme_local_x(local_x=lx))
            if (
                median_x is not None
                and sigma_x is not None
                and sigma_x > 0
            ):
                z_x = abs(float(lx) - median_x) / sigma_x
                if z_x >= EXCLUDE_Z_THRESHOLD:
                    year_reasons.append(
                        _reason_z_outlier(
                            year_prev=year_prev,
                            year_curr=year,
                            local_x=lx,
                            median_x=median_x,
                            z_x=z_x,
                        )
                    )

        if year_reasons:
            reasons_by_year[year] = year_reasons

    return {
        year: _compose_diagnostic_comment(reasons)
        for year, reasons in reasons_by_year.items()
    }


def _attach_diagnostics_to_graph_point_row(
    rows: list[dict[str, Any]],
    *,
    display_years: list[int],
    investment_cells: dict[int, Decimal | None],
    current_year: int | None,
) -> None:
    intensity_row = _find_ei_row(rows, ROW_KIND_INTENSITY)
    graph_point_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
    if intensity_row is None or graph_point_row is None:
        return
    notes = compute_intensity_cell_diagnostics(
        display_years=display_years,
        intensity_cells=intensity_row.get("cells") or {},
        investment_cells=investment_cells,
        current_year=current_year,
    )
    if notes:
        graph_point_row["cell_diagnostic_notes"] = notes


def attach_electrical_intensity_diagnostics_to_blocks(
    territory_blocks: list[dict[str, Any]],
    *,
    display_years: list[int],
    current_year: int | None,
    rf_investment_cells: dict[int, Decimal | None] | None = None,
) -> None:
    """Разметка всех блоков страницы (только строка «Характерные точки графика»)."""
    for block in territory_blocks:
        if block.get("layout") == "ved_sections":
            for section in block.get("ved_sections") or []:
                if not section.get("has_ei_model_block"):
                    continue
                _attach_diagnostics_to_graph_point_row(
                    section.get("rows") or [],
                    display_years=display_years,
                    investment_cells=_investment_cells_from_section(section),
                    current_year=current_year,
                )
        else:
            if block.get("has_ei_model_block", True):
                _attach_diagnostics_to_graph_point_row(
                    block.get("rows") or [],
                    display_years=display_years,
                    investment_cells=rf_investment_cells or {},
                    current_year=current_year,
                )
