"""UI year form helpers for power demand coeff summary pages."""

from __future__ import annotations

from flask import Flask

from app.power_demand.routes import demand_summary_routes as routes


def test_parse_coeff_ui_year_form_range_defaults_to_reporting_window(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    with app.test_request_context("/power_demand/summary/coeff/oes/"):
        sy, ey, applied = routes._parse_coeff_ui_year_form_range(2025)
    assert (sy, ey, applied) == (2016, 2025, False)


def test_parse_coeff_ui_year_form_range_reads_applied_years(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    with app.test_request_context(
        "/power_demand/summary/coeff/oes/?start_year=2018&end_year=2022"
    ):
        sy, ey, applied = routes._parse_coeff_ui_year_form_range(2025)
    assert (sy, ey, applied) == (2018, 2022, True)


def test_apply_coeff_ui_year_form_context_sets_flags(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    ctx = {"start_year": 2016, "end_year": 2043}
    with app.test_request_context(
        "/power_demand/summary/coeff/oes/?start_year=2017&end_year=2019"
    ):
        routes._apply_coeff_ui_year_form_context(ctx, 2025)
    assert ctx["start_year"] == 2017
    assert ctx["end_year"] == 2019
    assert ctx["pd_coeff_years_applied"] is True
