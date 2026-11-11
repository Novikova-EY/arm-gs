"""Год ячейки определяется столбцом, а не прежним параметром view_year."""
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask, request
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
from types import SimpleNamespace
import pytest

from app.ecology.services import fuel_exchange_services as exchange
from app.ecology.services import operating_tes_page_services as services


class TableParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inputs = []
        self.headers = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))
        elif tag == "th":
            self.headers.append(dict(attrs))


def render_range_html(context):
    env = Environment(loader=FileSystemLoader(Path(__file__).parents[2] / "app" / "templates"))
    return env.get_template("ecology/operating_tes/_range_table.html").render(**context, can_edit=True)


def render_range(context):
    return TableParser(render_range_html(context))


@pytest.fixture
def year_range(monkeypatch):
    monkeypatch.setattr(services, "get_filter_year_list", lambda: [2025, 2026, 2027, 2028])
    monkeypatch.setattr(services, "get_sipr_start_year", lambda: 2026)
    monkeypatch.setattr(services, "get_sipr_end_year", lambda: 2027)
    monkeypatch.setattr(services, "get_year_feature_dict", lambda: {2026: "план", 2027: "план"})
    monkeypatch.setattr(services, "ensure_default_persisted_rows", lambda years: None)
    monkeypatch.setattr(services, "load_input_overrides", lambda years: {})
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", "gas_natural", 2026): {"k_co2": Decimal("2")},
        ("vsego", "gas_natural", 2027): {"k_co2": Decimal("3")},
        ("centr", "gas_natural", 2027): {"k_co2": Decimal("4")},
    })
    monkeypatch.setattr(services, "load_coefficient_overrides", lambda years, affiliation="all": {})
    inputs = {
        2026: {"vsego": {"gaz_prir": Decimal("10")}},
        2027: {"vsego": {"gaz_prir": Decimal("20")}, "centr": {"gaz_prir": Decimal("30")}},
    }
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {year: inputs.get(year, {}) for year in years})
    monkeypatch.setattr(services, "get_fuel_module_consumption_row_specs", lambda: [
        {"key": "gaz_prir", "label": "Природный газ", "kind": "value"},
    ])


@pytest.mark.parametrize("selected_year,expected_year", [
    (2026, 2026), (2027, 2027), (2025, 2026), (None, 2026),
])
def test_volumes_use_year_buttons_and_selected_year_data(year_range, selected_year, expected_year):
    from urllib.parse import parse_qs, urlsplit

    context = services.build_operating_tes_table_context(
        "vsego", "obemy", 2026, 2027, view_year=selected_year,
    )
    assert context["years"] == [expected_year]
    assert context["range_years"] == [2026, 2027]
    assert context["year_columns_mode"] is False
    assert {column["year"] for column in context["value_columns"]} == {expected_year}
    row = next(row for row in context["rows"] if row["key"] == "co2")
    assert Decimal(row["col_values_raw"][f"vsego:{expected_year}"]) == (20 if expected_year == 2026 else 60)
    if expected_year == 2026:
        assert row["col_values_raw"]["centr:2026"] == ""
    else:
        assert Decimal(row["col_values_raw"]["centr:2027"]) == 90
    assert row["is_empty"] is False
    html = render_page(context)
    before_table, table_html = html.split('<table', 1)
    assert 'aria-label="Годы периода"' in before_table
    active_year = before_table.split('aria-current="true"', 1)[1].split('</span', 1)[0]
    assert active_year.split('>', 1)[1].strip() == f"{expected_year} (план)"
    other_year = 2027 if expected_year == 2026 else 2026
    target_link = before_table.split(f'title="Показать данные за {other_year} год"')[0].rsplit('href="', 1)[1].split('"')[0]
    query = parse_qs(urlsplit(target_link).query)
    assert query["view_year"] == [str(other_year)]
    assert query["start_year"] == ["2026"]
    assert query["end_year"] == ["2027"]
    assert query["rounding_digits"] == ["1"]
    thead = table_html.split('<thead')[1].split('</thead>')[0]
    assert thead.count('<tr') == 1
    assert 'ot-year-col' not in thead
    rendered_row = table_html.split('data-row-key="co2"')[1].split('</tr>')[0]
    cells = rendered_row.split('<td')[2:]
    assert len(cells) == len(context["territory_columns"])
    assert cells[0].split('>', 1)[1].split('</td>')[0].strip() == ("20" if expected_year == 2026 else "60")


def test_operating_volumes_show_affiliations_as_filtered_subcolumns(year_range, monkeypatch):
    accepted = {
        2026: {
            "vsego": {"gaz_prir": Decimal("10")},
            "vsego::minen": {"gaz_prir": Decimal("5")},
            "vsego::prompred": {"gaz_prir": Decimal("2")},
            "centr": {"gaz_prir": Decimal("3")},
            "centr::minen": {"gaz_prir": Decimal("4")},
            "centr::prompred": {"gaz_prir": Decimal("6")},
        },
    }
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        year: accepted.get(year, {}) for year in years
    })
    context = services.build_operating_tes_table_context(
        "vsego", "obemy", 2026, 2026, view_year=2026,
        show_affiliation_columns=True,
    )

    expected_affiliations = ["all", "minen", "prompred"]
    assert [column["slug"] for column in context["affiliation_columns"]] == expected_affiliations
    assert [column["affiliation"] for column in context["value_columns"][:3]] == expected_affiliations
    row = next(row for row in context["rows"] if row["key"] == "co2")
    assert [Decimal(row["col_values_raw"][f"vsego:2026:{slug}"]) for slug in expected_affiliations] == [20, 10, 4]
    assert [Decimal(row["col_values_raw"][f"centr:2026:{slug}"]) for slug in expected_affiliations] == [6, 8, 12]

    context["value_columns"][0]["affiliation_label"] = "Все принадлежности"
    html = render_page(context)
    before_table, table_html = html.split("<table", 1)
    assert 'aria-label="Принадлежность данных"' not in before_table
    assert 'data-storage-key="ecology.operating_tes.territories"' in html
    assert 'data-territory-filter-button' in table_html
    thead = table_html.split("<thead", 1)[1].split("</thead>", 1)[0]
    assert thead.count("<tr") == 2
    assert "ot-affiliation-volume-table" in table_html
    assert "ot-uniform-value-columns" in table_html
    assert "--ot-value-col-width: 8.5rem" in html
    table_css = html.rsplit(".ot-calculation-table.ot-affiliation-volume-table td.ot-year-cell", 1)[1].split("}", 1)[0]
    assert "white-space: nowrap" in table_css
    assert "overflow: visible" in table_css
    assert "Всего" in thead
    assert "Станции отрасли" in thead
    assert '<th class="text-center align-middle ot-terr-col">Пром<wbr>предприятия</th>' in thead
    subheaders = thead.split("<tr", 2)[2].split("</tr>", 1)[0]
    assert "Всего" in subheaders
    assert "Все принадлежности" not in subheaders


