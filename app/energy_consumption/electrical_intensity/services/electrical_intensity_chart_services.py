# -*- coding: utf-8 -*-
"""Данные scatter-графиков электроёмкости (как в Excel «Таблица 1»)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.energy_consumption.long_term_consumption.services.electrical_intensity_constants import (
    REF_ROW_ACCUM_FIXED_CAPITAL,
    REF_ROW_ACCUM_MONETARY_INCOME,
    REF_ROW_FD_ACCUM_FIXED_CAPITAL,
    ROW_KIND_CALCULATED,
    ROW_KIND_INTENSITY,
)


def _chart_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if f != f:  # NaN
        return None
    return f


def _find_ei_row(rows: list[dict[str, Any]], row_kind: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("row_kind") == row_kind:
            return row
    return None


def _find_ref_row(
    reference_rows: list[dict[str, Any]], ref_kind: str
) -> dict[str, Any] | None:
    for row in reference_rows:
        if row.get("row_kind") == ref_kind:
            return row
    return None


def _append_point(
    target: list[dict[str, Any]],
    *,
    year: int,
    x_raw: Any,
    y_raw: Any,
) -> None:
    xf = _chart_float(x_raw)
    yf = _chart_float(y_raw)
    if xf is None or yf is None:
        return
    target.append({"x": xf, "y": yf, "year": year})


def _chart_calc_intensity_y(
    accum_x: float | None,
    *,
    coef_a: float | None,
    coef_x: float | None,
) -> float | None:
    """Y = A × I^X (A — вручную введённый коэффициент)."""
    if accum_x is None or coef_a is None or coef_x is None:
        return None
    if not (accum_x > 0) or not (coef_a > 0):
        return None
    try:
        powered = accum_x**coef_x
    except (OverflowError, ValueError):
        return None
    if not (powered == powered):  # NaN
        return None
    y = coef_a * powered
    if not (y == y):
        return None
    return y


def build_ei_section_scatter_chart(
    section: dict[str, Any],
    *,
    display_years: list[int],
    current_year: int | None,
) -> dict[str, Any] | None:
    """
    Scatter: X — накопленные инвестиции, Y — электроёмкость.
    «Фактическая» — годы ≤ текущего; «Расчётная» — Y = A_ручн. × I^X по display_years.
    """
    if not (section.get("has_ei_block") or section.get("has_ei_intensity_block")):
        return None

    ref_rows = section.get("reference_rows") or []
    accum_row = _find_ref_row(ref_rows, REF_ROW_ACCUM_FIXED_CAPITAL)
    if accum_row is None:
        accum_row = _find_ref_row(ref_rows, REF_ROW_FD_ACCUM_FIXED_CAPITAL)
    if accum_row is None:
        accum_row = _find_ref_row(ref_rows, REF_ROW_ACCUM_MONETARY_INCOME)
    intensity_row = _find_ei_row(section.get("rows") or [], ROW_KIND_INTENSITY)
    calculated_row = _find_ei_row(section.get("rows") or [], ROW_KIND_CALCULATED)
    if accum_row is None or intensity_row is None:
        return None

    accum_cells = accum_row.get("cells") or {}
    intensity_cells = intensity_row.get("cells") or {}
    manual_coef_a = _chart_float(
        section.get("coefficient_a_manual") or section.get("coefficient_a")
    )
    coef_x = _chart_float(section.get("coefficient_x"))

    fact: list[dict[str, Any]] = []
    calc: list[dict[str, Any]] = []
    for year in display_years:
        x_val = accum_cells.get(year)
        if x_val is None:
            continue
        include_fact = current_year is None or year <= current_year
        if include_fact:
            _append_point(
                fact,
                year=year,
                x_raw=x_val,
                y_raw=intensity_cells.get(year),
            )
        if calculated_row is not None and manual_coef_a is not None and coef_x is not None:
            xf = _chart_float(x_val)
            y_calc = _chart_calc_intensity_y(
                xf, coef_a=manual_coef_a, coef_x=coef_x
            )
            if y_calc is not None:
                calc.append({"x": xf, "y": y_calc, "year": year})

    if not fact and not calc:
        return None

    if section.get("is_population_section"):
        x_axis_label = "Накопленные денежные доходы населения, млн руб."
        y_axis_label = "Потребление ээ на душу населения, кВт·ч/тыс. руб."
    else:
        x_axis_label = "Накопленные инвестиции, млн руб."
        y_axis_label = "Электроемкость, кВт·ч/тыс. руб."
    payload: dict[str, Any] = {
        "fact": fact,
        "calc": calc,
        "x_axis_label": x_axis_label,
        "y_axis_label": y_axis_label,
    }
    if calculated_row is not None and coef_x is not None:
        calc_bases: list[dict[str, Any]] = []
        for year in display_years:
            x_val = accum_cells.get(year)
            xf = _chart_float(x_val)
            if xf is None:
                continue
            calc_bases.append({"year": year, "x": xf})
        if calc_bases:
            payload["coef_x"] = coef_x
            payload["initial_coef_a"] = manual_coef_a
            payload["calc_bases"] = calc_bases
    return payload
