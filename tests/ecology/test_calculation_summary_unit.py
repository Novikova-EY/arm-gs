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


def test_fuel_exchange_source_separates_territory_affiliation_data(summary_data, monkeypatch):
    from app.ecology.services import fuel_summary_services

    def bucket(amount):
        value = Decimal(amount)
        return {"gaz_prir": value, "gaz": value, "b": value, "e": value * 1000, "q": value}

    inputs = {2026: {
        "vsego::all": bucket("2"),
        "vsego::minen": bucket("0.4"),
        "vsego::prompred": bucket("1.6"),
        "centr::all": bucket("1.5"),
        "centr::minen": bucket("0.5"),
        "centr::prompred": bucket("1"),
    }}
    monkeypatch.setattr(fuel_summary_services, "build_fuel_summary", lambda years: (
        {"operating": inputs}, {"operating": []},
    ))
    context = operating.build_operating_tes_table_context(
        "vsego", "toplivo", view_year=2026, fuel_source=True,
        show_affiliation_columns=True,
    )

    row = next(row for row in context["rows"] if row["key"] == "gaz_prir")
    assert [column["affiliation"] for column in context["value_columns"][:3]] == [
        "all", "minen", "prompred",
    ]
    assert row["col_values_raw"]["vsego:2026:all"] == "2"
    assert row["col_values_raw"]["vsego:2026:minen"] == "0.4"
    assert row["col_values_raw"]["vsego:2026:prompred"] == "1.6"
    assert row["col_values_raw"]["centr:2026:all"] == "1.5"
    assert row["col_values_raw"]["centr:2026:minen"] == "0.5"
    assert row["col_values_raw"]["centr:2026:prompred"] == "1"


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


def test_fuel_affiliation_columns_do_not_repeat_legacy_total(summary_data):
    context = operating.build_operating_tes_table_context(
        "vsego", "toplivo", view_year=2026, show_affiliation_columns=True,
    )
    row = next(row for row in context["rows"] if row["key"] == "gaz_prir")
    assert row["col_values_raw"]["vsego:2026:all"] == "1.04"
    assert row["col_values_raw"]["vsego:2026:minen"] == ""
    assert row["col_values_raw"]["vsego:2026:prompred"] == ""
    assert row["col_values_raw"]["centr:2026:minen"] == ""
    assert row["col_values_raw"]["centr:2026:prompred"] == ""


def test_fuel_summary_includes_territory_and_affiliation_slices(summary_data, monkeypatch):
    def bucket(amount):
        value = Decimal(amount)
        return {"gaz_prir": value, "gaz": value, "b": value, "e": value * 1000, "q": value}

    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        year: {
            "vsego::all": bucket("1.04"),
            "vsego::minen": bucket("0.4"),
            "vsego::prompred": bucket("0.6"),
            "centr::all": bucket("0.7"),
            "centr::minen": bucket("0.2"),
            "centr::prompred": bucket("0.5"),
        }
        for year in years
    })
    context = operating.build_operating_tes_table_context(
        "vsego", "toplivo", view_year=2026, show_affiliation_columns=True,
    )

    assert context["show_affiliation_columns"] is True
    assert [item["slug"] for item in context["affiliation_columns"]] == ["all", "minen", "prompred"]
    territory_slugs = {item["slug"] for item in context["territory_columns"]}
    assert not territory_slugs.intersection({"minen", "prompred"})
    assert {"vsego", "centr", "norilsk", "isolated-dv"} <= territory_slugs
    assert {column["territory_slug"] for column in context["value_columns"]} >= {"vsego", "centr"}
    row = next(row for row in context["rows"] if row["key"] == "gaz_prir")
    assert Decimal(row["col_values_raw"]["vsego:2026:all"]) == Decimal("1.04")
    assert Decimal(row["col_values_raw"]["vsego:2026:minen"]) == Decimal("0.4")
    assert Decimal(row["col_values_raw"]["vsego:2026:prompred"]) == Decimal("0.6")
    assert Decimal(row["col_values_raw"]["centr:2026:all"]) == Decimal("0.7")
    assert Decimal(row["col_values_raw"]["centr:2026:minen"]) == Decimal("0.2")
    assert Decimal(row["col_values_raw"]["centr:2026:prompred"]) == Decimal("0.5")