def test_legacy_volumes_snapshot_does_not_repeat_totals_as_affiliation_slices(year_range, monkeypatch):
    accepted = {
        2026: {
            "vsego": {"gaz_prir": Decimal("10")},
            "minen": {"gaz_prir": Decimal("5")},
            "prompred": {"gaz_prir": Decimal("2")},
            "centr": {"gaz_prir": Decimal("3")},
        },
    }
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        year: accepted.get(year, {}) for year in years
    })
    context = services.build_operating_tes_table_context(
        "vsego", "obemy", 2026, 2026, view_year=2026,
        show_affiliation_columns=True,
    )
    row = next(row for row in context["rows"] if row["key"] == "co2")

    assert row["col_values_raw"]["vsego:2026:minen"]
    assert row["col_values_raw"]["vsego:2026:prompred"]
    assert row["col_values_raw"]["centr:2026:minen"] == ""
    assert row["col_values_raw"]["centr:2026:prompred"] == ""
    assert row["col_values"]["centr:2026:minen"] == "–"
    assert row["col_values"]["centr:2026:prompred"] == "–"


@pytest.mark.parametrize("year", [2026, 2027])
@pytest.mark.parametrize(("digits", "specific_digits"), [(1, 3), (3, 1)])
def test_specific_emissions_follow_volume_rows_and_selected_fuel(
    year_range, monkeypatch, year, digits, specific_digits
):
    accepted = {
        y: {
            slug: {key: Decimal(value) * scale for key, value in {
                "b": "200", "e": "100000", "q": "8598", "gaz_prir": "50", "mazut": "10", "maztop": "10",
                "torf": "20", "tvproch": "30", "ugol": "40",
            }.items()}
            for slug, scale in (("vsego", y - 2025), ("centr", (y - 2025) * 3))
        }
        for y in (2026, 2027)
    }
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        y: {slug: dict(bucket) for slug, bucket in accepted[y].items()} for y in years
    })
    context = services.build_operating_tes_table_context(
        "vsego", "obemy", 2026, 2027, digits, view_year=year,
        specific_rounding_digits=specific_digits,
    )
    tables = context["specific_emission_tables"]
    assert len(tables) == 3
    assert tables[0]["title"] == "Удельные выбросы ЗВ и ПГ на единицу приведенной энергии, г/кВт.ч"
    assert "Выработка электроэнергии + Отпуск тепла / 859,8" in tables[0]["rows"][0]["formula_tooltip"]
    assert tables[1]["title"] == "Удельные выбросы ЗВ и ПГ на единицу электрической энергии, г/кВт.ч"
    assert "Выработка электроэнергии" in tables[1]["rows"][0]["formula_tooltip"]
    for table in tables[:2]:
        co_row = next(row for row in table["rows"] if row["key"] == "co")
        assert co_row["formula_tooltip"].startswith(f'{table["formula"]}.')
        assert "/ 1000" not in co_row["formula_tooltip"]
    for slug in ("vsego", "centr"):
        column = f"{slug}:{year}"
        fuel = accepted[year][slug]["b"]
        electricity = accepted[year][slug]["e"] / Decimal("1000")
        brought_energy = electricity + accepted[year][slug]["q"] / Decimal("859.8")
        solid = sum(accepted[year][slug][key] for key in ("mazut", "torf", "tvproch", "ugol"))
        for volume_row in context["rows"]:
            mass = Decimal(volume_row["col_values_raw"][column])
            key = volume_row["key"]
            mass_for_energy = mass
            if key == "pollutants_total":
                component_masses = {
                    row["key"]: Decimal(row["col_values_raw"][column])
                    for row in context["rows"]
                }
                mass_for_energy = sum((component_masses[item] for item in ("ash", "so2", "nox", "co")), Decimal("0"))
            expected = [
                mass_for_energy / brought_energy,
                mass_for_energy / electricity,
                mass * 100 / solid if key in {"ash", "so2"} else mass * 1000 / fuel,
            ]
            for table, value in zip(tables, expected):
                row = next(row for row in table["rows"] if row["key"] == volume_row["key"])
                assert Decimal(row["col_values_raw"][column]) == pytest.approx(value)
                assert row["col_values"][column] == services.format_cell(value, specific_digits)
        for volume_row in context["rows"]:
            value = Decimal(volume_row["col_values_raw"][column])
            assert volume_row["col_values"][column] == services.format_cell(value, digits)
    html = render_page(context)
    assert html.count('<table') == 4
    assert html.count('aria-label="Годы периода"') == 1
    assert html.count('id="rounding_digits"') == 1
    assert html.count('id="specific_rounding_digits"') == 1
    assert html.count('id="otShowEmptyRowsToggle"') == 1
    expected_order = [row["key"] for row in context["rows"]]
    for table in tables:
        assert [row["key"] for row in table["rows"]] == expected_order
        rendered = html.split(f'id="ot-specific-{table["key"]}"', 1)[1].split('</table>', 1)[0]
        assert rendered.count('<tr') == 9  # Заголовок, два разделителя и шесть строк данных.
        assert rendered.count(f'colspan="{len(context["value_columns"]) + 1}"') == 2
        assert 'Вредные вещества' in rendered
        assert 'Парниковые газы' in rendered
        assert 'Всего, в т.ч.' in rendered
        assert 'в т.ч.: твердые частицы' not in rendered
        assert '<input' not in rendered
        assert '<select' not in rendered


@pytest.mark.parametrize("fuel", [None, Decimal("0"), Decimal("100")])
@pytest.mark.parametrize("energy", [None, Decimal("0")])
def test_specific_emissions_do_not_divide_by_missing_energy_or_fuel(year_range, monkeypatch, fuel, energy):
    bucket = {"gaz_prir": Decimal("10"), "b": fuel, "e": energy, "q": energy}
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {2026: {"vsego": bucket}})
    context = services.build_operating_tes_table_context("vsego", "obemy", 2026, 2027)
    for table in context["specific_emission_tables"]:
        rows = {row["key"]: row for row in table["rows"]}
        for row in rows.values():
            assert row["col_values_raw"]["centr:2026"] == ""
            assert row["col_values"]["centr:2026"] == "–"
        if table["key"] in {"energy", "energy_fuel"} or fuel in (None, 0):
            assert rows["co2"]["col_values_raw"]["vsego:2026"] == ""
            assert rows["co2"]["col_values"]["vsego:2026"] == "–"
        else:
            assert Decimal(rows["co2"]["col_values_raw"]["vsego:2026"]) > 0
        if table["key"] == "fuel":
            for key in ("ash", "so2"):
                assert rows[key]["col_values_raw"]["vsego:2026"] == ""
                assert rows[key]["col_values"]["vsego:2026"] == "–"


def test_brought_energy_uses_heat_when_electricity_is_missing(year_range, monkeypatch):
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {2026: {
        "vsego": {"e": Decimal("0"), "q": Decimal("8598"), "b": Decimal("100"), "gaz_prir": Decimal("10")},
    }})
    context = services.build_operating_tes_table_context("vsego", "obemy", 2026, 2027)
    tables = {table["key"]: {row["key"]: row for row in table["rows"]}
              for table in context["specific_emission_tables"]}
    volume = Decimal(next(row for row in context["rows"] if row["key"] == "co2")["col_values_raw"]["vsego:2026"])
    assert Decimal(tables["energy"]["co2"]["col_values_raw"]["vsego:2026"]) == volume / Decimal("10")
    assert tables["energy_fuel"]["co2"]["col_values_raw"]["vsego:2026"] == ""


