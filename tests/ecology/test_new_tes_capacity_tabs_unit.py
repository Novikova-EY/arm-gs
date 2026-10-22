"""Независимые категории новых ТЭС и общий с действующими ТЭС KCO2."""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from flask import Flask, request
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.ecology.services import new_tes_page_services as services
from app.ecology.services import operating_tes_page_services as operating
from app.ecology.services.new_tes_constants import NEW_TES_VOLUME_COLUMNS


@pytest.fixture
def page_data(monkeypatch):
    monkeypatch.setattr(services, "get_year_columns", lambda *args: [2026, 2027])
    monkeypatch.setattr(services, "get_filter_year_list", lambda: [2026, 2027])
    monkeypatch.setattr(services, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(services, "get_fuel_module_consumption_row_specs", lambda: [
        {"key": "maztop", "label": "Мазут", "kind": "value"},
    ])
    monkeypatch.setattr(services, "ot_formula_text", lambda key: key)
    monkeypatch.setattr(services, "ensure_default_norm_rows", lambda years: None)
    monkeypatch.setattr(services, "load_norm_overrides", lambda years: {
        ("mazut", "le100", 2026): {"ash": Decimal("2")},
        ("mazut", "gt100", 2026): {"ash": Decimal("3")},
    })
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", "mazut", 2026): {"k_co2": Decimal("4")},
        ("vsego", "mazut", 2027): {"k_co2": Decimal("5")},
    })
    monkeypatch.setattr(services, "load_accepted_new_tes_fuel_inputs", lambda years: {
        year: {"vsego": {
            "le100": {"mazut": Decimal("10"), "maztop": Decimal("10"), "b": Decimal("10")},
            "gt100": {"mazut": Decimal("20"), "maztop": Decimal("20"), "b": Decimal("20")},
        }} for year in years
    })


def render_page(context):
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(Path(__file__).parents[2] / "app" / "templates"),
    ]))
    def url_for(endpoint, **values):
        return "/" + endpoint + "?" + urlencode({key: value for key, value in values.items() if value is not None})
    with Flask(__name__).test_request_context("/?capacity_class=gt100"):
        return env.get_template("ecology/operating_tes/operating_tes_table.html").render(
            **context, can_edit=True, current_user=SimpleNamespace(is_authenticated=True),
            csrf_token="test", request=request, url_for=url_for,
        )


@pytest.mark.parametrize("capacity,fuel,ash", [("le100", "10", "20"), ("gt100", "20", "60")])
def test_category_has_own_fuel_norms_and_volumes(page_data, capacity, fuel, ash):
    context = services.build_new_tes_table_context("vsego", "toplivo", view_year=2026, capacity_class=capacity)
    row = next(row for row in context["rows"] if row["key"] == "maztop")
    assert Decimal(row["col_values_raw"]["vsego"]) == Decimal(fuel)
    html = render_page(context)
    assert "до 100 МВт" in html
    assert "100 МВт и более" in html
    assert f"capacity_class={capacity}" in html.split('title="Показать данные за 2027 год"')[0].rsplit('href="', 1)[1]

    norms = services.build_new_tes_table_context("vsego", "spravochnik", view_year=2026, capacity_class=capacity)
    row = next(row for row in norms["rows"] if row["key"] == "mazut")
    assert set(row["char_values"][2026]) == {"ash", "so2", "nox", "k_co2"}
    assert row["char_values"][2026]["k_co2"] == "4"
    html = render_page(norms)
    thead = html.split("<thead", 1)[1].split("</thead>", 1)[0]
    assert 'rowspan="2"' in thead
    assert "Загрязняющие вещества, кг/т.у.т." in thead
    assert "Парниковые газы (CO2), т/т.у.т." in thead
    for label in ("твердые частицы (зола)", "диоксид серы (SO2)", "оксиды азота (NOx)"):
        assert label in thead
    assert "A<sup>р</sup>" not in thead
    assert 'data-field="k_co2"' in html
    assert f'capacity_class={capacity}"' in html.split('data-update-url="')[1].split('data-can-edit')[0]
    assert 'data-field="co"' not in html

    context = services.build_new_tes_table_context("vsego", "obemy", view_year=2026, capacity_class=capacity)
    row = next(row for row in context["rows"] if row["key"] == "mazut")
    values = {key: row["col_values_raw"][f"vsego:{key}"] for key, _ in NEW_TES_VOLUME_COLUMNS}
    assert Decimal(values["ash"]) == Decimal(ash)
    assert Decimal(values["so2"]) == Decimal(fuel) * Decimal("8.8")
    assert Decimal(values["nox"]) == Decimal(fuel) * Decimal("2.52")
    assert Decimal(values["co"]) == 0
    assert Decimal(values["co2"]) == Decimal(fuel) * 4
    assert Decimal(values["pollutants_total"]) == sum(Decimal(values[key]) for key in ("ash", "so2", "nox", "co"))
    html = render_page(context)
    assert context["page_title"] == "Ожидаемые объемы выбросов вредных веществ и парниковых газов в атмосферу, тыс. т"
    assert html.index('data-row-key="total"') < html.index('data-row-key="gas"')
    thead = html.split("<thead", 1)[1].split("</thead>", 1)[0]
    territories = context["territory_columns"]
    assert thead.count("<tr ") == 3
    assert thead.count('<th ') == 1 + len(territories) * 8
    assert thead.count('colspan="6"') == len(territories)
    assert thead.count('colspan="5"') == len(territories)
    assert thead.count('Вредные вещества, т') == len(territories)
    assert 'rowspan="3" scope="col">Вид топлива' in thead
    for terr in territories:
        assert f'>{terr["sheet_name"]}</th>' in thead
    for key, label in NEW_TES_VOLUME_COLUMNS:
        assert thead.count(label) == len(territories)
    assert 'data-row-key="mazut"' in html
    assert 'data-row-key="vsego"' not in html


