# -*- coding: utf-8 -*-
"""Строки зарубежного импорта и экспорта в балансах ЭЭ."""

from __future__ import annotations

from decimal import Decimal

from app.energy_balance.services import ee_balance_page_services as page_services
from app.energy_balance.services import ee_import_export_page_services as import_export_services


def test_import_export_page_forwards_balance_scope_filters(monkeypatch):
    observed = {}
    monkeypatch.setattr(
        import_export_services,
        "get_ee_transfers_page_data",
        lambda **kwargs: observed.update(kwargs) or {"all_rows": []},
    )
    monkeypatch.setattr(import_export_services, "get_union_energy_systems_map", lambda: {})
    monkeypatch.setattr(
        import_export_services, "get_union_energy_system_display_order_map", lambda: {}
    )
    monkeypatch.setattr(import_export_services, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(import_export_services, "get_ee_default_start_year", lambda: 2017)
    monkeypatch.setattr(import_export_services, "load_ee_import_export_oes_values", lambda **kwargs: {})
    monkeypatch.setattr(
        import_export_services,
        "classify_ee_balance_generation_years",
        lambda years, _features: ([], years),
    )

    import_export_services.get_ee_import_export_page_data(
        start_year=2026,
        end_year=2026,
        filters={"union_energy_system_filter": 10},
    )

    assert observed["filters"] == {"union_energy_system_filter": 10}


def test_balance_rows_include_country_details_and_direction_totals(monkeypatch):
    sheets = [
        {
            "slug": "ural",
            "sheet_name": "Урал",
            "layout": "oes_standard",
            "territory": {"kind": "ues", "id": 10},
        },
        {
            "slug": "centr",
            "sheet_name": "Центр",
            "layout": "oes_standard",
            "territory": {"kind": "ues", "id": 20},
        },
    ]
    monkeypatch.setattr(
        page_services,
        "power_balance_station_list_query",
        lambda sheet, _sheets, _start, _end: {
            "union_energy_system_filter": sheet["territory"]["id"]
        },
    )

    def import_export_data(*, filters, **_kwargs):
        if filters["union_energy_system_filter"] in (10, [10]):
            rows = [
                {
                    "direction": "import",
                    "country_id": 1,
                    "country_name": "Беларусь",
                    "periods": {2026: Decimal("5")},
                },
                {
                    "direction": "import",
                    "country_id": 2,
                    "country_name": "Казахстан",
                    "periods": {2026: Decimal("7")},
                },
                {
                    "direction": "export",
                    "country_id": 1,
                    "country_name": "Беларусь",
                    "periods": {2026: Decimal("-4")},
                },
            ]
        else:
            rows = [
                {
                    "direction": "import",
                    "country_id": 3,
                    "country_name": "Монголия",
                    "periods": {2026: Decimal("3")},
                },
            ]
        return {"hierarchy": [{"rows": rows}]}

    monkeypatch.setattr(page_services, "get_ee_import_export_page_data", import_export_data)

    tables = page_services.build_ee_balance_tables(
        [2026],
        inputs={
            "ural": {"consumption": {2026: Decimal("100")}},
            "centr": {"consumption": {2026: Decimal("100")}},
        },
        sheets=sheets,
        rounding_digits=1,
    )

    ural_rows = {row["key"]: row for row in tables["ural"]["rows"]}
    assert ural_rows["ee_import_country_1"]["label"] == "Импорт ЭЭ – Беларусь"
    assert ural_rows["ee_import_country_2"]["label"] == "Импорт ЭЭ – Казахстан"
    assert ural_rows["ee_import_total"]["label"] == "Импорт ЭЭ, всего"
    assert ural_rows["ee_import_total"]["formula_tooltip"] == (
        "Сумма импортов электрической энергии"
    )
    assert ural_rows["ee_import_total"]["year_values"][2026] == "12"
    assert ural_rows["ee_import_total"]["css_class"] == ural_rows["gaes_charge"]["css_class"]
    assert ural_rows["ee_import_total"]["collapsible"] is True
    assert ural_rows["ee_import_country_1"]["parent_group_key"] == "ee_import_total"
    assert ural_rows["ee_import_country_1"]["is_group_child"] is True
    assert ural_rows["ee_export_country_1"]["label"] == "Экспорт ЭЭ – Беларусь"
    assert ural_rows["ee_export_total"]["label"] == "Экспорт ЭЭ, всего"
    assert ural_rows["ee_export_total"]["formula_tooltip"] == (
        "Сумма экспортов электрической энергии"
    )
    assert ural_rows["ee_export_total"]["year_values"][2026] == "4"
    assert ural_rows["ee_export_total"]["css_class"] == ural_rows["gaes_charge"]["css_class"]
    assert ural_rows["ee_export_total"]["collapsible"] is True
    assert ural_rows["ee_export_country_1"]["parent_group_key"] == "ee_export_total"
    assert ural_rows["ee_export_country_1"]["is_group_child"] is True

    # Итоги направлений и строки стран идут перед итогом потребности.
    ural_keys = [row["key"] for row in tables["ural"]["rows"]]
    assert ural_keys[ural_keys.index("demand_total") - 5 : ural_keys.index("demand_total")] == [
        "ee_export_total",
        "ee_export_country_1",
        "ee_import_total",
        "ee_import_country_1",
        "ee_import_country_2",
    ]
    demand_terms = ural_rows["demand_total"]["formula"]["terms"]
    assert {"row_key": "ee_export_total", "coeff": 1} in demand_terms
    assert {"row_key": "ee_import_total", "coeff": -1} in demand_terms
    # Итого потребность = потребление 100 + заряд ГАЭС 0 + экспорт 4 − импорт 12
    assert ural_rows["demand_total"]["year_values"][2026] == "92"

    centr_rows = {row["key"]: row for row in tables["centr"]["rows"]}
    assert centr_rows["ee_import_total"]["label"] == "Импорт ЭЭ, всего"
    assert centr_rows["ee_import_total"]["year_values"][2026] == "3"
    assert centr_rows["ee_import_country_3"]["label"] == "Импорт ЭЭ – Монголия"
    assert centr_rows["ee_import_country_3"]["year_values"][2026] == "3"
    centr_terms = centr_rows["demand_total"]["formula"]["terms"]
    assert {"row_key": "ee_export", "coeff": 1} in centr_terms
    assert {"row_key": "ee_import_total", "coeff": -1} in centr_terms
    assert centr_rows["demand_total"]["year_values"][2026] == "97"


def test_trade_totals_recalculate_from_country_values(monkeypatch):
    sheet = {
        "slug": "sibir", "layout": "oes_sibir",
        "territory": {"kind": "ues", "id": 4},
    }
    years = [2024, 2026, 2031]
    monkeypatch.setattr(
        page_services, "power_balance_station_list_query",
        lambda *_args: {"union_energy_system_filter": 4},
    )
    monkeypatch.setattr(
        page_services, "get_ee_import_export_page_data",
        lambda **_kwargs: {"hierarchy": [{"ues_id": 4, "rows": [
            {"direction": "import", "country_id": 1, "country_name": "Казахстан",
             "periods": {year: Decimal("5") for year in years}},
            {"direction": "import", "country_id": 2, "country_name": "Монголия",
             "periods": {year: Decimal("7") for year in years}},
            {"direction": "export", "country_id": 2, "country_name": "Монголия",
             "periods": {year: Decimal("-4") for year in years}},
        ]}]},
    )
    trade_rows, trade_inputs = page_services._ee_import_export_rows_for_sheet(
        sheet, [sheet], years, 1, [2026, 2031]
    )
    rows = page_services.build_ee_balance_rows("oes_sibir")
    rows.extend(trade_rows)
    page_services._add_import_export_to_demand_total(rows, trade_rows)
    tables = {"sibir": {"sheet": sheet, "rows": rows}}
    page_services.apply_power_balance_input_values(
        tables, {"sibir": {"consumption": {year: Decimal("100") for year in years},
                            **trade_inputs}}, rounding_digits=1,
    )
    page_services._attach_formula_tooltips(tables, {"sibir": sheet}, rounding_digits=1)
    page_services.evaluate_power_balance_tables(tables, years, rounding_digits=1)
    by_key = {row["key"]: row for row in rows}
    assert by_key["ee_import_total"]["formula_client"] == {
        "terms": [{"row_key": "ee_import_country_1"}, {"row_key": "ee_import_country_2"}]
    }
    assert by_key["ee_export_total"]["formula_client"] == {
        "terms": [{"row_key": "ee_export_country_2"}]
    }
    assert by_key["ee_import_country_1"]["editable_years"] == [2026, 2031]
    assert by_key["demand_total"]["year_values_raw"][2026] == Decimal("92")
    by_key["ee_import_country_1"]["year_values_raw"][2026] = Decimal("10.5")
    by_key["ee_export_country_2"]["year_values_raw"][2026] = Decimal("8.5")
    page_services.evaluate_power_balance_tables(tables, years, rounding_digits=1)
    assert by_key["ee_import_total"]["year_values_raw"][2026] == Decimal("17.5")
    assert by_key["ee_export_total"]["year_values_raw"][2026] == Decimal("8.5")
    assert by_key["demand_total"]["year_values_raw"][2026] == Decimal("91")
    assert by_key["surplus_deficit"]["year_values_raw"][2026] == Decimal("-91")
    assert by_key["demand_total"]["year_values_raw"][2024] == Decimal("92")
    assert by_key["demand_total"]["year_values_raw"][2031] == Decimal("92")
    by_key["ee_import_country_1"]["year_values_raw"][2026] = Decimal("0")
    page_services.evaluate_power_balance_tables(tables, years, rounding_digits=1)
    assert by_key["ee_import_total"]["year_values_raw"][2026] == Decimal("7")
    assert by_key["demand_total"]["year_values_raw"][2026] == Decimal("101.5")


def test_balance_formula_json_survives_html_attributes():
    import json
    from html.parser import HTMLParser
    from jinja2 import Environment, FileSystemLoader

    class RowParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.row_attrs = dict(attrs)

    env = Environment(loader=FileSystemLoader("app/templates"), autoescape=True)
    source, _, _ = env.loader.get_source(env, "energy_balance/ee_balance/ee_balance_table.html")
    row_key_at = source.index('data-row-key="{{ row.key }}"')
    opening_tag = source[source.rfind("<tr", 0, row_key_at):source.index(">", row_key_at) + 1]
    template = env.from_string(opening_tag)
    formulas = [
        {"terms": [{"row_key": "flow_in_oes_4_8"}, {"row_key": "country's", "coeff": -1}]},
        {"op": "ratio", "numerator": "generation_total", "denominator": "installed_total"},
        None,
    ]
    for formula in formulas:
        external = {"2026": "12.5", "2031": "-3.5"}
        html = template.render(row={
            "key": "total", "kind": "total", "formula_client": formula,
            "formula_ext_raw": external,
        })
        parser = RowParser()
        parser.feed(html)
        assert json.loads(parser.row_attrs["data-formula"]) == formula
        assert json.loads(parser.row_attrs["data-ext-raw"]) == external