def test_specific_emissions_keep_zero_emissions_and_missing_mass_distinct(year_range, monkeypatch):
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {2026: {
        "vsego": {"b": Decimal("100"), "e": Decimal("100000"), "q": Decimal("8598"), "gaz_prir": Decimal("10")},
        "centr": {"b": Decimal("100"), "e": Decimal("100000"), "q": Decimal("8598")},

    }})
    monkeypatch.setattr(services, "load_coefficient_overrides", lambda years: {
        ("vsego", 2026, "nox_n"): Decimal("1"),
    })
    context = services.build_operating_tes_table_context("vsego", "obemy", 2026, 2027)
    for table in context["specific_emission_tables"]:
        row = next(row for row in table["rows"] if row["key"] == "nox")
        assert Decimal(row["col_values_raw"]["vsego:2026"]) == 0
        assert row["col_values"]["vsego:2026"] == "0"
        assert row["col_values_raw"]["centr:2026"] == ""
        assert row["col_values"]["centr:2026"] == "–"


@pytest.mark.parametrize("selected_year,expected_year", [
    (2026, 2026), (2027, 2027), (2025, 2026), (None, 2026),
])
@pytest.mark.parametrize("fuel_scope", ["operating", "new_lt100", "new_ge100"])
def test_fuel_summary_shows_and_submits_only_displayed_year(year_range, monkeypatch, selected_year, expected_year, fuel_scope):
    from urllib.parse import parse_qs, urlsplit

    inputs = {2026: {}, 2027: {"centr": {"gaz_prir": Decimal("30")}}}
    from app.ecology.services import fuel_summary_services
    from app.ecology.services.fuel_summary_constants import FUEL_SUMMARY_SCOPES, FUEL_SUMMARY_CRITERIA

    monkeypatch.setattr(fuel_summary_services, "build_fuel_summary", lambda years: (
        {fuel_scope: {year: inputs[year] for year in years}}, {fuel_scope: []},
    ))
    context = services.build_operating_tes_table_context(
        "vsego", "toplivo", 2026, 2027, view_year=selected_year, fuel_source=True, fuel_scope=fuel_scope,
    )
    context.update(table_endpoint="fuel_bp.ecology_summary", fuel_exchange_source=True, can_send=True,
                   fuel_scope=fuel_scope, fuel_summary_scopes=FUEL_SUMMARY_SCOPES,
                   fuel_summary_criteria=FUEL_SUMMARY_CRITERIA)
    assert context["year_columns_mode"] is False
    assert context["years"] == [expected_year]
    assert context["range_years"] == [2026, 2027]
    assert {column["year"] for column in context["value_columns"]} == {expected_year}
    row = next(row for row in context["rows"] if row["key"] == "gaz_prir")
    assert row["col_values_raw"][f"centr:{expected_year}"] == ("30" if expected_year == 2027 else "")
    assert row["is_empty"] is (expected_year == 2026)
    html = render_page(context)
    before_table, table_html = html.split('<table', 1)
    assert 'aria-label="Годы периода"' in before_table
    navigation = before_table.split('aria-label="Категории ТЭС"', 1)[1].split('</nav>', 1)[0]
    assert navigation.count('<a ') == 2
    new_scope = fuel_scope if fuel_scope != "operating" else "new_lt100"
    for scope, label in [("operating", "Действующие ТЭС"), (new_scope, "Новые ТЭС")]:
        button = navigation.split(f'>{label}</a>', 1)[0].rsplit('<a ', 1)[1]
        style = "btn-primary" if scope == fuel_scope else "btn-outline-primary"
        assert f'class="btn {style}' in button
        href = button.split('href="', 1)[1].split('"', 1)[0].replace('&amp;', '&')
        query = parse_qs(urlsplit(href).query)
        assert query["scope"] == [scope]
        assert query["view_year"] == [str(expected_year)]
        assert query["start_year"] == ["2026"]
        assert query["end_year"] == ["2027"]
        assert query["rounding_digits"] == ["1"]
    subnav_marker = 'aria-label="Категории новых ТЭС"'
    assert (subnav_marker in before_table) == (fuel_scope != "operating")
    if fuel_scope != "operating":
        subnav = before_table.split(subnav_marker, 1)[1].split('</nav>', 1)[0]
        assert subnav.count('<a ') == 2
        for scope, label in FUEL_SUMMARY_SCOPES[1:]:
            button = subnav.split(f'>{label}</a>', 1)[0].rsplit('<a ', 1)[1]
            style = "btn-primary" if scope == fuel_scope else "btn-outline-primary"
            assert f'class="btn {style}"' in button
            assert ('aria-current="page"' in button) == (scope == fuel_scope)
            assert f'title="{FUEL_SUMMARY_CRITERIA[scope]}"' in button
            assert 'data-bs-toggle="tooltip"' in button
            href = button.split('href="', 1)[1].split('"', 1)[0].replace('&amp;', '&')
            query = parse_qs(urlsplit(href).query)
            assert query["scope"] == [scope]
            assert query["view_year"] == [str(expected_year)]
            assert query["start_year"] == ["2026"]
            assert query["end_year"] == ["2027"]
            assert query["rounding_digits"] == ["1"]
    active_year = before_table.split('aria-current="true"', 1)[1].split('</span', 1)[0]
    assert str(expected_year) in active_year
    other_year = 2027 if expected_year == 2026 else 2026
    target_link = before_table.split(f'title="Показать данные за {other_year} год"')[0].rsplit('href="', 1)[1].split('"')[0]
    assert target_link.startswith('/fuel_bp.ecology_summary?')
    query = parse_qs(urlsplit(target_link).query)
    assert query["view_year"] == [str(other_year)]
    assert query["start_year"] == ["2026"]
    assert query["end_year"] == ["2027"]
    assert query["rounding_digits"] == ["1"]
    assert 'ot-year-col' not in table_html.split('</thead>', 1)[0]
    assert 'id="fuel_submission_year"' not in html
    submission_form = before_table.split('<form method="POST"', 1)[1].split('</form>', 1)[0]
    assert 'action=' not in submission_form  # POST retains the displayed view_year in the URL.
    assert 'name="year"' not in submission_form
    assert 'fw-bold text-nowrap' in submission_form
    assert f'Передать данные за {expected_year} год' in submission_form


def test_coefficient_editable_cells_keep_their_own_year(year_range):
    context = services.build_operating_tes_table_context("centr", "koeff", 2026, 2027, view_year=2027)
    table = render_range(context)
    assert {field["data-year"] for field in table.inputs} == {"2026", "2027"}
    assert len(table.inputs) == 5 * 2
    assert {field["data-territory"] for field in table.inputs} == {"centr"}