def test_russia_summary_includes_affiliation_columns_without_losing_new_tes_total(summary_data, monkeypatch):
    load_inputs = exchange.load_accepted_fuel_inputs

    def inputs_with_affiliations(years, scope="operating"):
        loaded = load_inputs(years)
        if scope == "operating":
            for year in years:
                loaded[year]["vsego::minen"] = {"gaz_prir": Decimal("0.4"), "gaz": Decimal("0.4")}
                loaded[year]["vsego::prompred"] = {"gaz_prir": Decimal("0.6"), "gaz": Decimal("0.6")}
        return loaded

    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", inputs_with_affiliations)
    context = summary.build_calculation_summary_context(
        "vsego", "russia", view_year=2026, include_affiliation_columns=True,
    )
    assert context["show_affiliation_columns"] is True
    assert [item["slug"] for item in context["affiliation_columns"]] == ["all", "minen", "prompred"]
    assert [column["affiliation"] for column in context["value_columns"][:3]] == [
        "all", "minen", "prompred",
    ]
    total = next(row for row in context["rows"] if row["key"] == "co2")
    assert Decimal(total["col_values_raw"]["vsego:2026:all"]) == Decimal("6.12") * Decimal("1.59")
    assert Decimal(total["col_values_raw"]["vsego:2026:minen"]) == Decimal("0.4") * Decimal("1.59")
    assert Decimal(total["col_values_raw"]["vsego:2026:prompred"]) == Decimal("0.6") * Decimal("1.59")
    new_tes_row = next(row for row in context["summary_volume_tables"][1]["rows"] if row["key"] == "co2")
    assert new_tes_row["col_values_raw"]["vsego:2026:all"]
    assert new_tes_row["col_values_raw"]["vsego:2026:minen"] == ""
    assert new_tes_row["col_values_raw"]["vsego:2026:prompred"] == ""


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
    assert not russia["specific_emission_tables"]
    tables = russia["summary_volume_tables"]
    assert [table["key"] for table in tables] == ["operating", "new-gt100", "new-le100"]
    assert tables[0]["rows"] == source["rows"]
    for table, fuel in zip(tables[1:], (Decimal("3.04"), Decimal("2.04"))):
        category = {**russia, "rows": table["rows"]}
        assert cell(category, "nox") == fuel * Decimal("1.26") / 1000
        assert cell(category, "co2") == fuel * Decimal("1.59")
        assert cell(category, "co2", "yug") is None
    assert cell({**russia, "rows": tables[1]["rows"]}, "co2", "centr") is None
    assert cell({**russia, "rows": tables[2]["rows"]}, "co2", "centr") == Decimal("4.04") * Decimal("1.59")
    for spec in summary.VOLUME_ROWS:
        assert cell(russia, spec["key"]) == sum(
            cell({**russia, "rows": table["rows"]}, spec["key"]) or 0 for table in tables
        )


