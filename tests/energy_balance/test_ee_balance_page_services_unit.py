# -*- coding: utf-8 -*-
"""Юнит-тесты каркаса страниц расчета балансов электрической энергии."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.energy_balance.services.ee_balance_page_services import (
    EE_BALANCE_UNIT,
    HYDRO_YEAR_AVERAGE,
    HYDRO_YEAR_LOW,
    build_ee_balance_rows,
    build_ee_balance_table_context,
    build_ee_balance_tables,
    format_ee_balance_page_title,
    get_ee_balance_sheet,
    get_ee_balance_sheets,
    resolve_ee_balance_hydro_year,
    sheet_has_ges_or_gaes_capacity,
)
from app.energy_balance.services.power_balance_page_services import (
    GROUP_EES,
    GROUP_OES,
    GROUP_SZ,
    POWER_BALANCE_SHEETS,
    group_power_balance_sheets,
)


@pytest.fixture(autouse=True)
def _stable_station_types_and_no_db_load(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_installed_capacity_services.get_station_type_list_full",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_generation_inputs",
        lambda years, sheets=None, hydro_year=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_consumption_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_gaes_charge_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_custom_flows",
        lambda sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_export_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.attach_balance_sheet_notes",
        lambda tables, kind: None,
    )


def test_ee_balance_sheets_reuse_power_catalog_with_energy_titles():
    sheets = get_ee_balance_sheets()
    names = [sheet["sheet_name"] for sheet in sheets]
    assert names == [
        "ЕЭС России",
        "1-я СЗ ЕЭС",
        "2-я СЗ ЕЭС (ОЭС Востока)",
        "Калининградская СЗ ЕЭС",
        "Северо-Запад",
        "Центр",
        "Средняя Волга",
        "Юг",
        "Урал",
        "Сибирь",
    ]
    groups = group_power_balance_sheets(sheets)
    assert [item["group"] for item in groups] == [GROUP_EES, GROUP_SZ, GROUP_OES]
    for sheet in sheets:
        assert sheet["title"] == f"Баланс электрической энергии {sheet['sheet_name']}"
        assert sheet["unit"] == EE_BALANCE_UNIT


def test_get_ee_balance_sheet_unknown_returns_none():
    assert get_ee_balance_sheet("unknown") is None
    assert get_ee_balance_sheet("sibir")["table_number"] == 10


@pytest.mark.parametrize("sheet", list(POWER_BALANCE_SHEETS))
def test_each_layout_has_energy_rows_and_units(sheet):
    rows = build_ee_balance_rows(sheet["layout"])
    keys = [row["key"] for row in rows]
    assert keys
    assert len(keys) == len(set(keys))
    assert "consumption" in keys
    assert "gaes_charge" in keys
    assert keys[keys.index("consumption") + 1] == "gaes_charge"
    gaes_charge = next(row for row in rows if row["key"] == "gaes_charge")
    assert gaes_charge["label"] == "Заряд ГАЭС"
    assert gaes_charge["unit"] == EE_BALANCE_UNIT
    assert "export" in keys
    export = next(row for row in rows if row["key"] == "export")
    assert export["editable_values"] is True
    assert not export.get("formula")
    assert "generation_aes" in keys
    assert "generation_ses_ves" in keys
    assert "generation_total" in keys
    assert "flow_in" in keys
    assert "flow_out" in keys
    assert "installed_total" in keys
    assert "installed_aes" in keys
    assert "installed_ses_ves" in keys
    assert "chiim_total" in keys
    assert "chiim_aes" in keys
    assert "chiim_ses_ves" in keys
    installed_start = keys.index("installed_total")
    chiim_start = keys.index("chiim_total")
    assert keys[installed_start - 1] == "surplus_deficit_with_flow"
    assert chiim_start == keys.index("installed_ses_ves") + 1
    assert all(k.startswith("installed_") for k in keys[installed_start:chiim_start])
    assert all(k.startswith("chiim_") for k in keys[chiim_start:])
    energy_rows = [
        row
        for row in rows
        if not str(row["key"]).startswith("installed_")
        and not str(row["key"]).startswith("chiim_")
    ]
    capacity_rows = [row for row in rows if str(row["key"]).startswith("installed_")]
    chiim_rows = [row for row in rows if str(row["key"]).startswith("chiim_")]
    assert all(row["unit"] == EE_BALANCE_UNIT for row in energy_rows)
    assert all(row["unit"] == "МВт" for row in capacity_rows)
    assert all(row["unit"] == "ч." for row in chiim_rows)
    assert "demand_max" not in keys
    installed_total = next(row for row in rows if row["key"] == "installed_total")
    chiim_total = next(row for row in rows if row["key"] == "chiim_total")
    chiim_aes = next(row for row in rows if row["key"] == "chiim_aes")
    assert installed_total["kind"] == "total"
    assert chiim_total["kind"] == "total"
    assert chiim_total["label"] == "ЧЧИУМ"
    assert chiim_aes["rounding_digits"] == -1
    assert "Выработка электрической энергии АЭС" in (chiim_aes.get("formula") or {}).get("tooltip", "")
    assert "Установленная мощность АЭС" in (chiim_aes.get("formula") or {}).get("tooltip", "")


def test_unknown_layout_raises():
    with pytest.raises(KeyError):
        build_ee_balance_rows("missing")


def _row_display(tables, slug, key, year):
    row = next(item for item in tables[slug]["rows"] if item["key"] == key)
    return row["year_values"][year]


def test_oes_energy_formulas():
    years = [2026]
    tables = build_ee_balance_tables(
        years,
        inputs={
            "centr": {
                "consumption": {2026: "100"},
                "gaes_charge": {2026: "5"},
                "export": {2026: "10"},
                "generation_aes": {2026: "40"},
                "generation_ges": {2026: "20"},
                "generation_gaes": {2026: "5"},
                "generation_tes": {2026: "50"},
                "generation_snee": {2026: "0"},
                "generation_ses_ves": {2026: "15"},
                "installed_aes": {2026: 40},
                "installed_ges": {2026: 10},
                "installed_gaes": {2026: 5},
                "installed_tes": {2026: 30},
                "installed_snee": {2026: 2},
                "installed_ses_ves": {2026: 3},
            }
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "centr", "demand_total", 2026) == "115"
    assert _row_display(tables, "centr", "gaes_charge", 2026) == "5"
    assert _row_display(tables, "centr", "generation_total", 2026) == "130"
    assert _row_display(tables, "centr", "coverage_total", 2026) == "130"
    assert _row_display(tables, "centr", "surplus_deficit", 2026) == "15"
    assert _row_display(tables, "centr", "installed_total", 2026) == "90"
    aes = next(row for row in tables["centr"]["rows"] if row["key"] == "installed_aes")
    total = next(row for row in tables["centr"]["rows"] if row["key"] == "installed_total")
    assert aes["unit"] == "МВт"
    assert total["unit"] == "МВт"
    assert _row_display(tables, "centr", "chiim_aes", 2026) == "1 000"
    assert _row_display(tables, "centr", "chiim_ges", 2026) == "2 000"
    assert _row_display(tables, "centr", "chiim_gaes", 2026) == "1 000"
    assert _row_display(tables, "centr", "chiim_tes", 2026) == "1 667"
    assert _row_display(tables, "centr", "chiim_ses_ves", 2026) == "5 000"
    assert _row_display(tables, "centr", "chiim_total", 2026) == "1 444"
    chiim_aes = next(row for row in tables["centr"]["rows"] if row["key"] == "chiim_aes")
    chiim_total = next(row for row in tables["centr"]["rows"] if row["key"] == "chiim_total")
    assert chiim_aes["unit"] == "ч."
    assert chiim_total["unit"] == "ч."
    assert chiim_aes["year_values_raw"][2026] == 1000
    assert _row_display(tables, "centr", "chiim_snee", 2026) == "0"
    assert "Выработка электрической энергии АЭС" in chiim_aes["formula_tooltip"]
    assert "Установленная мощность АЭС" in chiim_aes["formula_tooltip"]


def test_oes_plan_years_make_snee_and_ses_ves_generation_editable(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        lambda years, year_features=None: ([], [2026]),
    )
    tables = build_ee_balance_tables(
        [2026],
        inputs={
            "centr": {
                "generation_snee": {2026: "1"},
                "generation_ses_ves": {2026: "2"},
            }
        },
        rounding_digits=1,
    )
    snee = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_snee")
    ses = next(
        row for row in tables["centr"]["rows"] if row["key"] == "generation_ses_ves"
    )
    tes = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_tes")
    ees_snee = next(
        row for row in tables["ees-rossii"]["rows"] if row["key"] == "generation_snee"
    )
    assert snee["editable_values"] is True
    assert snee["editable_years"] == [2026]
    assert snee["value_save_kind"] == "generation"
    assert ses["editable_values"] is True
    assert tes.get("editable_values") is not True
    assert ees_snee.get("formula")
    assert ees_snee.get("editable_values") is not True


def test_table_context_for_known_slug():
    with patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_columns",
        return_value=[2026, 2027],
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        return_value={2026: "Отчет", 2027: "План"},
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_filter_year_list",
        return_value=[2026, 2027],
    ):
        context = build_ee_balance_table_context("centr")
    assert context is not None
    assert context["sheet"]["sheet_name"] == "Центр"
    assert context["page_title"] == "Баланс электрической энергии Центр"
    assert context["years"] == [2026, 2027]
    consumption = next(row for row in context["rows"] if row["key"] == "consumption")
    export = next(row for row in context["rows"] if row["key"] == "export")
    installed_total = next(row for row in context["rows"] if row["key"] == "installed_total")
    assert consumption["unit"] == EE_BALANCE_UNIT
    assert export["editable_values"] is True
    assert installed_total["unit"] == "МВт"
    assert installed_total["label"] == "Установленная мощность"
    chiim_total = next(row for row in context["rows"] if row["key"] == "chiim_total")
    assert chiim_total["unit"] == "ч."
    assert chiim_total["label"] == "ЧЧИУМ"
    assert context["show_hydro_year_nav"] is False
    assert context["hydro_year"] is None
    assert context["hydro_year_buttons"] == []


def test_sheet_has_ges_or_gaes_capacity_true_when_ges_positive_in_one_year():
    rows = [
        {"key": "installed_ges", "year_values_raw": {2026: 0, 2027: 12.5}},
        {"key": "installed_gaes", "year_values_raw": {2026: 0, 2027: 0}},
    ]
    assert sheet_has_ges_or_gaes_capacity(rows, [2026, 2027]) is True


def test_sheet_has_ges_or_gaes_capacity_true_when_only_gaes_positive():
    rows = [
        {"key": "installed_ges", "year_values_raw": {2026: 0}},
        {"key": "installed_gaes", "year_values_raw": {2026: 1}},
    ]
    assert sheet_has_ges_or_gaes_capacity(rows, [2026]) is True


def test_sheet_has_ges_or_gaes_capacity_false_when_zero_or_empty():
    rows = [
        {"key": "installed_ges", "year_values_raw": {2026: 0}},
        {"key": "installed_gaes", "year_values_raw": {2026: None}},
        {"key": "installed_aes", "year_values_raw": {2026: 100}},
    ]
    assert sheet_has_ges_or_gaes_capacity(rows, [2026]) is False
    assert sheet_has_ges_or_gaes_capacity(rows, []) is False
    assert sheet_has_ges_or_gaes_capacity(None, [2026]) is False


def test_resolve_ee_balance_hydro_year_defaults_to_average():
    assert resolve_ee_balance_hydro_year(None) == HYDRO_YEAR_AVERAGE
    assert resolve_ee_balance_hydro_year("average") == HYDRO_YEAR_AVERAGE
    assert resolve_ee_balance_hydro_year("low") == HYDRO_YEAR_LOW
    assert resolve_ee_balance_hydro_year("маловодный") == HYDRO_YEAR_LOW


def test_format_ee_balance_page_title_appends_hydro_year():
    base = "Баланс электрической энергии Северо-Запад"
    assert format_ee_balance_page_title(base) == base
    assert format_ee_balance_page_title(base, hydro_year=None) == base
    assert (
        format_ee_balance_page_title(base, hydro_year=HYDRO_YEAR_AVERAGE)
        == "Баланс электрической энергии Северо-Запад (средневодный год)"
    )
    assert (
        format_ee_balance_page_title(base, hydro_year=HYDRO_YEAR_LOW)
        == "Баланс электрической энергии Северо-Запад (маловодный год)"
    )
    already = "Баланс электрической энергии Северо-Запад (маловодный год)"
    assert format_ee_balance_page_title(already, hydro_year=HYDRO_YEAR_LOW) == already


def test_table_context_hydro_year_nav_when_ges_capacity(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {
            "severo-zapad": {"installed_ges": {2026: 100, 2027: 0}}
        },
    )
    with patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_columns",
        return_value=[2026, 2027],
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        return_value={2026: "Отчет", 2027: "План"},
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_filter_year_list",
        return_value=[2026, 2027],
    ):
        context_avg = build_ee_balance_table_context("severo-zapad")
        context_low = build_ee_balance_table_context(
            "severo-zapad", hydro_year=HYDRO_YEAR_LOW
        )
    assert context_avg is not None
    assert context_low is not None
    assert context_avg["show_hydro_year_nav"] is True
    assert context_avg["hydro_year"] == HYDRO_YEAR_AVERAGE
    assert context_low["hydro_year"] == HYDRO_YEAR_LOW
    assert context_avg["page_title"] == (
        "Баланс электрической энергии Северо-Запад (средневодный год)"
    )
    assert context_low["page_title"] == (
        "Баланс электрической энергии Северо-Запад (маловодный год)"
    )
    assert [item["label"] for item in context_avg["hydro_year_buttons"]] == [
        "Северо-Запад (средневодный год)",
        "Северо-Запад (маловодный год)",
    ]
    assert [row["key"] for row in context_avg["rows"]] == [
        row["key"] for row in context_low["rows"]
    ]
    assert [row.get("year_values_raw") for row in context_avg["rows"]] == [
        row.get("year_values_raw") for row in context_low["rows"]
    ]


def test_table_context_passes_hydro_year_to_generation(monkeypatch):
    captured: dict[str, object] = {}

    def fake_gen(years, sheets=None, hydro_year=None):
        captured["hydro_year"] = hydro_year
        return {}

    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_generation_inputs",
        fake_gen,
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {
            "severo-zapad": {"installed_ges": {2026: 100, 2027: 0}}
        },
    )
    with patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_columns",
        return_value=[2026, 2027],
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        return_value={2026: "Отчет", 2027: "План"},
    ), patch(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_filter_year_list",
        return_value=[2026, 2027],
    ):
        context = build_ee_balance_table_context(
            "severo-zapad", hydro_year=HYDRO_YEAR_LOW
        )
    assert context is not None
    assert captured["hydro_year"] == HYDRO_YEAR_LOW


def test_hydro_year_nav_template_renders_second_row():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    env.globals["url_for"] = lambda endpoint, **kwargs: (
        "/energy_balance/ee_balance/{slug}/?hydro_year={hydro}".format(
            slug=kwargs.get("slug", ""),
            hydro=kwargs.get("hydro_year") or "",
        )
    )
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug="severo-zapad",
        sheet_groups=[
            {
                "group": "oes",
                "sheets": [
                    {"slug": "severo-zapad", "sheet_name": "ОЭС Северо-Запада"},
                    {"slug": "centr", "sheet_name": "ОЭС Центра"},
                ],
            }
        ],
        start_year=2026,
        end_year=2031,
        rounding_digits=1,
        show_hydro_year_nav=True,
        hydro_year=HYDRO_YEAR_AVERAGE,
        hydro_year_buttons=[
            {
                "key": HYDRO_YEAR_AVERAGE,
                "label": "ОЭС Северо-Запада (средневодный год)",
            },
            {"key": HYDRO_YEAR_LOW, "label": "ОЭС Северо-Запада (маловодный год)"},
        ],
    )
    assert "ОЭС Северо-Запада (средневодный год)" in html
    assert "ОЭС Северо-Запада (маловодный год)" in html
    assert 'hydro_year=average' in html
    assert 'hydro_year=low' in html
    assert html.count("btn-primary") >= 2

    hidden = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug="kaliningradskaya-sz-ees",
        sheet_groups=[
            {
                "group": "sz",
                "sheets": [
                    {
                        "slug": "kaliningradskaya-sz-ees",
                        "sheet_name": "Калининградская СЗ",
                    }
                ],
            }
        ],
        show_hydro_year_nav=False,
        hydro_year=None,
        hydro_year_buttons=[],
    )
    assert "средневодный год" not in hidden
    assert "маловодный год" not in hidden


def test_tites_east_child_buttons_render_before_hydro_year():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    env.globals["url_for"] = lambda endpoint, **kwargs: (
        "/energy_balance/ee_balance/{slug}/?hydro_year={hydro}".format(
            slug=kwargs.get("slug", ""),
            hydro=kwargs.get("hydro_year") or "",
        )
    )
    html = env.get_template("energy_balance/ee_balance/_sheet_nav.html").render(
        current_slug="eu-104",
        first_row_active_slug="oes-15",
        sheet_groups=[
            {
                "group": "oes",
                "sheets": [
                    {
                        "slug": "oes-15",
                        "sheet_name": "ТИТЭС Востока",
                        "first_child_slug": "eu-101",
                    }
                ],
            }
        ],
        tites_east_child_sheets=[
            {"slug": "eu-101", "sheet_name": "Центральный энергорайон Камчатского края"},
            {"slug": "eu-104", "sheet_name": "Чаун-Билибинский энергорайон"},
            {"slug": "eu-105", "sheet_name": "Анадырский энергорайон"},
        ],
        start_year=2026,
        end_year=2031,
        rounding_digits=1,
        show_hydro_year_nav=True,
        hydro_year=HYDRO_YEAR_AVERAGE,
        hydro_year_buttons=[
            {"key": HYDRO_YEAR_AVERAGE, "label": "Камчатская ЭС (средневодный год)"},
            {"key": HYDRO_YEAR_LOW, "label": "Камчатская ЭС (маловодный год)"},
        ],
    )
    kamchatka_at = html.find("Центральный энергорайон Камчатского края")
    chaun_at = html.find("Чаун-Билибинский энергорайон")
    anadyr_at = html.find("Анадырский энергорайон")
    hydro_at = html.find("Камчатская ЭС (средневодный год)")
    assert 0 < kamchatka_at < chaun_at < anadyr_at < hydro_at
    assert "/energy_balance/ee_balance/eu-101/" in html
    assert "/energy_balance/ee_balance/eu-104/" in html
    assert "/energy_balance/ee_balance/eu-105/" in html
    assert html.count("btn-primary") >= 3


def test_ees_and_sz1_installed_capacity_cross_sheet_formulas():
    years = [2026]
    tables = build_ee_balance_tables(
        years,
        inputs={
            "severo-zapad": {"installed_aes": {2026: 10}},
            "centr": {"installed_aes": {2026: 20}},
            "srednyaya-volga": {"installed_aes": {2026: 4}},
            "yug": {"installed_aes": {2026: 5}},
            "ural": {"installed_aes": {2026: 6}},
            "sibir": {"installed_aes": {2026: 7}},
            "2-sz-ees-vostok": {"installed_aes": {2026: 8}},
            "kaliningradskaya-sz-ees": {"installed_aes": {2026: 3}},
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "ees-rossii", "installed_aes", 2026) == "60"
    assert _row_display(tables, "1-sz-ees", "installed_aes", 2026) == "49"
    ees_aes = next(
        row for row in tables["ees-rossii"]["rows"] if row["key"] == "installed_aes"
    )
    assert ees_aes["unit"] == "МВт"
    assert "Северо-Запад" in ees_aes["formula_tooltip"]
    assert "2-я СЗ ЕЭС" in ees_aes["formula_tooltip"]


def test_ees_chiim_uses_aggregated_generation_and_capacity():
    years = [2026]
    tables = build_ee_balance_tables(
        years,
        inputs={
            "severo-zapad": {"generation_aes": {2026: 10}, "installed_aes": {2026: 10}},
            "centr": {"generation_aes": {2026: 20}, "installed_aes": {2026: 20}},
            "srednyaya-volga": {"generation_aes": {2026: 4}, "installed_aes": {2026: 4}},
            "yug": {"generation_aes": {2026: 5}, "installed_aes": {2026: 5}},
            "ural": {"generation_aes": {2026: 6}, "installed_aes": {2026: 6}},
            "sibir": {"generation_aes": {2026: 7}, "installed_aes": {2026: 7}},
            "2-sz-ees-vostok": {"generation_aes": {2026: 8}, "installed_aes": {2026: 8}},
            "kaliningradskaya-sz-ees": {"generation_aes": {2026: 3}, "installed_aes": {2026: 3}},
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "ees-rossii", "generation_aes", 2026) == "60"
    assert _row_display(tables, "ees-rossii", "installed_aes", 2026) == "60"
    assert _row_display(tables, "ees-rossii", "chiim_aes", 2026) == "1 000"
    assert _row_display(tables, "1-sz-ees", "chiim_aes", 2026) == "1 000"
