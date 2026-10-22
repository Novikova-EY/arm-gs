"""Сводка складывает исходные, а не округленные значения трех категорий ТЭС."""
from decimal import Decimal
from html import unescape
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from flask import Flask, request
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.ecology.routes import calculation_summary_routes as routes
from app.ecology.services import calculation_summary_services as summary
from app.ecology.services import fuel_exchange_services as exchange
from app.ecology.services import new_tes_page_services as new
from app.ecology.services import operating_tes_page_services as operating


@pytest.fixture
def summary_data(monkeypatch):
    for module in (new, operating):
        monkeypatch.setattr(module, "get_year_columns", lambda *args: [2026, 2027])
        monkeypatch.setattr(module, "get_filter_year_list", lambda: [2026, 2027])
        monkeypatch.setattr(module, "get_year_feature_dict", lambda: {})
        monkeypatch.setattr(module, "load_characteristic_overrides", lambda years: {})
        monkeypatch.setattr(module, "get_fuel_module_consumption_row_specs", lambda: [
            {"key": "b", "label": "Всего", "kind": "total"},
            {"key": "gaz_prir", "label": "Природный газ", "kind": "value"},
        ])
    monkeypatch.setattr(new, "ensure_default_norm_rows", lambda years: None)
    monkeypatch.setattr(new, "load_norm_overrides", lambda years: {})
    monkeypatch.setattr(new, "ot_formula_text", lambda key: "")
    monkeypatch.setattr(operating, "ensure_default_persisted_rows", lambda years: None)
    monkeypatch.setattr(operating, "load_input_overrides", lambda years: {})
    monkeypatch.setattr(operating, "load_coefficient_overrides", lambda years, affiliation="all": {})

    def bucket(amount, year):
        value = Decimal(amount) * (year - 2025)
        return {"gaz_prir": value, "gaz": value, "b": value, "e": value * 1000, "q": value}

    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        year: {"vsego": bucket("1.04", year)} for year in years
    })
    monkeypatch.setattr(new, "load_accepted_new_tes_fuel_inputs", lambda years: {
        year: {
            "vsego": {"le100": bucket("2.04", year), "gt100": bucket("3.04", year)},
            "centr": {"le100": bucket("4.04", year)},
        } for year in years
    })


def cell(context, row_key, territory="vsego"):
    column = next(col for col in context["value_columns"] if col.get("territory_slug", col["slug"]) == territory)
    raw = next(row for row in context["rows"] if row["key"] == row_key)["col_values_raw"][column["slug"]]
    return Decimal(raw) if raw else None


def test_fuel_sums_three_categories_before_rounding_and_preserves_missing(summary_data):
    context = summary.build_calculation_summary_context("vsego", "toplivo", view_year=2026, rounding_digits=1)
    assert cell(context, "gaz_prir") == Decimal("6.12")
    row = next(row for row in context["rows"] if row["key"] == "gaz_prir")
    assert row["col_values"]["vsego:2026"] == "6,1"
    assert cell(context, "ee_generation") == Decimal("6.12")
    assert cell(context, "heat_output") == Decimal("6.12")
    assert cell(context, "gaz_prir", "centr") == Decimal("4.04")
    assert cell(context, "gaz_prir", "yug") is None
    context = summary.build_calculation_summary_context("vsego", "toplivo", view_year=2027)
    assert cell(context, "gaz_prir") == Decimal("12.24")


@pytest.mark.parametrize("tab,capacity", [("new-le100", "le100"), ("new-gt100", "gt100")])
def test_new_category_is_a_duplicate(summary_data, tab, capacity):
    context = summary.build_calculation_summary_context("vsego", tab, view_year=2026)
    source = new.build_new_tes_table_context("vsego", "obemy", capacity_class=capacity, view_year=2026)
    assert context["rows"] == source["rows"]
    assert context["value_columns"] == source["value_columns"]
    assert context["new_tes_volume_columns"] == source["new_tes_volume_columns"]
    assert context["can_edit"] is False


def test_operating_category_is_a_duplicate(summary_data):
    context = summary.build_calculation_summary_context("vsego", "operating", view_year=2026)
    source = operating.build_operating_tes_table_context("vsego", "obemy", view_year=2026)
    assert context["rows"] == source["rows"]
    assert context["specific_emission_tables"] == source["specific_emission_tables"]