@pytest.mark.parametrize("tab", [tab["slug"] for tab in summary.CALCULATION_SUMMARY_TABS])
def test_all_tabs_render_and_keep_filters(summary_data, tab):
    context = summary.build_calculation_summary_context(
        "vsego", tab, start_year=2026, end_year=2027, view_year=2026, rounding_digits=2,
            specific_rounding_digits=3, include_affiliation_columns=tab == "russia",
    )
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(Path("app/templates")),
    ]))
    env.globals["get_reference_years"] = lambda: [2026, 2027]
    context["url_for"] = lambda endpoint, **values: "/" + endpoint + "?" + urlencode({
        key: value for key, value in values.items() if value is not None
    })
    with Flask(__name__).test_request_context("/?rounding_digits=2"):
        html = env.get_template("ecology/operating_tes/operating_tes_table.html").render(
            **context, request=request, current_user=SimpleNamespace(is_authenticated=True), csrf_token="test",
        )
    anchor_pattern = r'<a href="([^"]+)"\s+class="([^"]+)"([^>]*)>\s*([^<]+?)\s*</a>'
    main_nav = html.split('aria-label="Листы расчета">', 1)[1].split("</div>", 1)[0]
    main_links = re.findall(anchor_pattern, main_nav)
    assert [link[3] for link in main_links] == [
        "Данные по модулю Топливо", "Объемы выбросов по России", "Удельные выбросы по России",
        "Динамика изменения выбросов",
        "Динамика изменения удельных выбросов",
    ]
    active_parent = tab
    for href, classes, _, _ in main_links:
        target = parse_qs(urlsplit(unescape(href)).query)["sheet_slug"][0]
        assert ("btn-primary" in classes.split()) == (target == active_parent)
    assert 'aria-label="Объемы выбросов для новых ТЭС">' not in html
    for href, _, _, _ in main_links:
        params = parse_qs(urlsplit(unescape(href)).query)
        if not context.get("dynamics_territories"):
            assert params["view_year"] == ["2026"]
        assert params["start_year"] == ["2026"]
        assert params["end_year"] == ["2027"]
        assert params["rounding_digits"] == ["2"]
        if "specific_rounding_digits" in context:
            assert params["specific_rounding_digits"] == ["3"]
    if context.get("dynamics_territories"):
        assert 'aria-label="Годы периода"' not in html
        subnav = html.split('aria-label="Территории динамики выбросов">', 1)[1].split("</div>", 1)[0]
        sublinks = re.findall(anchor_pattern, subnav)
        assert [link[3] for link in sublinks] == [col["sheet_name"] for col in context["dynamics_territories"]]
        for (href, classes, attrs, _), territory in zip(sublinks, context["dynamics_territories"]):
            params = parse_qs(urlsplit(unescape(href)).query)
            assert params["territory_slug"] == [territory["slug"]]
            assert params["sheet_slug"] == [tab]
            assert params["specific_rounding_digits"] == ["3"]
            assert params["start_year"] == ["2026"]
            assert params["end_year"] == ["2027"]
            assert params["rounding_digits"] == ["2"]
            assert ("btn-primary" in classes.split()) == (territory["slug"] == "vsego")
            assert ('aria-current="page"' in attrs) == (territory["slug"] == "vsego")
    else:
        link = html.split('title="Показать данные за 2027 год"')[0].rsplit('href="', 1)[1]
        assert "view_year=2027" in link
        assert "start_year=2026" in link
        assert "end_year=2027" in link
        assert "rounding_digits=2" in link
        assert f"sheet_slug={tab}" in link
    assert 'data-can-edit="0"' in html
    assert 'class="form-control form-control-sm ot-edit-value"' not in html
    if context.get("dynamics_territories"):
        assert 'id="otTerritoryFilterMenu"' not in html
        for table_html in html.split("<table")[1:]:
            header = table_html.split("</thead>", 1)[0]
            assert re.findall(r'<th class="text-center align-middle ot-terr-col">(.*?)</th>', header) == ["2026", "2027"]
    else:
        assert html.count('id="otTerritoryFilterMenu"') == 1
        assert 'data-storage-key="ecology.calculation_summary.territories"' in html
        filter_script_url = context["url_for"]("static", filename="js/ecology/tes_territory_filter.js")
        assert html.count(f'<script src="{filter_script_url}"></script>') == 1
        for table_html in html.split("<table")[1:]:
            header = table_html.split("</thead>", 1)[0]
            assert header.count("data-territory-filter-button") == 1
            assert 'aria-controls="otTerritoryFilterMenu"' in header
    if tab in {"russia", "dynamics"}:
        assert html.count("<table") == 4
        if tab == "russia":
            assert context["show_affiliation_columns"] is True
            assert "Станции отрасли" in html
            assert re.search(
                r'<th class="text-center align-middle ot-terr-col">Пром<wbr>предприятия</th>', html,
            )
            assert re.search(r'<th colspan="3"[^>]*>Россия</th>', html)
            assert re.search(
                r'<input type="checkbox" value="vsego" data-territory-option checked>\s*Россия',
                html,
            )
            assert "--ot-label-col-w: 14rem;" in html
            assert "table.style.width = '100%'" in html
        titles = re.findall(r'<h2\b[^>]*>\s*(.*?)\s*</h2>', html)
        expected_titles = ["Всего", "Действующие ТЭС", "Новые ТЭС – 100 МВт и более", "Новые ТЭС – менее 100 МВт"]
        assert titles == (expected_titles if tab == "russia" else expected_titles[1:])
        if tab == "dynamics":
            assert context.get("main_table_title") is None
        assert 'id="ot-specific-' not in html
        for table in context["summary_volume_tables"]:
            assert f'id="ot-summary-{table["key"]}"' in html
    elif tab in {"specific", "dynamics-specific"}:
        assert html.count("<table") == 3
        if tab == "specific":
            assert context["page_title"] == "Удельные выбросы ЗВ и ПГ"
        if tab == "dynamics-specific":
            assert context.get("main_table_title") is None
            assert not re.search(r'<h2\b[^>]*>\s*Всего\s*</h2>', html)
        assert 'id="rounding_digits"' not in html
        assert html.count('id="specific_rounding_digits"') == 1
        controls = html.split('class="d-flex align-items-center gap-2 flex-shrink-0 ms-auto"', 1)[1].split("</div>", 1)[0]
        assert 'id="specific_rounding_digits"' in controls
        assert 'id="operatingTesTable"' not in html
        assert 'id="ot-summary-' not in html
        for table in context["specific_emission_tables"]:
            assert table["title"] in html
            assert f'id="ot-specific-{table["key"]}"' in html


