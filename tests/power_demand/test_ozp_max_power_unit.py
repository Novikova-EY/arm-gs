# -*- coding: utf-8 -*-
"""Unit tests for ОЗП maxima table helpers."""

from decimal import Decimal

from flask import Flask

from app.power_demand.services import ozp_max_power_services as ozp


def test_build_ozp_columns_last_year_has_two_periods():
    columns = ozp.build_ozp_columns(2020, 2024)
    assert [c["calendar_year"] for c in columns] == [2020, 2021, 2022, 2023, 2024, 2024]
    assert [c["ozp_end"] for c in columns] == [2020, 2021, 2022, 2023, 2024, 2025]
    assert columns[0]["label"] == "2019–2020 гг."
    assert columns[-2]["label"] == "2023–2024 гг."
    assert columns[-1]["label"] == "2024–2025 гг."


def test_build_year_header_groups_spans_last_year():
    columns = ozp.build_ozp_columns(2020, 2024)
    groups = ozp.build_year_header_groups(columns)
    assert groups == [
        {"year": 2020, "colspan": 1},
        {"year": 2021, "colspan": 1},
        {"year": 2022, "colspan": 1},
        {"year": 2023, "colspan": 1},
        {"year": 2024, "colspan": 2},
    ]


def test_parse_year_range_defaults_to_n_minus_4(monkeypatch):
    monkeypatch.setattr(ozp, "period_base_year_n", lambda: 2024)
    sy, ey = ozp.parse_year_range(None, None, years=list(range(2010, 2041)))
    assert (sy, ey) == (2020, 2024)


def test_parse_year_range_reads_query_and_swaps():
    sy, ey = ozp.parse_year_range("2023", "2021", years=list(range(2010, 2041)))
    assert (sy, ey) == (2021, 2023)


def test_parse_rounding_digits_default_integer():
    assert ozp.parse_rounding_digits(None) == -1
    assert ozp.parse_rounding_digits("2") == 2
    assert ozp.parse_rounding_digits("9") == -1


def test_calc_growth_pct_matches_sample():
    current = Decimal("155273")
    previous = Decimal("148078")
    growth = ozp.calc_growth_pct(current, previous)
    assert growth is not None
    assert round(growth, 2) == Decimal("4.86")
    assert ozp.format_growth_display(growth) == "4,86"
    assert ozp.format_growth_display(None) == "—"


def test_compute_growth_series_uses_previous_outside_range():
    series = ozp.compute_growth_series(
        [Decimal("148078"), Decimal("155273"), None],
        Decimal("151900"),
    )
    assert series[0] is not None
    assert round(series[0], 2) == Decimal("-2.52")
    assert series[1] is not None
    assert round(series[1], 2) == Decimal("4.86")
    assert series[2] is None


def test_compute_growth_series_empty_previous_skips_first():
    series = ozp.compute_growth_series(
        [Decimal("100"), Decimal("110")],
        None,
    )
    assert series[0] is None
    assert series[1] == Decimal("10")


def test_save_ozp_cells_rejects_growth_pct():
    result = ozp.save_ozp_cells(
        [{"ozp_end_year": 2024, "parameter_key": "growth_pct", "value": "4,86"}]
    )
    assert result["ok"] is False
    assert "показатель" in result["error"].lower()


def test_save_ozp_cells_rejects_bad_parameter():
    result = ozp.save_ozp_cells(
        [{"ozp_end_year": 2024, "parameter_key": "note", "value": "1"}]
    )
    assert result["ok"] is False
    assert "показатель" in result["error"].lower()


def test_save_ozp_cells_rejects_bad_year():
    result = ozp.save_ozp_cells(
        [{"ozp_end_year": "abc", "parameter_key": "max_power", "value": "1"}]
    )
    assert result["ok"] is False


def test_ozp_maxima_routes_registered():
    from app.power_demand.routes import ozp_max_power_routes as routes

    assert callable(routes.ozp_maxima)
    assert callable(routes.ozp_maxima_save)
    assert callable(routes.ozp_maxima_export)


def test_ozp_maxima_page_uses_template(monkeypatch):
    from app.power_demand.routes import ozp_max_power_routes as routes

    captured = {}

    def fake_render(template_name, **ctx):
        captured["template"] = template_name
        captured["ctx"] = ctx
        return "ok"

    monkeypatch.setattr(routes, "render_template", fake_render)
    monkeypatch.setattr(routes.ozp, "filter_year_list", lambda: list(range(2018, 2031)))
    monkeypatch.setattr(
        routes.ozp,
        "build_page_context",
        lambda **kwargs: {
            "page_title": "t",
            "start_year": kwargs["start_year"],
            "end_year": kwargs["end_year"],
            "rounding_digits": kwargs["rounding_digits"],
            "can_edit_ozp": kwargs["can_edit"],
        },
    )
    monkeypatch.setattr(routes, "can_edit_power_demand", lambda _user: True)

    app = Flask(__name__)
    with app.test_request_context("/power_demand/ozp_maxima/?start_year=2020&end_year=2024"):
        body = routes.ozp_maxima.__wrapped__()
    assert body == "ok"
    assert captured["template"] == "power_demand/ozp_max_power.html"
    assert captured["ctx"]["start_year"] == 2020
    assert captured["ctx"]["end_year"] == 2024
