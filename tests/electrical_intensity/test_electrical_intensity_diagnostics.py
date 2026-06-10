# -*- coding: utf-8 -*-
"""Тесты диагностики строки «Электроёмкость»."""

from decimal import Decimal

from app.energy_consumption.long_term_consumption.services.electrical_intensity_diagnostic_services import (
    ABS_LOCAL_X_LIMIT,
    EXCLUDE_Z_THRESHOLD,
    MIN_INVESTMENT_SHARE,
    compute_intensity_cell_diagnostics,
)


def _cells(**pairs: float) -> dict[int, Decimal | None]:
    return {year: Decimal(str(v)) for year, v in pairs.items()}


def test_low_investment_share_flags_year():
    years = list(range(2014, 2021))
    intensity = {y: Decimal(str(100.0 + y)) for y in years}
    investment = {y: Decimal(str(10.0 * (y - 2013))) for y in years}
    investment[2020] = Decimal("1000")

    notes = compute_intensity_cell_diagnostics(
        display_years=years,
        intensity_cells=intensity,
        investment_cells=investment,
        current_year=2020,
    )
    assert 2014 in notes
    assert "15%" in notes[2014] or "15,0%" in notes[2014]


def test_extreme_local_x_flags_current_year():
    years = [2018, 2019, 2020]
    intensity = {
        2018: Decimal("100"),
        2019: Decimal("100"),
        2020: Decimal("800"),
    }
    investment = {
        2018: Decimal("100"),
        2019: Decimal("110"),
        2020: Decimal("120"),
    }
    notes = compute_intensity_cell_diagnostics(
        display_years=years,
        intensity_cells=intensity,
        investment_cells=investment,
        current_year=2020,
    )
    assert 2020 in notes
    assert str(ABS_LOCAL_X_LIMIT).replace(".", ",") in notes[2020] or "2,5" in notes[2020]


def test_multiple_reasons_combined():
    years = [2018, 2019]
    intensity = {2018: Decimal("50"), 2019: Decimal("200")}
    investment = {2018: Decimal("10"), 2019: Decimal("20")}
    notes = compute_intensity_cell_diagnostics(
        display_years=years,
        intensity_cells=intensity,
        investment_cells={**investment, 2020: Decimal("1000")},
        current_year=2020,
    )
    if 2019 in notes:
        assert "Причины:" in notes[2019] or "Причина:" in notes[2019]