@pytest.mark.parametrize("territory", ["vsego", "centr", "yug"])
def test_dynamics_preserves_each_year_and_category(summary_data, territory):
    context = summary.build_calculation_summary_context(
        territory, "dynamics", start_year=2026, end_year=2027, view_year=2027, rounding_digits=1,
    )
    assert [col["year"] for col in context["value_columns"]] == [2026, 2027]
    assert all(col["territory_slug"] == territory for col in context["value_columns"])
    assert context["year_columns_mode"] is True
    assert context["can_edit"] is False
    assert context["page_title"] == (
        "Динамика ожидаемых объемов выбросов вредных веществ и парниковых газов в атмосферу, тыс. т"
    )
    assert not context["specific_emission_tables"]
    for year in (2026, 2027):
        annual = summary.build_calculation_summary_context(territory, "russia", view_year=year, rounding_digits=1)
        assert context["dynamics_territories"] == annual["territory_columns"]
        for actual_table, expected_table in zip(
            [context, *context["summary_volume_tables"]], [annual, *annual["summary_volume_tables"]],
        ):
            for actual, expected in zip(actual_table["rows"], expected_table["rows"]):
                slug = f"{territory}:{year}"
                assert actual["key"] == expected["key"]
                assert actual["unit"] == expected["unit"]
                assert actual["col_values_raw"][slug] == expected["col_values_raw"][slug]
                assert actual["col_values"][slug] == expected["col_values"][slug]
    row = next(row for row in context["rows"] if row["key"] == "co2")
    if territory == "yug":
        assert row["is_empty"] is True
    else:
        assert Decimal(row["col_values_raw"][f"{territory}:2027"]) == 2 * Decimal(row["col_values_raw"][f"{territory}:2026"])


def test_dynamics_uses_selected_range_and_keeps_rows_with_later_data(summary_data, monkeypatch):
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        year: {"vsego": {"gaz_prir": Decimal("1"), "gaz": Decimal("1")}}
        for year in years if year == 2027
    })
    monkeypatch.setattr(new, "load_accepted_new_tes_fuel_inputs", lambda years: {})
    context = summary.build_calculation_summary_context("vsego", "dynamics", view_year=2026)
    row = next(row for row in context["rows"] if row["key"] == "co2")
    assert row["col_values_raw"]["vsego:2026"] == ""
    assert Decimal(row["col_values_raw"]["vsego:2027"]) > 0
    assert row["is_empty"] is False

    for module in (new, operating):
        monkeypatch.setattr(module, "get_year_columns", lambda start, end: list(range(int(start), int(end) + 1)))
    context = summary.build_calculation_summary_context(
        "vsego", "dynamics", start_year=2027, end_year=2027, view_year=2026,
    )
    assert [col["year"] for col in context["value_columns"]] == [2027]
    assert context["start_year"] == context["end_year"] == 2027
    assert all(list(row["col_values_raw"]) == ["vsego:2027"] for row in context["rows"])


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
    context = summary.build_calculation_summary_context("vsego", "specific", view_year=year, rounding_digits=digits)
    fuel_context = summary.build_calculation_summary_context("vsego", "toplivo", view_year=year, rounding_digits=digits)
    tables = context["specific_emission_tables"]
    assert [table["key"] for table in tables] == ["energy", "energy_fuel", "fuel"]
    assert cell(context, "co") > 0
    for table in tables[:2]:
        co_row = next(row for row in table["rows"] if row["key"] == "co")
        assert co_row["formula_tooltip"].startswith(f'{table["formula"]}.')
        assert "/ 1000" not in co_row["formula_tooltip"]
    for territory in ("vsego", "centr"):
        electricity = cell(fuel_context, "ee_generation", territory)
        brought_energy = electricity + cell(fuel_context, "heat_output", territory) / Decimal("859.8")
        fuel = cell(fuel_context, "b", territory)
        solid_fuel = sum(cell(fuel_context, key, territory) for key in ("mazut", "torf", "tvproch", "ugol"))
        for spec in summary.VOLUME_ROWS:
            key = spec["key"]
            mass = cell(context, key, territory)
            energy_mass = mass
            if key == "pollutants_total":
                energy_mass = sum(cell(context, item, territory) for item in ("ash", "so2", "nox", "co"))
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