def test_new_and_russia_totals_use_transposed_units_and_do_not_double_count_fuel(summary_data):
    context = summary.build_calculation_summary_context("vsego", "new", view_year=2026)
    assert [row["key"] for row in context["rows"]] == [spec["key"] for spec in summary.VOLUME_ROWS]
    assert not context["new_tes_volume_columns"]
    assert not context["specific_emission_tables"]
    assert cell(context, "nox") == Decimal("5.08") * Decimal("1.26") / 1000
    assert cell(context, "co2") == Decimal("5.08") * Decimal("1.59")
    assert cell(context, "pollutants_total") == cell(context, "nox")
    assert cell(context, "co2", "centr") == Decimal("4.04") * Decimal("1.59")
    assert cell(context, "co2", "yug") is None
    russia = summary.build_calculation_summary_context("vsego", "russia", view_year=2026)
    source = operating.build_operating_tes_table_context("vsego", "obemy", view_year=2026)
    for spec in summary.VOLUME_ROWS:
        assert cell(russia, spec["key"]) == (cell(source, spec["key"]) or 0) + (cell(context, spec["key"]) or 0)
    assert cell(russia, "co2") == Decimal("6.12") * Decimal("1.59")
    assert cell(russia, "co2", "centr") == cell(context, "co2", "centr")
    assert len(russia["specific_emission_tables"]) == 3


@pytest.mark.parametrize("tab", [tab["slug"] for tab in summary.CALCULATION_SUMMARY_TABS])
def test_all_tabs_render_and_keep_filters(summary_data, tab):
    context = summary.build_calculation_summary_context(
        "vsego", tab, start_year=2026, end_year=2027, view_year=2026, rounding_digits=2,
    )
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(Path("app/templates")),
    ]))
    context["url_for"] = lambda endpoint, **values: "/" + endpoint + "?" + urlencode({
        key: value for key, value in values.items() if value is not None
    })
    with Flask(__name__).test_request_context("/?rounding_digits=2"):
        html = env.get_template("ecology/operating_tes/operating_tes_table.html").render(
            **context, request=request, current_user=SimpleNamespace(is_authenticated=True), csrf_token="test",
        )
    anchor_pattern = r'<a href="([^"]+)"\s+class="([^"]+)"([^>]*)>\s*([^<]+?)\s*</a>'
    main_nav = html.split('aria-label="Листы расчёта">', 1)[1].split("</div>", 1)[0]
    main_links = re.findall(anchor_pattern, main_nav)
    assert [link[3] for link in main_links] == [
        "Данные по модулю Топливо", "Объемы выбросов для действующих ТЭС",
        "Объемы выбросов для новых ТЭС", "Объемы выбросов по России",
    ]
    active_parent = "new" if tab in {"new", "new-le100", "new-gt100"} else tab
    for href, classes, _, _ in main_links:
        target = parse_qs(urlsplit(unescape(href)).query)["sheet_slug"][0]
        assert ("btn-primary" in classes.split()) == (target == active_parent)
    subnav_marker = 'aria-label="Объемы выбросов для новых ТЭС">'
    sublinks = []
    if active_parent == "new":
        subnav = html.split(subnav_marker, 1)[1].split("</div>", 1)[0]
        sublinks = re.findall(anchor_pattern, subnav)
        assert [link[3] for link in sublinks] == ["Всего", "до 100 МВт", "100 МВт и более"]
        for (href, classes, attrs, _), target in zip(sublinks, ("new", "new-le100", "new-gt100")):
            assert parse_qs(urlsplit(unescape(href)).query)["sheet_slug"] == [target]
            assert ("btn-primary" in classes.split()) == (target == tab)
            assert ('aria-current="page"' in attrs) == (target == tab)
    else:
        assert subnav_marker not in html
    for href, _, _, _ in [*main_links, *sublinks]:
        params = parse_qs(urlsplit(unescape(href)).query)
        assert params["view_year"] == ["2026"]
        assert params["start_year"] == ["2026"]
        assert params["end_year"] == ["2027"]
        assert params["rounding_digits"] == ["2"]
    link = html.split('title="Показать данные за 2027 год"')[0].rsplit('href="', 1)[1]
    assert "view_year=2027" in link
    assert "start_year=2026" in link
    assert "end_year=2027" in link
    assert "rounding_digits=2" in link
    assert f"sheet_slug={tab}" in link
    assert 'data-can-edit="0"' in html
    assert 'class="form-control form-control-sm ot-edit-value"' not in html
    assert html.count('id="otTerritoryFilterMenu"') == 1
    assert 'data-storage-key="ecology.calculation_summary.territories"' in html
    filter_script_url = context["url_for"]("static", filename="js/ecology/tes_territory_filter.js")
    assert html.count(f'<script src="{filter_script_url}"></script>') == 1
    for table_html in html.split("<table")[1:]:
        header = table_html.split("</thead>", 1)[0]
        assert header.count("data-territory-filter-button") == 1
        assert 'aria-controls="otTerritoryFilterMenu"' in header
    if tab == "russia":
        assert html.count("<table") == 4
        for table in context["specific_emission_tables"]:
            assert table["title"] in html
            assert f'id="ot-specific-{table["key"]}"' in html