def test_single_year_range_has_only_one_year_column(year_range):
    context = services.build_operating_tes_table_context("vsego", "koeff", 2027, 2027, view_year=2026)
    assert context["years"] == [2027]
    assert [column["year"] for column in context["value_columns"]] == [2027]
    assert {field["data-year"] for field in render_range(context).inputs} == {"2027"}


@pytest.mark.parametrize("sheet", [item["slug"] for item in services.CALC_SHEETS])
def test_all_sheets_use_reference_territory_labels_and_order(year_range, monkeypatch, sheet):
    from app.common.services.get_services.energy_systems import union_energy_system_get_services as reference

    monkeypatch.setattr(reference, "get_union_energy_system_list_full", lambda: [
        SimpleNamespace(name="ОЭС Центра (справочник)"),
        SimpleNamespace(name="ОЭС Северо-Запада"),
    ])
    context = services.build_operating_tes_table_context("centr", sheet, 2026, 2027, view_year=2027)
    assert context["territory"]["sheet_name"] == "ОЭС Центра (справочник)"
    columns = (
        context["coefficient_territories"] if sheet == "koeff"
        else context["level_territories"] if sheet == "khar-topl"
        else context["territory_columns"]
    )
    names = [item["sheet_name"] for item in columns]
    assert names.index("ОЭС Центра (справочник)") < names.index("ОЭС Северо-Запада")
    assert names[-3:] == ["ТИТЭС Сибири", "ТИТЭС Востока", "Децентрализованная зона"]
    html = render_page(context)
    assert "ОЭС Центра (справочник)" in html
    assert "Децентрализованная зона" in html
    assert "МинЭн" not in html
    assert "ПромПред" not in html
    if sheet == "pg":
        row = next(row for row in context["rows"] if row["key"] == "gas_natural")
        assert Decimal(row["col_values_raw"]["centr:2027"]) == 90
        assert Decimal(row["col_values_raw"]["vsego:2027"]) == 60


def render_page(context, can_edit=True):
    app = Flask(__name__)
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(Path(__file__).parents[2] / "app" / "templates"),
    ]))
    env.globals["get_reference_years"] = lambda: [2025, 2026, 2027, 2028]
    def url_for(endpoint, **values):
        from urllib.parse import urlencode
        return "/" + endpoint + "?" + urlencode({key: value for key, value in values.items() if value is not None})
    with app.test_request_context("/?start_year=2026&end_year=2027&rounding_digits=1"):
        html = env.get_template("ecology/operating_tes/operating_tes_table.html").render(
            **context, can_edit=can_edit, current_user=SimpleNamespace(is_authenticated=True),
            csrf_token="test-token", request=request, url_for=url_for,
        )
    return html


@pytest.mark.parametrize("sheet", ["zola", "sera", "azot", "co", "pg", "pg-tj"])
@pytest.mark.parametrize("selected_year,expected_year", [(2026, 2026), (2027, 2027), (2025, 2026)])
def test_emissions_use_year_buttons_and_selected_year_data(year_range, sheet, selected_year, expected_year):
    context = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027, view_year=selected_year)
    assert context["years"] == [expected_year]
    assert context["range_years"] == [2026, 2027]
    assert context["year_columns_mode"] is False
    assert {column["year"] for column in context["value_columns"]} == {expected_year}
    html = render_page(context)
    before_table, table_html = html.split('<table', 1)
    assert 'aria-label="Годы периода"' in before_table
    assert f'view_year={2027 if expected_year == 2026 else 2026}' in before_table
    thead = table_html.split('<thead')[1].split('</thead>')[0]
    is_pair = context["emission_view"]["kind"] == "pair"
    assert "ot-uniform-value-columns" in table_html
    assert thead.count('<tr') == (2 if is_pair else 1)
    assert 'ot-year-col' not in thead
    gas_row = next(row for row in context["rows"] if row["key"] == "gas_natural")
    rendered_gas_row = table_html.split('data-row-key="gas_natural"')[1].split('</tr>')[0]
    if is_pair:
        values = gas_row["pair_values"][f"vsego:{expected_year}"]
        assert values["left"] in rendered_gas_row
        assert values["right"] in rendered_gas_row
    else:
        assert gas_row["col_values"][f"vsego:{expected_year}"] in rendered_gas_row
    if sheet == "pg":
        assert Decimal(gas_row["col_values_raw"][f"vsego:{expected_year}"]) == (20 if expected_year == 2026 else 60)
        if expected_year == 2026:
            assert gas_row["col_values_raw"]["centr:2026"] == ""
        else:
            assert Decimal(gas_row["col_values_raw"]["centr:2027"]) == 90


def test_fuel_table_uses_year_buttons_and_all_territories(year_range):
    context = services.build_operating_tes_table_context(
        "vsego", "toplivo", 2026, 2027, view_year=2026,
    )
    assert context["years"] == [2026]
    assert context["range_years"] == [2026, 2027]
    assert context["year_columns_mode"] is False
    territories = [column["slug"] for column in context["territory_columns"]]
    assert territories[0] == "vsego"
    assert "minen" not in territories
    assert "prompred" not in territories
    assert {"severo-zapad", "norilsk", "isolated-dv", "decentralized-zone"}.issubset(territories)
    row = next(row for row in context["rows"] if row["key"] == "gaz_prir")
    assert row["col_values_raw"]["vsego:2026"] == "10"
    assert "vsego:2027" not in row["col_values_raw"]
    html = render_page(context)
    before_table, table_html = html.split('<table', 1)
    assert 'aria-label="Территория расчета"' not in before_table
    assert 'aria-label="Принадлежность данных"' in before_table
    assert 'aria-label="Годы периода"' in before_table
    assert 'view_year=2027' in before_table
    thead = table_html.split('<thead')[1].split('</thead>')[0]
    assert "Всего" in thead
    assert "ОЭС Северо-Запада" in thead
    assert "ТИТЭС Сибири" in thead
    assert "Децентрализованная зона" in thead
    assert "Станции отрасли" not in thead
    assert "Пром-предприятия" not in thead
    gas_row = table_html.split('data-row-key="gaz_prir"')[1].split('</tr>')[0]
    assert "10" in gas_row
    assert "20" not in gas_row
    assert 'data-autosave="1"' in html


