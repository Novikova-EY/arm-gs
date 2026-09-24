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
from app.energy_balance.services.ee_balance_generation_services import (
    hydro_year_for_balance_sheet,
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
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.overlay_tes_forecast_generation_inputs",
        lambda inputs, sheets=None, years=None: inputs or {},
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
    assert "generation_ses" in keys
    assert "generation_ves" in keys
    assert "generation_total" in keys
    assert "flow_in" in keys
    assert "flow_out" in keys
    assert "installed_total" in keys
    assert "installed_aes" in keys
    assert "installed_ses_ves" in keys
    assert "installed_ses" in keys
    assert "installed_ves" in keys
    assert "chiim_total" in keys
    assert "chiim_aes" in keys
    assert "chiim_ses_ves" in keys
    assert "chiim_ses" in keys
    assert "chiim_ves" in keys
    installed_start = keys.index("installed_total")
    chiim_start = keys.index("chiim_total")
    assert keys[installed_start - 1] == "surplus_deficit_with_flow"
    assert chiim_start == keys.index("installed_ves") + 1
    assert keys.index("generation_ses") == keys.index("generation_ses_ves") + 1
    assert keys.index("generation_ves") == keys.index("generation_ses") + 1
    assert keys.index("chiim_ses") == keys.index("chiim_ses_ves") + 1
    assert keys.index("chiim_ves") == keys.index("chiim_ses") + 1
    gen_ses_ves = next(row for row in rows if row["key"] == "generation_ses_ves")
    gen_ses = next(row for row in rows if row["key"] == "generation_ses")
    assert gen_ses_ves.get("collapsible") is True
    assert gen_ses.get("is_group_child") is True
    assert gen_ses.get("parent_group_key") == "generation_ses_ves"
    assert gen_ses["label"] == "СЭС"
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
                "generation_ses": {2026: "10"},
                "generation_ves": {2026: "5"},
                "installed_aes": {2026: 40},
                "installed_ges": {2026: 10},
                "installed_gaes": {2026: 5},
                "installed_tes": {2026: 30},
                "installed_snee": {2026: 2},
                "installed_ses": {2026: 2},
                "installed_ves": {2026: 1},
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


def test_selected_eu_plan_tes_equals_consumption_minus_other_generation(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        lambda: {2024: "факт", 2026: "план"},
    )
    residual_inputs = {
        "consumption": {2024: "100", 2026: "200"},
        "generation_aes": {2024: "1", 2026: "2"},
        "generation_ges": {2024: "3", 2026: "4"},
        "generation_gaes": {2024: "0", 2026: "0"},
        "generation_tes": {2024: "80", 2026: "999"},
        "generation_snee": {2024: "5", 2026: "6"},
        "generation_ses": {2024: "7", 2026: "8"},
        "generation_ves": {2024: "9", 2026: "10"},
    }
    sheets = [
        {
            "slug": "eu-255",
            "sheet_name": "Анадырский энергорайон",
            "layout": "oes_standard",
            "territory": {"kind": "eu", "id": 255, "name": "Анадырский энергорайон"},
        },
        {
            "slug": "eu-256",
            "sheet_name": "Центральный энергорайон Сахалинской области",
            "layout": "oes_standard",
            "territory": {
                "kind": "eu",
                "id": 256,
                "name": "Центральный энергорайон Сахалинской области",
            },
        },
        {
            "slug": "eu-254",
            "sheet_name": "Чаун-Билибинский энергорайон",
            "layout": "oes_standard",
            "territory": {"kind": "eu", "id": 254, "name": "Чаун-Билибинский энергорайон"},
        },
        {
            "slug": "eu-258",
            "sheet_name": "Центральный энергорайон Камчатского края",
            "layout": "oes_standard",
            "territory": {
                "kind": "eu",
                "id": 258,
                "name": "Центральный энергорайон Камчатского края",
            },
        },
        {
            "slug": "eu-257",
            "sheet_name": "Центральный энергорайон Магаданской области",
            "layout": "oes_standard",
            "territory": {
                "kind": "eu",
                "id": 257,
                "name": "Центральный энергорайон Магаданской области",
            },
        },
    ]
    tables = build_ee_balance_tables(
        [2024, 2026],
        inputs={
            "eu-255": dict(residual_inputs),
            "eu-256": dict(residual_inputs),
            "eu-254": dict(residual_inputs),
            "eu-258": dict(residual_inputs),
            "eu-257": dict(residual_inputs),
        },
        rounding_digits=1,
        sheets=sheets,
    )
    for slug in ("eu-255", "eu-256", "eu-254", "eu-258"):
        assert _row_display(tables, slug, "generation_tes", 2024) == "80"
        assert _row_display(tables, slug, "generation_tes", 2026) == "170"
        assert _row_display(tables, slug, "generation_total", 2026) == "200"
        tes = next(row for row in tables[slug]["rows"] if row["key"] == "generation_tes")
        assert tes["formula_tooltip"].startswith("В прогнозном периоде: ТЭС =")
        assert "Потребление электрической энергии" in tes["formula_tooltip"]
        assert "СЭС" in tes["formula_tooltip"]
        assert "ВЭС" in tes["formula_tooltip"]
    assert _row_display(tables, "eu-257", "generation_tes", 2026) == "999"
    magadan_tes = next(
        row for row in tables["eu-257"]["rows"] if row["key"] == "generation_tes"
    )
    assert "помесячного расчёта" in magadan_tes["formula_tooltip"]


def test_plan_tes_from_consumption_is_not_negative_when_consumption_unset(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        lambda: {2026: "план"},
    )
    sheets = [
        {
            "slug": "eu-254",
            "sheet_name": "Чаун-Билибинский энергорайон",
            "layout": "oes_standard",
        }
    ]
    tables = build_ee_balance_tables(
        [2026],
        inputs={
            "eu-254": {
                "consumption": {2026: "0"},
                "generation_aes": {2026: "350"},
                "generation_tes": {2026: "48"},
            }
        },
        rounding_digits=1,
        sheets=sheets,
    )
    assert _row_display(tables, "eu-254", "generation_tes", 2026) == "0"
    assert _row_display(tables, "eu-254", "generation_aes", 2026) == "350"


def test_anadyr_plan_tes_uses_ses_ves_parent_when_children_empty(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.get_ee_balance_year_features",
        lambda: {2026: "план"},
    )
    sheets = [
        {
            "slug": "eu-255",
            "sheet_name": "Анадырский энергорайон",
            "layout": "oes_standard",
        }
    ]
    tables = build_ee_balance_tables(
        [2026],
        inputs={
            "eu-255": {
                "consumption": {2026: "100"},
                "generation_aes": {2026: "10"},
                "generation_tes": {2026: "1"},
                "generation_ses_ves": {2026: "15"},
            }
        },
        rounding_digits=1,
        sheets=sheets,
    )
    assert _row_display(tables, "eu-255", "generation_tes", 2026) == "75"


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
    ses_ves = next(
        row for row in tables["centr"]["rows"] if row["key"] == "generation_ses_ves"
    )
    ses = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_ses")
    ves = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_ves")
    tes = next(row for row in tables["centr"]["rows"] if row["key"] == "generation_tes")
    ees_snee = next(
        row for row in tables["ees-rossii"]["rows"] if row["key"] == "generation_snee"
    )
    assert snee["editable_values"] is True
    assert snee["editable_years"] == [2026]
    assert snee["value_save_kind"] == "generation"
    assert ses_ves.get("formula")
    assert ses_ves.get("editable_values") is not True
    assert ses.get("editable_values") is not True
    assert ves.get("editable_values") is not True
    assert tes.get("editable_values") is not True
    assert ees_snee.get("formula")
    assert ees_snee.get("editable_values") is not True
    installed_ses = next(
        row for row in tables["centr"]["rows"] if row["key"] == "installed_ses"
    )
    assert installed_ses.get("editable_values") is not True


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


def test_hydro_year_for_balance_sheet_average_only_for_five_oes():
    sheets = [
        {
            "slug": "centr",
            "group": "oes",
            "layout": "oes_standard",
            "sheet_name": "ОЭС Центра",
            "territory": {"kind": "ues", "id": 2, "name": "Центр"},
        },
        {
            "slug": "sibir",
            "group": "oes",
            "layout": "oes_sibir",
            "sheet_name": "ОЭС Сибири",
            "territory": {"kind": "ues", "id": 6, "name": "Сибирь"},
        },
        {
            "slug": "ees-rossii",
            "group": "ees",
            "layout": "ees_rossii",
            "sheet_name": "ЕЭС России",
        },
        {
            "slug": "1-sz-ees",
            "group": "sz",
            "layout": "sz1",
            "sheet_name": "1-я СЗ ЕЭС",
        },
        {
            "slug": "eu-258",
            "group": "eu",
            "layout": "oes_standard",
            "sheet_name": "Энергорайон",
            "parent_slug": "oes-2",
        },
        {
            "slug": "eu-101",
            "group": "eu",
            "layout": "oes_standard",
            "sheet_name": "Центральный энергорайон Камчатского края",
            "parent_slug": "sibir",
        },
    ]
    by_slug = {item["slug"]: item for item in sheets}
    assert hydro_year_for_balance_sheet(by_slug["centr"], sheets) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {
            "slug": "severo-zapad",
            "group": "oes",
            "layout": "oes_standard",
            "sheet_name": "ОЭС Северо-Запада",
        },
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {
            "slug": "srednyaya-volga",
            "group": "oes",
            "sheet_name": "ОЭС Волги",
        },
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {"slug": "ural", "group": "oes", "sheet_name": "ОЭС Урала"},
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(
        {"slug": "yug", "group": "oes", "layout": "oes_yug", "sheet_name": "ОЭС Юга"},
        sheets,
    ) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(by_slug["sibir"], sheets) == HYDRO_YEAR_LOW
    assert hydro_year_for_balance_sheet(by_slug["ees-rossii"], sheets) is None
    assert hydro_year_for_balance_sheet(by_slug["1-sz-ees"], sheets) is None
    assert hydro_year_for_balance_sheet(by_slug["eu-258"], sheets) == HYDRO_YEAR_AVERAGE
    assert hydro_year_for_balance_sheet(by_slug["eu-101"], sheets) == HYDRO_YEAR_LOW


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


def test_table_context_hydro_year_in_title_without_buttons(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_power_balance_installed_capacity_inputs",
        lambda years, sheets=None: {
            "severo-zapad": {"installed_ges": {2026: 100, 2027: 0}},
            "sibir": {"installed_ges": {2026: 80, 2027: 0}},
            "ees-rossii": {"installed_ges": {2026: 180, 2027: 0}},
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
        context_nw = build_ee_balance_table_context(
            "severo-zapad", hydro_year=HYDRO_YEAR_LOW
        )
        context_sibir = build_ee_balance_table_context("sibir")
        context_ees = build_ee_balance_table_context("ees-rossii")
    assert context_nw is not None
    assert context_sibir is not None
    assert context_ees is not None
    assert context_nw["show_hydro_year_nav"] is False
    assert context_nw["hydro_year_buttons"] == []
    assert context_nw["hydro_year"] == HYDRO_YEAR_AVERAGE
    assert context_nw["page_title"] == (
        "Баланс электрической энергии Северо-Запад (средневодный год)"
    )
    assert context_sibir["hydro_year"] == HYDRO_YEAR_LOW
    assert context_sibir["page_title"] == (
        "Баланс электрической энергии Сибирь (маловодный год)"
    )
    assert context_ees["hydro_year"] is None
    assert context_ees["page_title"] == "Баланс электрической энергии ЕЭС России"


def test_table_context_does_not_pass_global_hydro_year_to_generation(monkeypatch):
    captured: dict[str, object] = {}

    def fake_gen(years, sheets=None, hydro_year=None):
        captured["called"] = True
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
    assert captured["called"] is True
    assert captured["hydro_year"] is None


def test_sheet_nav_template_has_no_hydro_year_buttons():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    def _url_for(endpoint, **kwargs):
        slug = kwargs.get("slug", "")
        if endpoint == "energy_balance_bp.power_balance_table":
            return "/energy_balance/power_balance/{slug}/".format(slug=slug)
        return "/energy_balance/ee_balance/{slug}/".format(slug=slug)

    env.globals["url_for"] = _url_for
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
    assert "ОЭС Северо-Запада (средневодный год)" not in html
    assert "ОЭС Северо-Запада (маловодный год)" not in html
    assert "hydro_year=" not in html
    assert "Вариант водохозяйственного года" not in html
    assert "Балансы мощности" in html
    assert "Балансы ЭЭ" not in html
    assert "Балансы ЭМ" not in html
    assert "/energy_balance/power_balance/severo-zapad/" in html
    assert html.count('class="btn btn-secondary fs-5 text-nowrap flex-shrink-0"') == 1
    oes_at = html.find("ОЭС Северо-Запада")
    power_at = html.find("Балансы мощности")
    assert 0 <= oes_at < power_at


def test_tites_east_child_buttons_render_without_hydro_year():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=True,
    )
    def _url_for(endpoint, **kwargs):
        slug = kwargs.get("slug", "")
        if endpoint == "energy_balance_bp.power_balance_table":
            return "/energy_balance/power_balance/{slug}/".format(slug=slug)
        return "/energy_balance/ee_balance/{slug}/".format(slug=slug)

    env.globals["url_for"] = _url_for
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
    power_at = html.find("Балансы мощности")
    kamchatka_at = html.find("Центральный энергорайон Камчатского края")
    chaun_at = html.find("Чаун-Билибинский энергорайон")
    anadyr_at = html.find("Анадырский энергорайон")
    assert 0 < power_at < kamchatka_at < chaun_at < anadyr_at
    assert "Камчатская ЭС (средневодный год)" not in html
    assert "hydro_year=" not in html
    assert "Балансы ЭЭ" not in html
    assert "/energy_balance/power_balance/eu-104/" in html
    assert "/energy_balance/ee_balance/eu-101/" in html
    assert "/energy_balance/ee_balance/eu-104/" in html
    assert "/energy_balance/ee_balance/eu-105/" in html
    assert html.count("btn-primary") >= 2


def test_ees_and_sz1_generation_sums_mixed_hydro_years():
    years = [2026]
    tables = build_ee_balance_tables(
        years,
        inputs={
            "severo-zapad": {"generation_ges": {2026: 10}},
            "centr": {"generation_ges": {2026: 20}},
            "srednyaya-volga": {"generation_ges": {2026: 4}},
            "yug": {"generation_ges": {2026: 5}},
            "ural": {"generation_ges": {2026: 6}},
            "sibir": {"generation_ges": {2026: 7}},
            "2-sz-ees-vostok": {"generation_ges": {2026: 8}},
            "kaliningradskaya-sz-ees": {"generation_ges": {2026: 3}},
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "ees-rossii", "generation_ges", 2026) == "60"
    assert _row_display(tables, "1-sz-ees", "generation_ges", 2026) == "49"


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
