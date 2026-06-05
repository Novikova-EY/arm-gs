# -*- coding: utf-8 -*-
"""Тесты расчёта строки «Характерные точки графика»."""

from decimal import Decimal

from app.energy_consumption.long_term_consumption.services.electrical_intensity_constants import (
    POPULATION_SECTION_MARKER,
)
from app.energy_consumption.long_term_consumption.services.electrical_intensity_services import (
    _compute_ei_graph_point,
    _compute_pop_per_capita_consumption,
    compute_graph_points_for_row,
)


def test_population_graph_point_formula_matches_excel_log():
    per_capita_2017 = Decimal("1.1136159156")
    per_capita_2016 = Decimal("1.0932717297")
    accum_2017 = Decimal("75789.64413603014")
    accum_2016 = Decimal("66208.82892879898")

    result = _compute_ei_graph_point(
        per_capita_2017,
        per_capita_2016,
        accum_2017,
        accum_2016,
    )
    assert result is not None
    assert abs(result - Decimal("0.136424785064")) < Decimal("0.000000001")


def test_pop_per_capita_consumption_is_household_over_population():
    value = _compute_pop_per_capita_consumption(
        Decimal("1113.6159156"),
        Decimal("1000"),
    )
    assert value == Decimal("1.1136159156")


def test_compute_graph_points_for_row_accepts_population_marker(app, monkeypatch):
    """Маркер блока «Население» не должен приводиться к int в маршруте AJAX."""
    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services.get_current_version",
        lambda: 1,
    )
    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services._ei_current_year_number",
        lambda: 2020,
    )
    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services._load_ved_consumption_values_map",
        lambda **kwargs: {(1, 2017): Decimal("100"), (1, 2016): Decimal("90")},
    )
    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services._refdata_ved_types_for_version",
        lambda version_id: [],
    )

    class _HouseholdVed:
        id = 1

    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services._find_ved_by_target",
        lambda ved_types, target: _HouseholdVed(),
    )
    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services._load_population_by_fd_year",
        lambda **kwargs: {2017: Decimal("100"), 2016: Decimal("100")},
    )
    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services._load_accum_monetary_income_by_fd_year",
        lambda **kwargs: {
            2017: Decimal("75789.64413603014"),
            2016: Decimal("66208.82892879898"),
        },
    )
    monkeypatch.setattr(
        "app.energy_consumption.long_term_consumption.services.electrical_intensity_services._load_population_year_values_map",
        lambda **kwargs: {},
    )

    with app.app_context():
        result = compute_graph_points_for_row(
            rounding_digits=0,
            display_years=[2016, 2017],
            territory_kind="fd",
            territory_id=5,
            ved_id=POPULATION_SECTION_MARKER,
        )
    assert "2017" in result["cells_display"]