@pytest.fixture
def russia_specific_data(summary_data, monkeypatch):
    for module in (new, operating):
        monkeypatch.setattr(module, "get_fuel_module_consumption_row_specs", lambda: [
            {"key": key, "label": key, "kind": "value"}
            for key in ("b", "gaz_prir", "mazut", "maztop", "torf", "tvproch", "ugol", "kuzngd")
        ])
    monkeypatch.setattr(operating, "load_coefficient_overrides", lambda years, affiliation="all": {
        ("vsego", year, "co_k"): Decimal("0") for year in years
    })

    def bucket(factor, year):
        scale = Decimal(factor) * (year - 2025)
        values = {key: Decimal(value) * scale for key, value in {
            "b": "100.04", "q": "859.8", "gaz": "10.04", "gaz_prir": "10.04",
            "mazut": "2.04", "maztop": "2.04", "torf": "3.04", "tvproch": "4.04",
            "ugol": "5.04", "kuzngd": "5.04",
        }.items()}
        values["e"] = Decimal("10004") * scale * scale
        return values

    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        year: {"vsego": bucket(1, year)} for year in years
    })
    monkeypatch.setattr(new, "load_accepted_new_tes_fuel_inputs", lambda years: {
        year: {
            "vsego": {"le100": bucket(2, year), "gt100": bucket(3, year)},
            "centr": {"le100": bucket(4, year)},
        } for year in years
    })


@pytest.mark.parametrize("year", [2026, 2027])
@pytest.mark.parametrize("digits", [1, 3])
def test_russia_specific_emissions_use_total_fuel_and_unrounded_mass(russia_specific_data, year, digits):
    context = summary.build_calculation_summary_context("vsego", "russia", view_year=year, rounding_digits=digits)
    fuel_context = summary.build_calculation_summary_context("vsego", "toplivo", view_year=year, rounding_digits=digits)
    tables = context["specific_emission_tables"]
    assert [table["key"] for table in tables] == ["energy", "energy_fuel", "fuel"]
    assert cell(context, "co") > 0
    for territory in ("vsego", "centr"):
        electricity = cell(fuel_context, "ee_generation", territory)
        brought_energy = electricity + cell(fuel_context, "heat_output", territory) / Decimal("859.8")
        fuel = cell(fuel_context, "b", territory)
        solid_fuel = sum(cell(fuel_context, key, territory) for key in ("mazut", "torf", "tvproch", "ugol"))
        for spec in summary.VOLUME_ROWS:
            key = spec["key"]
            mass = cell(context, key, territory)
            energy_mass = mass / 1000 if key == "co" else mass
            if key == "pollutants_total":
                energy_mass = sum(cell(context, item, territory) for item in ("ash", "so2", "nox")) + cell(context, "co", territory) / 1000
            expected = [
                energy_mass / brought_energy,
                energy_mass / electricity,
                mass * 100 / solid_fuel if key in {"ash", "so2"} else mass / fuel * 1000,
            ]
            column = f"{territory}:{year}"
            for table, value in zip(tables, expected):
                row = next(row for row in table["rows"] if row["key"] == key)
                assert Decimal(row["col_values_raw"][column]) == pytest.approx(value)
                assert row["col_values"][column] == operating.format_cell(value, digits)
    for table in tables:
        assert [row["key"] for row in table["rows"]] == [row["key"] for row in context["rows"]]
        assert all(row["col_values_raw"][f"yug:{year}"] == "" for row in table["rows"])


@pytest.mark.parametrize("denominator", [None, Decimal("0")])
def test_russia_specific_emissions_without_denominators_are_empty(summary_data, monkeypatch, denominator):
    bucket = {"gaz_prir": Decimal("10"), "gaz": Decimal("10")}
    if denominator is not None:
        bucket.update({key: denominator for key in ("b", "e", "q")})
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {year: {"vsego": dict(bucket)} for year in years})
    monkeypatch.setattr(new, "load_accepted_new_tes_fuel_inputs", lambda years: {
        year: {"vsego": {"le100": dict(bucket), "gt100": dict(bucket)}} for year in years
    })
    context = summary.build_calculation_summary_context("vsego", "russia", view_year=2026)
    assert cell(context, "co2") > 0
    for table in context["specific_emission_tables"]:
        for row in table["rows"]:
            assert row["col_values_raw"]["vsego:2026"] == ""
            assert row["col_values"]["vsego:2026"] == "–"


def test_index_keeps_selected_filters():
    app = Flask(__name__)
    app.register_blueprint(routes.ecology_bp, url_prefix="/ecology")
    with app.test_request_context("/?start_year=2024&end_year=2031&view_year=2024&rounding_digits=1"):
        response = routes.calculation_summary_index.__wrapped__()
    assert "/ecology/calculation_summary/vsego/toplivo/" in response.location
    assert "view_year=2024" in response.location
    assert "rounding_digits=1" in response.location


@pytest.mark.parametrize("territory,tab", [("invalid", "operating"), ("vsego", "invalid")])
def test_unknown_summary_is_not_found(monkeypatch, territory, tab):
    from werkzeug.exceptions import NotFound

    with Flask(__name__).test_request_context("/"):
        with pytest.raises(NotFound):
            routes.calculation_summary.__wrapped__(territory, tab)