@pytest.mark.parametrize("sheet", ["toplivo", "zola", "sera", "azot", "co", "pg", "pg-tj"])
def test_report_tabs_filter_affiliation_and_year_without_affiliation_columns(year_range, sheet):
    from urllib.parse import parse_qs, urlsplit

    context = services.build_operating_tes_table_context(
        "vsego", sheet, 2026, 2027, view_year=2027, affiliation="prompred",
    )
    assert context["years"] == [2027]
    assert context["range_years"] == [2026, 2027]
    assert context["year_columns_mode"] is False
    expected_slugs = {item["slug"] for item in services.TERRITORIES} - {"minen", "prompred"}
    assert {column["slug"] for column in context["territory_columns"]} == expected_slugs
    assert {column["year"] for column in context["value_columns"]} == {2027}
    assert {column["calculation_affiliation"] for column in context["value_columns"]} == {"prompred"}

    html = render_page(context)
    before_table, table_html = html.split("<table", 1)
    affiliation_position = before_table.index('aria-label="Принадлежность данных"')
    years_position = before_table.index('aria-label="Годы периода"')
    assert affiliation_position < years_position
    assert 'name="affiliation" value="prompred"' in before_table
    target_link = before_table.split('title="Показать данные за 2026 год"')[0].rsplit('href="', 1)[1].split('"')[0]
    query = parse_qs(urlsplit(target_link).query)
    assert query["view_year"] == ["2026"]
    assert query["affiliation"] == ["prompred"]
    assert query["start_year"] == ["2026"]
    assert query["end_year"] == ["2027"]

    thead = table_html.split("<thead")[1].split("</thead>")[0]
    assert "Всего" in thead
    assert "ОЭС Северо-Запада" in thead
    assert "ТИТЭС Сибири" in thead
    assert "Децентрализованная зона" in thead
    assert "Станции отрасли" not in thead
    assert "Пром-предприятия" not in thead


@pytest.mark.parametrize(("selected_year", "expected_year"), [(2026, 2026), (2027, 2027), (2025, 2026)])
def test_characteristics_year_buttons_show_the_selected_year(year_range, selected_year, expected_year):
    from urllib.parse import parse_qs, urlsplit

    context = services.build_operating_tes_table_context(
        "vsego", "khar-topl", 2026, 2027, view_year=selected_year,
    )
    assert context["years"] == [expected_year]
    assert context["range_years"] == [2026, 2027]
    assert context["year_columns_mode"] is False
    html = render_page(context)
    table = TableParser(html.split('<table')[1].split('</table>')[0])
    assert {field["data-year"] for field in table.inputs} == {str(expected_year)}
    assert {field["data-field"] for field in table.inputs} == services.CHAR_EDIT_FIELDS
    assert len(context["rows"]) == len({row["key"] for row in context["rows"]})
    co2_inputs = [field for field in table.inputs if field.get("data-field") == "k_co2"]
    assert len(co2_inputs) == 1
    assert co2_inputs[0]["data-year"] == str(expected_year)
    assert co2_inputs[0]["value"] == str(2 if expected_year == 2026 else 3)
    thead = html.split("<thead")[1].split("</thead>")[0]
    assert thead.count("<tr") == 2
    assert context["page_title"] not in thead
    group_row, year_row = thead.split("<tr")[1:]
    group_headers, year_headers = [TableParser(row).headers for row in (group_row, year_row)]
    assert group_headers[0]["rowspan"] == "2"
    assert sum(int(header.get("colspan", 1)) for header in group_headers) == len(context["char_columns"]) + 1
    assert len(year_headers) == len(context["char_columns"])
    assert "Низшая теплота сгорания" in group_row
    assert "Коэффициенты для расчета как в НД о Кадастре ПГ" in group_row
    assert 'ot-year-col' not in thead
    before_table = html.split('<table')[0]
    assert 'aria-label="Годы периода"' in before_table
    year_navigation = before_table.split('aria-label="Годы периода"', 1)[1].split('</div>', 1)[0]
    assert 'aria-current="true"' in year_navigation
    other_year = 2027 if expected_year == 2026 else 2026
    target_link = before_table.split(f'title="Показать данные за {other_year} год"')[0].rsplit('href="', 1)[1].split('"')[0]
    query = parse_qs(urlsplit(target_link).query)
    assert query["view_year"] == [str(other_year)]
    assert query["start_year"] == ["2026"]
    assert query["end_year"] == ["2027"]
    assert 'aria-label="Территория расчета"' in before_table
    assert 'aria-label="Принадлежность данных"' in before_table
    assert 'data-autosave="1"' in html


@pytest.mark.parametrize("sheet,substance", [("zola", "золы"), ("sera", "серы"), ("co", "CO"), ("azot", "азота"), ("pg", "ПГ"), ("pg-tj", "ПГ через ТДж")])
def test_emission_formulas_render_indices_and_escape_custom_text(year_range, monkeypatch, sheet, substance):
    from app.ecology.services.formula_text import operating_tes_formula_text_services as formulas

    context = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027)
    html = render_page(context)
    formula = html.split(f'aria-label="Расчетная формула {substance}"')[0].rsplit('<div', 1)[-1]
    assert "М<sub>отх</sub>" in formula
    if sheet in {"zola", "sera", "co"}:
        assert "B<sup>H</sup>" in formula
        assert html.count("Перевод в натур. (B<sup>H</sup>)") == len(context["territory_columns"])
    if sheet == "zola":
        assert "a<sub>ун</sub>" in formula
        assert "A<sup>р</sup>" in formula
        assert "q<sub>ч</sub>" in formula
        assert "Q<sub>н</sub>" in formula
    elif sheet == "sera":
        assert "М<sub>отх</sub> = 0,02 · B<sup>H</sup> · S<sup>p</sup> · (1 − x)" in formula
        assert "КПД сероочистки" in html
        assert "КПД золоулавливания" not in html
    elif sheet == "co":
        assert "М<sub>отх</sub><sup>CO</sup> = 0,001 · B<sup>H</sup>" in formula
        assert "(q<sub>3</sub> · R · Q<sub>н</sub> / 1013) · (1 − q<sub>4</sub> / 100)" in formula
        assert "Коэффициент подавления CO" in html
        assert "КПД золоулавливания" not in html
        assert "КПД сероочистки" not in html
    elif sheet == "azot":
        assert "М<sub>отх</sub><sup>NOx</sup> = 0,001 · B · (1 − q<sub>ч</sub> / 100) · b<sub>j</sub>" in formula
        assert "Коэффициент подавления оксидов азота в топке n" in html
        assert "Перевод в натур." not in html
        assert "B<sup>H</sup>" not in html
        assert "(1 − n)" not in formula
    elif sheet == "pg":
        assert "М<sub>отх</sub><sup>CO<sub>2</sub></sup> = B · K<sub>CO<sub>2</sub></sub>" in formula
        assert "Коэффициент подавления ПГ (оксидов углерода)" in html
        assert "Перевод в натур." not in html
        assert "B<sup>H</sup>" not in html
    else:
        assert "М<sub>отх</sub><sup>CO<sub>2</sub></sup> = МДж · K<sub>CO<sub>2</sub></sub> / 1000" in formula
        assert "Коэффициент подавления ПГ (оксидов углерода)" in html
        assert "КПД золоулавливания" not in html
        assert "Перевод в натур." not in html
        assert "B<sup>H</sup>" not in html
        assert html.count('aria-label="Формула МДж"') == len(context["territory_columns"])
        assert "МДж = B / (тут/тн) · (ТДж/тыс. т натур.)" in html
        assert "а не национальный коэффициент эмиссии" in html
    assert "кДж/кг" not in formula
    assert "title=\"Расчетная формула: М&lt;sub&gt;отх&lt;/sub&gt;" in formula
    assert html.count(f'aria-label="Формула Мотх {substance}"') == len(context["territory_columns"])
    if sheet in {"zola", "sera", "co"}:
        assert html.count(f'aria-label="Формула перевода в натур. для {substance}"') == len(context["territory_columns"])
        assert "B&lt;sup&gt;H&lt;/sup&gt; = Топливо · 7000 / Q&lt;sub&gt;н&lt;/sub&gt;" in html
        assert "акцептованное значение" in html

    monkeypatch.setattr(formulas, "get_formula_text_overrides", lambda: {
        f"sheet_{sheet.replace('-', '_')}": 'Мотх = <img src=x onerror="alert(1)">',
    })
    context = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027)
    html = render_page(context)
    assert '<img src=x' not in html
    assert '&lt;img src=x onerror=&#34;alert(1)&#34;&gt;' in html
    assert '&amp;lt;img' in html