@pytest.mark.parametrize("key", ["energy", "energy_fuel", "fuel"])
@pytest.mark.parametrize("territory", ["vsego", "centr", "yug"])
@pytest.mark.parametrize("digits", [0, -1, 3])
def test_specific_dynamics_matches_annual_tables(russia_specific_data, key, territory, digits):
    context = summary.build_calculation_summary_context(
        territory, "dynamics-specific", start_year=2026, end_year=2027, view_year=2027,
        rounding_digits=1, specific_rounding_digits=digits,
    )
    assert context["year_columns_mode"] is True
    assert context["can_edit"] is False
    assert context["specific_emissions_only"] is True
    assert context["page_title"] == "Динамика изменения удельных выбросов"
    assert context["territory_filter_storage_key"] is None
    assert not context.get("summary_volume_tables")
    assert [col["slug"] for col in context["value_columns"]] == [f"{territory}:2026", f"{territory}:2027"]
    assert [table["key"] for table in context["specific_emission_tables"]] == ["energy", "energy_fuel", "fuel"]
    table = next(table for table in context["specific_emission_tables"] if table["key"] == key)
    for year in (2026, 2027):
        annual = summary.build_calculation_summary_context(
            territory, "specific", view_year=year, rounding_digits=1, specific_rounding_digits=digits,
        )
        expected = next(table for table in annual["specific_emission_tables"] if table["key"] == key)
        assert table["title"] == expected["title"]
        assert table["formula"] == expected["formula"]
        assert context["dynamics_territories"] == annual["territory_columns"]
        for row, source in zip(table["rows"], expected["rows"]):
            slug = f"{territory}:{year}"
            assert row["key"] == source["key"]
            assert row["col_values_raw"][slug] == source["col_values_raw"][slug]
            assert row["col_values"][slug] == source["col_values"][slug]
            assert row["formula_tooltip"] == source["formula_tooltip"]
            assert row["formula_tooltip_html"] == source["formula_tooltip_html"]
    co2 = next(row for row in table["rows"] if row["key"] == "co2")
    assert co2["is_empty"] == (territory == "yug")
    if territory == "yug":
        assert all(row["is_empty"] for row in table["rows"])


def test_specific_dynamics_selected_range_and_missing_denominators(summary_data, monkeypatch):
    def bucket(year):
        return {
            "gaz_prir": Decimal("10"), "gaz": Decimal("10"),
            "b": Decimal("0") if year == 2026 else Decimal("10"),
            "e": Decimal("0") if year == 2026 else Decimal("1000"),
            "q": Decimal("0"),
        }

    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        year: {"vsego": bucket(year)} for year in years
    })
    monkeypatch.setattr(new, "load_accepted_new_tes_fuel_inputs", lambda years: {})
    for module in (new, operating):
        monkeypatch.setattr(module, "get_year_columns", lambda start, end: list(range(int(start), int(end) + 1)))
    context = summary.build_calculation_summary_context(
        "vsego", "dynamics-specific", start_year=2026, end_year=2031, view_year=2026,
        rounding_digits=1, coefficient_rounding_digits=0,
    )
    assert [col["year"] for col in context["value_columns"]] == list(range(2026, 2032))
    assert len(context["specific_emission_tables"]) == 3
    for table in context["specific_emission_tables"]:
        row = next(row for row in table["rows"] if row["key"] == "co2")
        assert row["col_values_raw"]["vsego:2026"] == ""
        assert row["col_values"]["vsego:2026"] == "–"
        assert Decimal(row["col_values_raw"]["vsego:2031"]) > 0
        assert row["is_empty"] is False
    single = summary.build_calculation_summary_context(
        "vsego", "dynamics-specific", start_year=2027, end_year=2027, view_year=2026,
    )
    assert [col["year"] for col in single["value_columns"]] == [2027]