def test_total_remains_first_and_visible_without_accepted_fuel(page_data, monkeypatch):
    monkeypatch.setattr(services, "load_accepted_new_tes_fuel_inputs", lambda years: {})
    context = services.build_new_tes_table_context("vsego", "obemy", view_year=2026, capacity_class="gt100")
    total = context["rows"][0]
    assert total["key"] == "total"
    assert total["is_empty"] is False
    assert not any(total["col_values_raw"].values())
    html = render_page(context)
    assert 'class="table-info" data-row-key="total"' in html


def test_selected_year_changes_shared_kco2_and_volume(page_data):
    norms = services.build_new_tes_table_context("vsego", "spravochnik", view_year=2027)
    row = next(row for row in norms["rows"] if row["key"] == "mazut")
    assert row["char_values"][2027]["k_co2"] == "5"
    volumes = services.build_new_tes_table_context("vsego", "obemy", view_year=2027)
    row = next(row for row in volumes["rows"] if row["key"] == "mazut")
    assert Decimal(row["col_values_raw"]["vsego:co2"]) == 50


@pytest.mark.parametrize("capacity,mazut_b,gas_b,ash_norm", [
    ("le100", 3, 2, 2), ("gt100", 7, 5, 3),
])
def test_volume_cells_keep_fuel_and_territory_separate(page_data, monkeypatch, capacity, mazut_b, gas_b, ash_norm):
    monkeypatch.setattr(services, "load_accepted_new_tes_fuel_inputs", lambda years: {
        year: {
            "vsego": {capacity: {"maztop": Decimal("10"), "mazut": Decimal("10"), "b": Decimal("10")}},
            "centr": {capacity: {
                "maztop": Decimal(mazut_b), "mazut": Decimal(mazut_b),
                "gaz_prir": Decimal(gas_b), "gaz": Decimal(gas_b), "b": Decimal(mazut_b + gas_b),
            }},
        } for year in years
    })
    context = services.build_new_tes_table_context("vsego", "obemy", view_year=2026, capacity_class=capacity)
    rows = {row["key"]: row for row in context["rows"]}
    assert list(rows) == ["total", *[spec["key"] for spec in services.FUEL_ROWS]]
    total = rows["total"]
    roots = [spec["key"] for spec in services.FUEL_ROWS if not spec.get("parent_key")]
    for column in context["value_columns"]:
        raw = total["col_values_raw"][column["slug"]]
        expected = services._sum_present([
            Decimal(rows[key]["col_values_raw"][column["slug"]])
            if rows[key]["col_values_raw"][column["slug"]] else None
            for key in roots
        ])
        assert (Decimal(raw) if raw else None) == expected
    assert Decimal(total["col_values_raw"]["centr:co2"]) == mazut_b * 4 + Decimal(gas_b) * Decimal("1.59")
    assert total["kind"] == "total"
    assert total["label"] == "Итого"
    assert Decimal(rows["mazut"]["col_values_raw"]["vsego:ash"]) == 10 * ash_norm
    assert Decimal(rows["mazut"]["col_values_raw"]["centr:ash"]) == mazut_b * ash_norm
    assert Decimal(rows["mazut"]["col_values_raw"]["centr:co2"]) == mazut_b * 4
    assert Decimal(rows["gas_natural"]["col_values_raw"]["centr:co2"]) == Decimal(gas_b) * Decimal("1.59")
    assert rows["gas_natural"]["col_values_raw"]["vsego:co2"] == ""
    for metric, _label in NEW_TES_VOLUME_COLUMNS:
        assert rows["oil_fuel"]["col_values_raw"][f"centr:{metric}"] == rows["mazut"]["col_values_raw"][f"centr:{metric}"]
        assert rows["mazut"]["col_values_raw"][f"yug:{metric}"] == ""
    assert rows["mazut"]["is_empty"] is False
    assert rows["diesel"]["is_empty"] is True
    html = render_page(context)
    mazut_html = html.split('data-row-key="mazut"', 1)[1].split('</tr>', 1)[0]
    columns = context["value_columns"]
    assert mazut_html.count('<td ') == 1 + len(columns)
    assert [column["slug"] for column in columns] == [
        f"{terr['slug']}:{metric}" for terr in context["territory_columns"] for metric, _ in NEW_TES_VOLUME_COLUMNS
    ]
    assert 'data-territory="centr" data-metric="co2"' in mazut_html
    assert f'title="{mazut_b * 4}">' in mazut_html