@pytest.mark.parametrize("sheet,leaf_mass,parent_mass", [
    ("zola", "0.24", "0.30"), ("sera", "0.09", "0.1125"), ("co", "0.000784", "0.00098"),
])
@pytest.mark.parametrize("year,territory,fuel", [
    (2026, "vsego", 100), (2027, "vsego", 200), (2027, "centr", 300),
])
def test_emissions_use_accepted_fuel_and_heat_for_each_subtype(
    year_range, monkeypatch, year, territory, fuel, sheet, leaf_mass, parent_mass,
):
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        2026: {"vsego": {"kuzngd": Decimal("100"), "kuznt": Decimal("50")}},
        2027: {
            "vsego": {"kuzngd": Decimal("200"), "kuznt": Decimal("100")},
            "centr": {"kuzngd": Decimal("300"), "kuznt": Decimal("150")},
        },
    })
    monkeypatch.setattr(services, "load_input_overrides", lambda years: {
        (territory, year, "kuzn_gd"): Decimal("999"),
    })
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", key, y): {
            "qh_kcal": Decimal(heat), "qh_kj": Decimal("1013" if sheet == "co" else "32680"),
            "ash": Decimal("20"), "ash_share": Decimal("0.5"), "q_mech": Decimal("2"),
            "k_natural": Decimal("10"), "q_chem": Decimal("0.5"), "r_chem": Decimal("0.8"),
            "sulfur": Decimal("2.5"), "sulfur_share": Decimal("0.1"),
            "tut_per_t": Decimal("0.5"), "tj_per_kt": Decimal("10"), "t_co2_per_tj": Decimal("20"),
        }
        for key, heat in [("kuzn_gd", "3500"), ("kuzn_t", "7000")]
        for y in years
    })
    context = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027, view_year=year)
    rows = {row["key"]: row for row in context["rows"]}
    column = f"{territory}:{year}"
    assert Decimal(rows["kuzn_gd"]["col_values_raw"][f"{column}:l"]) == fuel * 2
    assert Decimal(rows["kuzn_gd"]["col_values_raw"][f"{column}:r"]) == Decimal(fuel) * Decimal(leaf_mass)
    assert Decimal(rows["kuznetsk"]["col_values_raw"][f"{column}:l"]) == Decimal(fuel) * Decimal("2.5")
    assert Decimal(rows["kuznetsk"]["col_values_raw"][f"{column}:r"]) == Decimal(fuel) * Decimal(parent_mass)

    other = services.build_operating_tes_table_context("vsego", "pg-tj", 2026, 2027, view_year=year)
    other_row = next(row for row in other["rows"] if row["key"] == "kuzn_gd")
    assert Decimal(other_row["col_values_raw"][f"{column}:l"]) == Decimal(fuel) * 20
    assert Decimal(other_row["col_values_raw"][f"{column}:r"]) == Decimal(fuel) * Decimal("0.4")


@pytest.mark.parametrize("sheet,mass_per_fuel", [("zola", "0.24"), ("sera", "0.09"), ("co", "0.000784"), ("azot", "0.0049"), ("pg", "2.5"), ("pg-tj", "0.4")])
@pytest.mark.parametrize("year", [2026, 2027])
@pytest.mark.parametrize("only_total", [False, True], ids=["all-territories", "no-local-data"])
def test_emission_columns_use_their_own_accepted_fuel_page_values(
    year_range, monkeypatch, year, only_total, sheet, mass_per_fuel,
):
    slugs = (
        "vsego", "severo-zapad", "centr", "srednyaya-volga", "yug", "ural",
        "sibir", "vostok", "norilsk", "isolated-dv", "decentralized-zone",
    )
    accepted = {
        y: {
            slug: {"kuzngd": Decimal(index * (y - 2025) * 100)}
            for index, slug in enumerate(slugs, 1)
            if not only_total or slug == "vsego"
        }
        for y in (2026, 2027)
    }
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        y: {slug: dict(bucket) for slug, bucket in accepted[y].items()} for y in years
    })
    monkeypatch.setattr(services, "get_fuel_module_consumption_row_specs", lambda: [
        {"key": "kuzngd", "label": "Кузнецкий Г, Д", "kind": "value"},
    ])
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", "kuzn_gd", y): {
            "qh_kcal": Decimal("3500"), "qh_kj": Decimal("1013" if sheet == "co" else "32680"),
            "q_chem": Decimal("0.5"), "r_chem": Decimal("0.8"), "bj": Decimal("5"), "k_co2": Decimal("2.5"),
            "ash": Decimal("20"), "ash_share": Decimal("0.5"), "q_mech": Decimal("2"),
            "sulfur": Decimal("2.5"), "sulfur_share": Decimal("0.1"),
            "tut_per_t": Decimal("0.5"), "tj_per_kt": Decimal("10"), "t_co2_per_tj": Decimal("20"),
        }
        for y in years
    })
    emission_page = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027, view_year=year)
    emission_row = next(row for row in emission_page["rows"] if row["key"] == "kuzn_gd")
    assert {column["slug"] for column in emission_page["territory_columns"]} == set(slugs)
    assert not {column["slug"] for column in emission_page["territory_columns"]} & {"minen", "prompred"}
    for slug in slugs:
        fuel_page = services.build_operating_tes_table_context(
            slug, "toplivo", 2026, 2027, view_year=year,
        )
        fuel_row = next(row for row in fuel_page["rows"] if row["key"] == "kuzngd")
        column = f"{slug}:{year}"
        fuel = fuel_row["col_values_raw"][column]
        motkh_column = column if sheet in {"azot", "pg"} else f"{column}:r"
        motkh = emission_row["col_values_raw"][motkh_column]
        if only_total and slug != "vsego":
            assert fuel == motkh == ""
            if sheet not in {"azot", "pg"}:
                assert emission_row["col_values_raw"][f"{column}:l"] == ""
        else:
            assert Decimal(fuel) == accepted[year][slug]["kuzngd"]
            assert Decimal(motkh) == Decimal(fuel) * Decimal(mass_per_fuel)
            if sheet not in {"azot", "pg"}:
                expected_left = Decimal(fuel) * (20 if sheet == "pg-tj" else 2)
                assert Decimal(emission_row["col_values_raw"][f"{column}:l"]) == expected_left
        if sheet in {"azot", "pg"}:
            assert f"{column}:l" not in emission_row["col_values_raw"]