@pytest.mark.parametrize("selection,expected_digits", [
    ("0", 0), ("-1", -1), ("1", 1), ("2", 2), ("3", 3),
    (None, 1), ("", 1), ("invalid", operating.ROUNDING_DIGITS),
])
def test_specific_rounding_from_request_preserves_raw_values(
    russia_specific_data, monkeypatch, selection, expected_digits,
):
    baseline = summary.build_calculation_summary_context(
        "vsego", "specific", view_year=2026, rounding_digits=1,
    )
    monkeypatch.setattr(routes, "render_template", lambda template, **context: context)
    monkeypatch.setattr(routes, "log_page_visit", lambda *args, **kwargs: None)
    params = {
        "start_year": 2026, "end_year": 2027, "view_year": 2026,
        "rounding_digits": 1, "coefficient_rounding_digits": 0,
    }
    if selection is not None:
        params["specific_rounding_digits"] = selection
    with Flask(__name__).test_request_context("/?" + urlencode(params)):
        context = routes.calculation_summary.__wrapped__("vsego", "specific")
    assert context["specific_rounding_digits"] == expected_digits
    assert context["rounding_digits"] == 1
    assert context["rows"] == baseline["rows"]
    changed = False
    for table, original in zip(context["specific_emission_tables"], baseline["specific_emission_tables"]):
        for row, original_row in zip(table["rows"], original["rows"]):
            assert row["col_values_raw"] == original_row["col_values_raw"]
            for column, raw in row["col_values_raw"].items():
                value = Decimal(raw) if raw else None
                assert row["col_values"][column] == operating.format_cell(value, expected_digits)
            changed |= row["col_values"] != original_row["col_values"]
    if expected_digits != 1:
        assert changed


@pytest.mark.parametrize("denominator", [None, Decimal("0")])
def test_russia_specific_emissions_without_denominators_are_empty(summary_data, monkeypatch, denominator):
    bucket = {"gaz_prir": Decimal("10"), "gaz": Decimal("10")}
    if denominator is not None:
        bucket.update({key: denominator for key in ("b", "e", "q")})
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {year: {"vsego": dict(bucket)} for year in years})
    monkeypatch.setattr(new, "load_accepted_new_tes_fuel_inputs", lambda years: {
        year: {"vsego": {"le100": dict(bucket), "gt100": dict(bucket)}} for year in years
    })
    context = summary.build_calculation_summary_context("vsego", "specific", view_year=2026)
    assert cell(context, "co2") > 0
    for table in context["specific_emission_tables"]:
        for row in table["rows"]:
            assert row["col_values_raw"]["vsego:2026"] == ""
            assert row["col_values"]["vsego:2026"] == "–"


def test_russia_route_requests_affiliation_subcolumns(summary_data, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        routes, "build_calculation_summary_context",
        lambda *args, **kwargs: captured.update(kwargs) or {
            "sheet": {"sheet_name": "Объемы выбросов по России"},
            "territory": {"sheet_name": "Всего"},
            "start_year": 2026, "end_year": 2031, "view_year": 2026,
        },
    )
    monkeypatch.setattr(routes, "log_page_visit", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "render_template", lambda *args, **kwargs: "page")
    with Flask(__name__).test_request_context("/?start_year=2026&end_year=2031"):
        assert routes.calculation_summary.__wrapped__("vsego", "russia") == "page"
    assert captured["include_affiliation_columns"] is True


def test_operating_tes_fuel_route_requests_affiliation_subcolumns(monkeypatch):
    from types import SimpleNamespace
    from app.ecology.routes import operating_tes_routes as operating_routes
    from app.ecology.services import fuel_exchange_services

    captured = {}
    monkeypatch.setattr(
        operating_routes, "build_operating_tes_table_context",
        lambda *args, **kwargs: captured.update(kwargs) or {
            "sheet": {"layout": "fuel", "slug": "toplivo"},
            "range_years": [2026], "view_year": 2026,
        },
    )
    monkeypatch.setattr(operating_routes, "log_page_visit", lambda *args, **kwargs: None)
    monkeypatch.setattr(operating_routes, "can_edit_ecology", lambda user: False)
    monkeypatch.setattr(operating_routes, "current_user", SimpleNamespace())
    monkeypatch.setattr(fuel_exchange_services, "pending_submissions", lambda years: [])
    monkeypatch.setattr(operating_routes, "render_template", lambda *args, **kwargs: "page")
    with Flask(__name__).test_request_context("/"):
        assert operating_routes.operating_tes_table.__wrapped__("vsego", "toplivo") == "page"
    assert captured["show_affiliation_columns"] is True