def test_kco2_edits_are_shared_both_ways_and_between_capacity_tabs(operating_tes_db):
    services.upsert_norm("gas_natural", 2026, "pg_le100", Decimal("3"))
    overrides = operating.load_characteristic_overrides([2026])
    assert operating.resolve_chars("gas_natural", 2026, overrides)["k_co2"] == 3
    assert services.resolve_norm("gas_natural", "gt100", 2026, {}, overrides)["pg"] == 3
    operating.upsert_characteristic("centr", "gas_natural", 2026, "k_co2", Decimal("5"))
    overrides = operating.load_characteristic_overrides([2026])
    for capacity in ("le100", "gt100"):
        assert services.resolve_norm("gas_natural", capacity, 2026, {}, overrides)["pg"] == 5
    assert services.resolve_norm("gas_natural", "le100", 2027, {}, overrides)["pg"] == Decimal("1.59")
    assert operating_tes_db.query(operating.OperatingTesFuelCharacteristic).count() == 1


def test_norm_edits_keep_capacity_year_and_version_independent(operating_tes_db, monkeypatch):
    from sqlalchemy.orm import registry

    mapper_registry = registry()
    table = services.NewTesNorm.__table__
    model = type("NewTesNorm", (), {})
    mapper_registry.map_imperatively(model, table)
    table.create(operating_tes_db.connection())
    model.query = operating_tes_db.query(model)
    monkeypatch.setattr(services, "NewTesNorm", model)
    monkeypatch.setattr(services, "db", SimpleNamespace(session=operating_tes_db))
    monkeypatch.setattr(services, "get_current_db_version_id", lambda: 1)
    try:
        services.upsert_norm("mazut", 2026, "ash_le100", Decimal("2"))
        services.upsert_norm("mazut", 2026, "ash_gt100", Decimal("3"))
        services.upsert_norm("mazut", 2027, "ash_le100", Decimal("4"))
        monkeypatch.setattr(services, "get_current_db_version_id", lambda: 2)
        services.upsert_norm("mazut", 2026, "ash_le100", Decimal("5"))
        overrides = services.load_norm_overrides([2026, 2027])
        assert overrides[("mazut", "le100", 2026)]["ash"] == 5
        assert ("mazut", "gt100", 2026) not in overrides
        monkeypatch.setattr(services, "get_current_db_version_id", lambda: 1)
        overrides = services.load_norm_overrides([2026, 2027])
        assert overrides[("mazut", "le100", 2026)]["ash"] == 2
        assert overrides[("mazut", "gt100", 2026)]["ash"] == 3
        assert overrides[("mazut", "le100", 2027)]["ash"] == 4
    finally:
        mapper_registry.dispose()


def test_invalid_category_and_deleted_sheets_are_not_silently_replaced():
    assert services.build_new_tes_table_context("vsego", "obemy", capacity_class="invalid") is None
    for sheet in ("zola", "sera", "azot", "co", "pg", "pg-tj", "udel-e", "udel-fuel", "udel-ee"):
        assert services.build_new_tes_table_context("vsego", sheet) is None