@pytest.mark.parametrize("sheet,prefix,eta_key,expected_mass", [
    ("zola", "ash", "ash_eta", "25.2"),
    ("sera", "so2", "sulfur_eta", "9.45"),
    ("co", "co", "co_k", "0.08232"),
    ("azot", "nox", "nox_n", "1.029"),
    ("pg", "pg", "pg_k", "525"),
    ("pg-tj", "pg_tj", "pg_k", "84"),
])
@pytest.mark.parametrize("year", [2026, 2027])
def test_emission_summary_uses_six_groups_and_each_columns_capture(
    year_range, monkeypatch, year, sheet, prefix, eta_key, expected_mass,
):
    slugs = [territory["slug"] for territory in services.TERRITORIES]
    aliases = {"norilsk": "tites-sibir", "isolated-dv": "tites-vostok"}
    fuel = {
        "gaz": 999, "gaz_prir": 3, "gazpp": 7,
        "isk_gaz": 999, "domen_g": 20, "mazut": 999, "maztop": 30,
        "torf": 40, "ugol": 999, "kuzn": 999, "kuzngd": 20, "don": 30,
        "proch": 999, "tvproch": 60,
    }
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        y: {
            slug: {field: Decimal(amount * index * (y - 2025)) for field, amount in fuel.items()}
            for index, slug in enumerate(slugs, 1)
        } for y in years
    })
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", key, y): {
            "qh_kcal": Decimal("7000"), "qh_kj": Decimal("1013" if sheet == "co" else "32680"),
            "q_chem": Decimal("0.5"), "r_chem": Decimal("0.8"), "bj": Decimal("5"), "k_co2": Decimal("2.5"),
            "ash": Decimal("20"), "ash_share": Decimal("0.5"), "q_mech": Decimal("2"),
            "sulfur": Decimal("2.5"), "sulfur_share": Decimal("0.1"),
            "tut_per_t": Decimal("0.5"), "tj_per_kt": Decimal("10"), "t_co2_per_tj": Decimal("20"),
        }
        for key in services.DEFAULT_CHARACTERISTICS for y in years
    })
    monkeypatch.setattr(services, "load_coefficient_overrides", lambda years: {
        (aliases.get(slug, slug), y, kind): (
            Decimal(index + y - 2026) / 100 if kind == eta_key else Decimal("0.99")
        )
        for index, slug in enumerate(slugs, 1) for y in years
        for kind in ("ash_eta", "sulfur_eta", "co_k", "nox_n", "pg_k")
    })
    context = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027, view_year=year)
    rows = {row["key"]: row for row in context["rows"]}
    total_key, emitted_key = f"{prefix}_motkh_total", f"{prefix}_emitted"
    assert [row["key"] for row in context["rows"][:4]] == [
        total_key, eta_key, emitted_key, "gas",
    ]
    visible_slugs = [slug for slug in slugs if slug not in {"minen", "prompred"}]
    assert {column["slug"] for column in context["territory_columns"]} == set(visible_slugs)
    for index, slug in enumerate(slugs, 1):
        if slug in {"minen", "prompred"}:
            continue
        column = f"{slug}:{year}"
        expected_total = Decimal(expected_mass) * index * (year - 2025)
        expected_eta = Decimal(index + year - 2026) / 100
        assert Decimal(rows[total_key]["col_values_raw"][column]) == expected_total
        assert Decimal(rows[eta_key]["col_values_raw"][column]) == expected_eta
        assert Decimal(rows[emitted_key]["col_values_raw"][column]) == expected_total * (1 - expected_eta)
        motkh_column = column if sheet in {"azot", "pg"} else f"{column}:r"
        root_sum = sum(Decimal(rows[key]["col_values_raw"][motkh_column]) for key in (
            "gas", "gas_artificial", "oil_fuel", "peat", "coal", "other_fuel",
        ))
        assert root_sum == expected_total
    html = render_page(context)
    fields = [field for field in TableParser(html).inputs if field.get("class", "").endswith("ot-edit-value")]
    assert len(fields) == len(visible_slugs)
    for slug, field in zip(visible_slugs, fields):
        index = slugs.index(slug) + 1
        assert field["data-year"] == str(year)
        assert field["data-territory"] == aliases.get(slug, slug)
        assert field["data-affiliation"] == "all"
        assert field["data-field"] == eta_key
        assert field["data-column"] == f"{slug}:{year}"
        assert "sheet_slug=koeff" in field["data-update-url"]
        assert Decimal(field["value"].replace(",", ".")) == Decimal(index + year - 2026) / 100
        assert Decimal(field["data-capture-total"]) == Decimal(expected_mass) * index * (year - 2025)
    assert "ot-edit-value\"" not in render_page(context, can_edit=False)
    assert rows[eta_key]["css_class"] == "table-warning"
    assert rows[total_key]["css_class"] == rows[emitted_key]["css_class"] == "table-primary"
    for key in (total_key, eta_key, emitted_key):
        rendered_row = html.split(f'data-row-key="{key}"')[1].split('</tr>')[0]
        if sheet in {"azot", "pg"}:
            assert 'colspan="2"' not in rendered_row
            assert rendered_row.count('<td') == len(visible_slugs) + 1
        else:
            assert rendered_row.count('colspan="2"') == len(visible_slugs)
        assert "ot-row-empty-hidden" not in html.split(f'data-row-key="{key}"')[0].rsplit('<tr', 1)[1]
    assert "ΣМ<sub>отх</sub>." in html
    assert "М<sub>выб</sub>." in html
    assert 'aria-label="Описание: ΣМотх."' in html
    assert "повторно не суммируются" in html


@pytest.mark.parametrize("sheet", ["zola", "sera", "co", "azot", "pg", "pg-tj"])
def test_empty_emission_summary_remains_visible_with_coefficients(year_range, monkeypatch, sheet):
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {year: {} for year in years})
    context = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027)
    summary = context["rows"][:3]
    assert all(row["is_empty"] is False for row in summary)
    assert summary[0]["col_values_raw"]["vsego:2026"] == ""
    assert summary[1]["col_values_raw"]["vsego:2026"] != ""
    assert summary[2]["col_values_raw"]["vsego:2026"] == ""


@pytest.mark.parametrize("heat", [None, Decimal("0"), Decimal("3500")])
def test_pg_uses_conditional_fuel_and_applies_suppression_once(year_range, monkeypatch, heat):
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        2026: {"vsego": {"gaz_prir": Decimal("100"), "gazpp": Decimal("50")}},
    })
    monkeypatch.setattr(services, "load_input_overrides", lambda years: {
        ("vsego", 2026, "gas_natural"): Decimal("999"),
    })
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", key, 2026): {
            "qh_kcal": heat, "k_natural": Decimal("10"), "k_co2": Decimal(coefficient),
        }
        for key, coefficient in (("gas_natural", "2"), ("gas_associated", "3"))
    })
    monkeypatch.setattr(services, "load_coefficient_overrides", lambda years: {
        ("vsego", 2026, "pg_k"): Decimal("0.2"),
    })
    context = services.build_operating_tes_table_context("vsego", "pg", 2026, 2027, view_year=2026)
    rows = {row["key"]: row for row in context["rows"]}
    expected = {
        "gas_natural": "200", "gas_associated": "150", "gas": "350",
        "pg_motkh_total": "350", "pg_k": "0.2", "pg_emitted": "280",
    }
    for key, amount in expected.items():
        assert Decimal(rows[key]["col_values_raw"]["vsego:2026"]) == Decimal(amount)
    assert all(not row["pair_values"] for row in context["rows"])


