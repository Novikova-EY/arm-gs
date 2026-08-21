# -*- coding: utf-8 -*-
"""Юнит-тесты каркаса страниц расчета балансов электрической энергии."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.energy_balance.services.ee_balance_page_services import (
    EE_BALANCE_UNIT,
    build_ee_balance_rows,
    build_ee_balance_table_context,
    build_ee_balance_tables,
    get_ee_balance_sheet,
    get_ee_balance_sheets,
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
        lambda years, sheets=None: {},
    )
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_page_services.load_ee_balance_consumption_inputs",
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
    assert "export" in keys
    export = next(row for row in rows if row["key"] == "export")
    assert export["editable_values"] is True
    assert not export.get("formula")
    assert "generation_aes" in keys
    assert "generation_ses_ves" in keys
    assert "generation_total" in keys
    assert "flow_in" in keys
    assert "flow_out" in keys
    assert all(row["unit"] == EE_BALANCE_UNIT for row in rows)
    assert "demand_max" not in keys
    assert "installed_total" not in keys


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
                "export": {2026: "10"},
                "generation_aes": {2026: "40"},
                "generation_ges": {2026: "20"},
                "generation_gaes": {2026: "5"},
                "generation_tes": {2026: "50"},
                "generation_snee": {2026: "0"},
                "generation_ses_ves": {2026: "15"},
            }
        },
        rounding_digits=1,
    )
    assert _row_display(tables, "centr", "demand_total", 2026) == "110"
    assert _row_display(tables, "centr", "generation_total", 2026) == "130"
    assert _row_display(tables, "centr", "coverage_total", 2026) == "130"
    assert _row_display(tables, "centr", "surplus_deficit", 2026) == "20"


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
    assert consumption["unit"] == EE_BALANCE_UNIT
    assert export["editable_values"] is True
