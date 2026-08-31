"""UI year form helpers for power demand coeff summary pages."""

from __future__ import annotations

from flask import Flask

from app.power_demand.routes import demand_summary_routes as routes
from app.power_demand.services.demand_summary_services import (
    slice_coeff_summary_for_lazy_long_segment,
)


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


def test_apply_coeff_ui_year_form_context_keeps_table_years(monkeypatch):
    """Форма 2021–2031 не режет колонки таблицы: скрытие — на клиенте."""
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    table_years = list(range(2016, 2032))
    ctx = {"start_year": 2016, "end_year": 2043, "years": list(table_years)}
    with app.test_request_context(
        "/power_demand/summary/coeff/oes/?start_year=2021&end_year=2031"
    ):
        routes._apply_coeff_ui_year_form_context(ctx, 2025)
    assert ctx["years"] == table_years
    assert ctx["start_year"] == 2021
    assert ctx["end_year"] == 2031
    assert ctx["pd_coeff_years_applied"] is True


def test_parse_coeff_page_data_year_range_defaults_to_reporting(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    monkeypatch.setattr(routes, "_coeff_base_year_n", lambda: 2025)
    with app.test_request_context("/power_demand/summary/coeff/oes/"):
        n, sy, ey, include_medium, include_long = routes._parse_coeff_page_data_year_range()
    assert (n, sy, ey, include_medium, include_long) == (2025, 2016, 2025, False, False)


def test_parse_coeff_page_data_year_range_pd_medium(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    monkeypatch.setattr(routes, "_coeff_base_year_n", lambda: 2025)
    with app.test_request_context("/power_demand/summary/coeff/oes/?pd_medium=1"):
        n, sy, ey, include_medium, include_long = routes._parse_coeff_page_data_year_range()
    assert (n, sy, ey, include_medium, include_long) == (2025, 2016, 2031, True, False)


def test_parse_coeff_page_data_year_range_form_past_n_includes_medium(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    monkeypatch.setattr(routes, "_coeff_base_year_n", lambda: 2025)
    with app.test_request_context(
        "/power_demand/summary/coeff/oes/?start_year=2021&end_year=2031"
    ):
        n, sy, ey, include_medium, include_long = routes._parse_coeff_page_data_year_range()
    assert n == 2025
    assert (sy, ey) == (2016, 2031)
    assert include_medium is True
    assert include_long is False


def test_parse_coeff_page_data_year_range_include_long(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, "_filter_year_list_for_summary", lambda: list(range(2010, 2041)))
    monkeypatch.setattr(routes, "_coeff_base_year_n", lambda: 2025)
    with app.test_request_context(
        "/power_demand/summary/coeff/oes/?coeff_include_long=1"
    ):
        n, sy, ey, include_medium, include_long = routes._parse_coeff_page_data_year_range()
    assert (n, sy, ey, include_medium, include_long) == (2025, 2016, 2040, True, True)


def test_coeff_period_header_groups_html_reporting_only():
    groups = routes._coeff_period_header_groups_html(
        include_medium=False, include_long=False
    )
    assert [g["key"] for g in groups] == ["reporting"]


def test_slice_coeff_summary_drops_medium_when_not_requested():
    years = list(range(2016, 2044))
    ctx = {
        "years": list(years),
        "year_is_plan": {y: False for y in years},
        "summary_rows": [
            {
                "year_values": [str(y) for y in years],
                "year_k_values": ["k"] * len(years),
            }
        ],
    }
    slice_coeff_summary_for_lazy_long_segment(
        ctx, 2025, include_long=False, include_medium=False
    )
    assert ctx["years"] == list(range(2016, 2026))
    assert ctx["summary_rows"][0]["year_values"] == [str(y) for y in range(2016, 2026)]
    assert ctx["summary_include_medium_years"] is False
