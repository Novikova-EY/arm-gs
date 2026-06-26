# -*- coding: utf-8 -*-
"""Тесты расчёта строки «Характерные точки графика»."""

from decimal import Decimal

from werkzeug.datastructures import ImmutableMultiDict

from app.electrical_intensity.services import (
    electrical_intensity_services as eis,
)
from app.electrical_intensity.services.electrical_intensity_constants import (
    POPULATION_SECTION_MARKER,
    REF_ROW_HOUSEHOLD_CONSUMPTION,
    ROW_KIND_CALCULATED,
    ROW_KIND_GRAPH_POINT,
)
from app.electrical_intensity.services.electrical_intensity_services import (
    _compute_ei_graph_point,
    _compute_household_from_population_and_per_capita,
    _compute_pop_per_capita_consumption,
    _enrich_population_household_plan_years,
    _should_autofill_graph_point_cell,
    compute_graph_points_for_row,
    save_electrical_intensity_from_post,
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


def test_household_from_population_and_per_capita_is_inverse():
    per_capita = Decimal("1.1136159156")
    population = Decimal("1000")
    household = _compute_household_from_population_and_per_capita(population, per_capita)
    assert household == Decimal("1113.6159156")


def test_enrich_population_household_plan_years_sets_formula_and_cells(app, monkeypatch):
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services.get_year_feature_dict",
        lambda: {2025: "план"},
    )
    reference_rows = [
        {
            "row_kind": REF_ROW_HOUSEHOLD_CONSUMPTION,
            "cells": {2020: Decimal("100"), 2025: Decimal("999")},
            "cells_display": {},
            "cell_tooltips": {},
        }
    ]
    section_rows = [
        {
            "row_kind": ROW_KIND_CALCULATED,
            "cells": {2025: Decimal("1.5")},
        }
    ]
    with app.app_context():
        _enrich_population_household_plan_years(
            reference_rows,
            section_rows=section_rows,
            population_by_year={2025: Decimal("1000")},
            display_years=[2020, 2025],
            rounding_digits=1,
            current_year=2020,
        )
    household_row = reference_rows[0]
    assert household_row["cells"][2025] == Decimal("1500")
    assert household_row["cells"][2020] == Decimal("100")
    assert "Численность населения" in household_row["formula_hint"]
    assert 2025 in household_row["computed_years"]