def test_fuel_ecology_summary_route_requests_affiliation_subcolumns(monkeypatch):
    from types import SimpleNamespace
    from app.fuel.routes import ecology_summary_routes as fuel_routes

    captured = {}
    monkeypatch.setattr(
        fuel_routes, "build_operating_tes_table_context",
        lambda *args, **kwargs: captured.update(kwargs) or {
            "view_year": 2026, "range_years": [2026], "start_year": 2026,
            "end_year": 2026, "rounding_digits": 1,
        },
    )
    monkeypatch.setattr(fuel_routes, "current_user", SimpleNamespace(has_admin=False))
    monkeypatch.setattr(fuel_routes, "render_template", lambda *args, **kwargs: "page")
    with Flask(__name__).test_request_context("/"):
        assert fuel_routes.ecology_summary.__wrapped__() == "page"
    assert captured["fuel_source"] is True
    assert captured["show_affiliation_columns"] is True



def test_index_keeps_selected_filters():
    app = Flask(__name__)
    app.register_blueprint(routes.ecology_bp, url_prefix="/ecology")
    with app.test_request_context("/?start_year=2024&end_year=2031&view_year=2024&rounding_digits=1"):
        response = routes.calculation_summary_index.__wrapped__()
    assert "/ecology/calculation_summary/vsego/russia/" in response.location
    assert "view_year=2024" in response.location
    assert "rounding_digits=1" in response.location


@pytest.mark.parametrize("territory,tab", [("invalid", "operating"), ("vsego", "invalid")])
def test_unknown_summary_is_not_found(monkeypatch, territory, tab):
    from werkzeug.exceptions import NotFound

    with Flask(__name__).test_request_context("/"):
        with pytest.raises(NotFound):
            routes.calculation_summary.__wrapped__(territory, tab)


@pytest.mark.parametrize("section,tab,expected", [
    ("operating", "toplivo", 1), ("operating", "khar-topl", 1),
    ("operating", "koeff", 1), ("operating", "zola", 1),
    ("operating", "sera", 1), ("operating", "azot", 1),
    ("operating", "co", 1), ("operating", "pg", 1),
    ("operating", "pg-tj", 1), ("operating", "obemy", 0),
    ("new", "toplivo", 1), ("new", "spravochnik", 2), ("new", "obemy", 1),
    ("summary", "toplivo", 1), ("summary", "russia", 0),
    ("summary", "new-le100", 1), ("summary", "new-gt100", 1),
    ("summary", "specific", 0), ("summary", "dynamics", 0),
    ("summary", "dynamics-specific", 0),
])
def test_fuel_filter_only_on_tables_with_fuel_rows(summary_data, section, tab, expected):
    builders = {
        "operating": operating.build_operating_tes_table_context,
        "new": new.build_new_tes_table_context,
        "summary": summary.build_calculation_summary_context,
    }
    context = builders[section]("vsego", tab, start_year=2026, end_year=2027, view_year=2026)
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(Path("app/templates")),
    ]))
    env.globals["get_reference_years"] = lambda: [2026, 2027]
    context["url_for"] = lambda endpoint, **values: "/" + endpoint + "?" + urlencode({
        key: value for key, value in values.items() if value is not None
    })
    with Flask(__name__).test_request_context("/"):
        html = env.get_template("ecology/operating_tes/operating_tes_table.html").render(
            **context, request=request, current_user=SimpleNamespace(is_authenticated=True), csrf_token="test",
        )
    assert html.count("data-fuel-filter-button") == expected
    assert html.count('id="otFuelFilterMenu"') == 1
    script_url = context["url_for"]("static", filename="js/ecology/tes_territory_filter.js")
    assert html.count(f'<script src="{script_url}"></script>') == 1
    for table_html in html.split("<table")[1:]:
        if "data-fuel-filter-button" in table_html.split("</thead>", 1)[0]:
            assert 'data-row-key="' in table_html