@pytest.mark.parametrize("year,energy_natural,energy_associated,mass_natural,mass_associated,emitted,displayed", [
    (2026, "2000", "1200", "40", "48", "69.52", "69,5"),
    (2027, "4000", "2400", "80", "96", "121.44", "121,4"),
])
def test_pg_tj_uses_each_fuels_inventory_coefficients_and_selected_year(
    year_range, monkeypatch, year, energy_natural, energy_associated, mass_natural, mass_associated, emitted, displayed,
):
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        y: {"vsego": {"gaz_prir": Decimal("100"), "gazpp": Decimal("50")}} for y in years
    })
    monkeypatch.setattr(services, "load_input_overrides", lambda years: {
        ("vsego", y, "gas_natural"): Decimal("999") for y in years
    })
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", key, y): {
            "tut_per_t": Decimal(tut), "tj_per_kt": Decimal(tj) * (y - 2025),
            "t_co2_per_tj": Decimal(co2), "k_natural": Decimal("999"),
            "qh_kcal": None, "qh_kj": None, "ash": Decimal("99"), "k_co2": Decimal("999"),
        }
        for key, tut, tj, co2 in (("gas_natural", "0.5", "10", "20"), ("gas_associated", "0.25", "6", "40"))
        for y in years
    })
    monkeypatch.setattr(services, "load_coefficient_overrides", lambda years: {
        ("vsego", y, "pg_k"): Decimal("0.21" if y == 2026 else "0.31") for y in years
    })
    context = services.build_operating_tes_table_context(
        "vsego", "pg-tj", 2026, 2027, rounding_digits=1, view_year=year,
    )
    rows = {row["key"]: row for row in context["rows"]}
    column = f"vsego:{year}"
    for key, energy, mass in (
        ("gas_natural", energy_natural, mass_natural),
        ("gas_associated", energy_associated, mass_associated),
    ):
        assert Decimal(rows[key]["col_values_raw"][f"{column}:l"]) == Decimal(energy)
        assert Decimal(rows[key]["col_values_raw"][f"{column}:r"]) == Decimal(mass)
    total_mass = Decimal(mass_natural) + Decimal(mass_associated)
    assert Decimal(rows["gas"]["col_values_raw"][f"{column}:r"]) == total_mass
    assert Decimal(rows["pg_tj_motkh_total"]["col_values_raw"][column]) == total_mass
    assert Decimal(rows["pg_tj_emitted"]["col_values_raw"][column]) == Decimal(emitted)
    assert rows["pg_tj_emitted"]["col_values"][column] == displayed
    assert context["sheet"]["unit"] == "тыс. т"
    assert "тыс.т/год" in context["page_title"]


@pytest.mark.parametrize("sheet,eta_key", [
    ("zola", "ash_eta"), ("sera", "sulfur_eta"), ("co", "co_k"),
    ("azot", "nox_n"), ("pg", "pg_k"), ("pg-tj", "pg_k"),
])
@pytest.mark.parametrize("digits,display", [(0, "0,8567"), (1, "0,9"), (2, "0,86"), (3, "0,857"), (-1, "1")])
def test_coefficient_rounding_only_changes_coefficient_display(year_range, monkeypatch, sheet, eta_key, digits, display):
    from urllib.parse import parse_qs, urlsplit
    from html import unescape

    monkeypatch.setattr(services, "load_coefficient_overrides", lambda years: {
        ("vsego", year, eta_key): Decimal("0.8567") for year in years
    })
    original = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027, rounding_digits=1)
    rounded = services.build_operating_tes_table_context(
        "vsego", sheet, 2026, 2027, rounding_digits=1, coefficient_rounding_digits=digits,
    )
    assert rounded["rounding_digits"] == 1
    assert rounded["coefficient_rounding_digits"] == digits
    for before, after in zip(original["rows"], rounded["rows"]):
        assert after["col_values_raw"] == before["col_values_raw"]
        if after["key"] != eta_key:
            assert after == before
    row = next(row for row in rounded["rows"] if row["key"] == eta_key)
    assert row["col_values"]["vsego:2026"] == display
    html = render_page(rounded)
    assert html.index('id="coefficient_rounding_digits"') < html.index('id="rounding_digits"')
    assert "Округл (КПД/КП)" in html
    field = next(field for field in TableParser(html).inputs if field.get("data-column") == "vsego:2026")
    assert field["value"] == display
    assert field["data-raw-value"] == "0,8567"
    readonly = render_page(rounded, can_edit=False)
    assert display in readonly.split(f'data-row-key="{eta_key}"')[1].split('</tr>')[0]
    for anchor in html.split('<a href="')[1:]:
        query = parse_qs(urlsplit(unescape(anchor.split('"', 1)[0])).query)
        if "sheet_slug" in query and "rounding_digits" in query:
            assert query["coefficient_rounding_digits"] == [str(digits)]


@pytest.mark.parametrize("sheet", ["obemy", "toplivo", "khar-topl", "koeff"])
def test_coefficient_rounding_control_is_hidden_on_other_tabs(year_range, sheet):
    context = services.build_operating_tes_table_context("vsego", sheet, 2026, 2027)
    assert 'id="coefficient_rounding_digits"' not in render_page(context)

@pytest.mark.parametrize("sheet,kind", [
    ("zola", "ash_eta"), ("sera", "sulfur_eta"), ("azot", "nox_n"),
    ("co", "co_k"), ("pg", "pg_k"), ("pg-tj", "pg_k"),
])
@pytest.mark.parametrize("stored,editable", [
    ("0.973410000000000000", "0,97341"),
    ("0.973410000000000001", "0,973410000000000001"),
    ("0.000000000000000000", "0"),
    ("1.000000000000000000", "1"),
])
def test_editable_emission_coefficients_trim_only_insignificant_zeros(
    year_range, monkeypatch, sheet, kind, stored, editable,
):
    monkeypatch.setattr(services, "load_coefficient_overrides", lambda years: {
        ("vsego", 2026, kind): Decimal(stored),
    })
    context = services.build_operating_tes_table_context(
        "vsego", sheet, 2026, 2027, view_year=2026, coefficient_rounding_digits=1,
    )
    fields = TableParser(render_page(context)).inputs
    field = next(field for field in fields
                 if field.get("data-column") == "vsego:2026" and field.get("data-field") == kind)
    assert field["data-raw-value"] == editable
    assert Decimal(field["data-raw-value"].replace(",", ".")) == Decimal(stored)