def test_compute_graph_points_for_row_accepts_population_marker(app, monkeypatch):
    """Маркер блока «Население» не должен приводиться к int в маршруте AJAX."""
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services.get_current_version",
        lambda: 1,
    )
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services._ei_current_year_number",
        lambda: 2020,
    )
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services._load_ved_consumption_values_map",
        lambda **kwargs: {(1, 2017): Decimal("100"), (1, 2016): Decimal("90")},
    )
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services._refdata_ved_types_for_version",
        lambda version_id: [],
    )

    class _HouseholdVed:
        id = 1

    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services._find_ved_by_target",
        lambda ved_types, target: _HouseholdVed(),
    )
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services._load_population_by_fd_year",
        lambda **kwargs: {2017: Decimal("100"), 2016: Decimal("100")},
    )
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services._load_accum_monetary_income_by_fd_year",
        lambda **kwargs: {
            2017: Decimal("75789.64413603014"),
            2016: Decimal("66208.82892879898"),
        },
    )
    monkeypatch.setattr(
        "app.electrical_intensity.services.electrical_intensity_services._load_population_year_values_map",
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


def test_should_not_autofill_graph_point_when_db_row_exists_with_null():
    row = {
        "row_kind": ROW_KIND_GRAPH_POINT,
        "cells": {2023: None},
        "db_years": frozenset({2023}),
    }
    assert _should_autofill_graph_point_cell(row, 2023) is False
    assert _should_autofill_graph_point_cell(row, 2024) is True


def test_save_graph_point_clear_persisted_when_orig_had_value(app, monkeypatch):
    """Очистка отображаемого graph_point создаёт NULL в БД."""
    class _Row:
        def __init__(self):
            self.parameter_value = None
            self.modified_by = None

    saved_row = _Row()

    def _capture_fd_row(cache, version_id, fd_id, ved_id, row_kind, year_n, user):
        return saved_row

    monkeypatch.setattr(eis, "get_current_version", lambda: 20)
    monkeypatch.setattr(eis, "_ei_current_year_number", lambda: 2025)
    monkeypatch.setattr(eis, "_username", lambda: "tester")
    monkeypatch.setattr(eis, "_refdata_ved_ids", lambda version_id: frozenset({5}))
    monkeypatch.setattr(eis, "_refdata_ved_types_for_version", lambda version_id: [])
    monkeypatch.setattr(eis, "_preload_rf_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_fd_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_rf_coef_row", lambda version_id: None)
    monkeypatch.setattr(eis, "_preload_fd_coef_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_coef_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_resolve_fd_year_row", _capture_fd_row)
    monkeypatch.setattr(
        eis,
        "queue_electrical_intensity_cell_change",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        eis,
        "_territory_label_for_log",
        lambda kind, fd_id: f"fd:{fd_id}",
    )
    monkeypatch.setattr(
        eis,
        "_ved_label_for_log",
        lambda ved_id, **kwargs: f"ved:{ved_id}",
    )

    form = ImmutableMultiDict(
        [
            ("territory_kind[]", "fd"),
            ("territory_id[]", "88"),
            ("cell_ved_id[]", "5"),
            ("row_kind[]", "graph_point"),
            ("cell_year[]", "2023"),
            ("cell_value[]", ""),
            ("cell_orig_value[]", "1.2"),
        ]
    )

    with app.app_context():
        with app.test_request_context():
            updated, skipped = save_electrical_intensity_from_post(form)

    assert updated == 1
    assert skipped == 0
    assert saved_row.parameter_value is None


def test_save_graph_point_clear_computed_without_orig(app, monkeypatch):
    """Очистка вычисленного graph_point без cell_orig_value, но с маркером отображения."""
    saved_row = type("Row", (), {"parameter_value": None, "modified_by": None})()

    monkeypatch.setattr(eis, "get_current_version", lambda: 20)
    monkeypatch.setattr(eis, "_ei_current_year_number", lambda: 2025)
    monkeypatch.setattr(eis, "_username", lambda: "tester")
    monkeypatch.setattr(eis, "_refdata_ved_ids", lambda version_id: frozenset({1}))
    monkeypatch.setattr(eis, "_refdata_ved_types_for_version", lambda version_id: [])
    monkeypatch.setattr(eis, "_preload_rf_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_fd_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_rf_coef_row", lambda version_id: None)
    monkeypatch.setattr(eis, "_preload_fd_coef_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_coef_cache", lambda version_id: {})
    monkeypatch.setattr(
        eis,
        "_resolve_fd_year_row",
        lambda cache, version_id, fd_id, ved_id, row_kind, year_n, user: saved_row,
    )
    monkeypatch.setattr(
        eis,
        "queue_electrical_intensity_cell_change",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        eis,
        "_territory_label_for_log",
        lambda kind, fd_id: f"fd:{fd_id}",
    )
    monkeypatch.setattr(
        eis,
        "_ved_label_for_log",
        lambda ved_id, **kwargs: f"ved:{ved_id}",
    )

    form = ImmutableMultiDict(
        [
            ("territory_kind[]", "fd"),
            ("territory_id[]", "88"),
            ("cell_ved_id[]", "1"),
            ("row_kind[]", "graph_point"),
            ("cell_year[]", "2023"),
            ("cell_value[]", ""),
            ("cell_gp_had_display[]", "1"),
        ]
    )

    with app.app_context():
        with app.test_request_context():
            updated, skipped = save_electrical_intensity_from_post(form)

    assert updated == 1
    assert skipped == 0
    assert saved_row.parameter_value is None


def test_save_graph_point_not_skipped_when_ved_missing_from_cache(app, monkeypatch):
    """graph_point не пропускается, если ВЭД есть в refdata_ids, но не попал в ved_by_id."""
    saved: dict[str, object] = {}

    class _Row:
        parameter_value = Decimal("0.1")
        modified_by = None

    def _capture_fd_row(cache, version_id, fd_id, ved_id, row_kind, year_n, user):
        saved["fd_id"] = fd_id
        saved["ved_id"] = ved_id
        saved["year"] = year_n
        return _Row()

    monkeypatch.setattr(eis, "get_current_version", lambda: 20)
    monkeypatch.setattr(eis, "_ei_current_year_number", lambda: 2025)
    monkeypatch.setattr(eis, "_username", lambda: "tester")
    monkeypatch.setattr(eis, "_refdata_ved_ids", lambda version_id: frozenset({5}))
    monkeypatch.setattr(eis, "_refdata_ved_types_for_version", lambda version_id: [])
    monkeypatch.setattr(eis, "_preload_rf_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_fd_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_rf_coef_row", lambda version_id: None)
    monkeypatch.setattr(eis, "_preload_fd_coef_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_coef_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_resolve_fd_year_row", _capture_fd_row)
    monkeypatch.setattr(
        eis,
        "queue_electrical_intensity_cell_change",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        eis,
        "_territory_label_for_log",
        lambda kind, fd_id: f"fd:{fd_id}",
    )
    monkeypatch.setattr(
        eis,
        "_ved_label_for_log",
        lambda ved_id, **kwargs: f"ved:{ved_id}",
    )

    form = ImmutableMultiDict(
        [
            ("territory_kind[]", "fd"),
            ("territory_id[]", "88"),
            ("cell_ved_id[]", "5"),
            ("row_kind[]", "graph_point"),
            ("cell_year[]", "2019"),
            ("cell_value[]", "1.5"),
        ]
    )

    with app.app_context():
        with app.test_request_context():
            updated, skipped = save_electrical_intensity_from_post(form)

    assert updated == 1
    assert skipped == 0
    assert saved["ved_id"] == 5
    assert saved["year"] == 2019
