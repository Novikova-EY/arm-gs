# -*- coding: utf-8 -*-
"""Юнит-тесты помесячного расчёта прогнозной выработки ТЭС (Магадан)."""

from __future__ import annotations

from types import SimpleNamespace
from decimal import Decimal
from unittest.mock import patch

from app.energy_balance.services.ee_balance_generation_services import (
    GENERATION_GES_KEY,
    GENERATION_TES_KEY,
)
from app.energy_balance.services.ee_balance_tes_forecast_services import (
    ROW_CHIIM_HEADER,
    ROW_CONSUMPTION,
    ROW_DEFICIT,
    ROW_GES_USED,
    ROW_HOURS,
    ROW_KIUM_HEADER,
    ROW_PIVR_SUM,
    ROW_PRODUCTION,
    ROW_TES_FACT_AVG,
    ROW_TES_TOTAL,
    _load_ges_pivr_months,
    compute_tes_forecast_year,
    hours_in_month,
    is_magadan_tes_forecast_sheet,
    is_tes_forecast_sheet,
    overlay_tes_forecast_generation_inputs,
    resolve_tes_forecast_view_year,
    tes_fact_average_sample_years,
    tes_fact_avg_year_row_key,
    tes_forecast_page_title,
    tes_forecast_plan_years,
    tes_forecast_year_has_tes_input,
    tes_forecast_year_tes_total,
    year_hours_total,
    _station_machine_groups,
    machine_group_row_key,
)


def _row(rows, key: str) -> dict:
    return next(item for item in rows if item["key"] == key)


def test_hours_follow_calendar_year():
    assert hours_in_month(1, 2026) == Decimal("744")
    assert hours_in_month(2, 2026) == Decimal("672")
    assert hours_in_month(4, 2026) == Decimal("720")
    assert year_hours_total(2026) == Decimal("8760")
    assert hours_in_month(2, 2028) == Decimal("696")
    assert year_hours_total(2028) == Decimal("8784")


def test_magadan_sheet_detection():
    assert is_magadan_tes_forecast_sheet(
        {
            "sheet_name": "Центральный энергорайон Магаданской области",
            "territory": {"name": "Центральный энергорайон Магаданской области"},
        }
    )
    assert not is_magadan_tes_forecast_sheet(
        {
            "sheet_name": "Центральный энергорайон Сахалинской области",
        }
    )
    assert not is_magadan_tes_forecast_sheet(None)


def test_tites_sibir_sheet_is_tes_forecast():
    sibir = {
        "slug": "oes-318",
        "sheet_name": "ТИТЭС Сибири",
        "territory": {"name": "ТИТЭС Сибири"},
    }
    assert is_tes_forecast_sheet(sibir)
    assert tes_forecast_page_title(sibir) == (
        "Помесячный баланс электрической энергии ТИТЭС Сибири "
        "для условий маловодного года"
    )
    assert not is_magadan_tes_forecast_sheet(sibir)
    assert not is_tes_forecast_sheet({"sheet_name": "ТИТЭС Востока"})
    magadan = {
        "sheet_name": "Центральный энергорайон Магаданской области",
        "territory": {"name": "Центральный энергорайон Магаданской области"},
    }
    assert is_tes_forecast_sheet(magadan)


def test_plan_year_tabs_and_view_year():
    features = {2024: "факт", 2025: "текущий (оценка)", 2026: "план", 2027: "план"}
    years = [2024, 2025, 2026, 2027]
    assert tes_forecast_plan_years(years, features) == [2026, 2027]
    assert resolve_tes_forecast_view_year(None, [2026, 2027]) == 2026
    assert resolve_tes_forecast_view_year(2027, [2026, 2027]) == 2027
    assert resolve_tes_forecast_view_year(2024, [2026, 2027]) == 2026


def test_compute_formulas_match_excel_structure():
    rows = compute_tes_forecast_year(
        year=2026,
        stored={
            ROW_CONSUMPTION: {1: Decimal("100"), 2: Decimal("80")},
            "tes_station_1": {1: Decimal("40"), 2: Decimal("10")},
            "tes_machine_11": {1: Decimal("5"), 2: Decimal("7")},
            "tes_machine_12": {1: Decimal("6")},
        },
        annual_consumption=Decimal("1000"),
        ges_stations=[
            {
                "id": 10,
                "label": "Колымская ГЭС",
                "capacity": Decimal("900"),
                "pivr": {1: Decimal("151.776"), 2: Decimal("134.4")},
            },
            {
                "id": 11,
                "label": "Усть-Среднеканская ГЭС",
                "capacity": Decimal("570"),
                "pivr": {1: Decimal("100.44"), 2: Decimal("80.64")},
            },
        ],
        tes_stations=[
            {
                "id": 1,
                "label": "Магаданская ТЭЦ",
                "capacity": Decimal("75"),
                "machines": [],
            },
            {
                "id": 2,
                "label": "Аркагалинская ГРЭС",
                "capacity": Decimal("47"),
                "machines": [
                    {"id": 11, "label": "5 АПТ-12-1", "capacity": Decimal("12")},
                    {"id": 12, "label": "2 К-35-29", "capacity": Decimal("35")},
                ],
            },
        ],
        aes_capacity=None,
        ges_capacity=Decimal("1470"),
    )
    pivr = _row(rows, ROW_PIVR_SUM)
    assert pivr["label"] == "Выработка ГЭС по ПИВР"
    assert pivr["values"][1] == Decimal("252.216")
    assert pivr["values"][2] == Decimal("215.04")
    assert pivr["values"]["year"] == Decimal("467.256")
    ges_used = _row(rows, ROW_GES_USED)["values"]
    assert ges_used[1] == pivr["values"][1]
    tes_total = _row(rows, ROW_TES_TOTAL)["values"]
    assert tes_total[1] == Decimal("51")
    assert tes_total[2] == Decimal("17")
    production = _row(rows, ROW_PRODUCTION)["values"]
    assert production[1] == ges_used[1] + tes_total[1]
    deficit = _row(rows, ROW_DEFICIT)["values"]
    assert deficit[1] == production[1] - Decimal("100")
    arkagala = _row(rows, "tes_station_2")["values"]
    assert arkagala[1] == Decimal("11")
    assert arkagala[2] == Decimal("7")
    chiim_tec = _row(rows, "chiim_tes_station_1")["values"]
    assert chiim_tec[1] == Decimal("40") / Decimal("75") * Decimal("1000")
    kium_tec = _row(rows, "kium_tes_station_1")["values"]
    assert kium_tec[1] == chiim_tec[1] / Decimal("744") * Decimal("100")
    assert _row(rows, ROW_CHIIM_HEADER)["label"] == "ЧЧИУМ"
    assert _row(rows, ROW_KIUM_HEADER)["label"] == "КИУМ"
    assert _row(rows, "kium_tes_station_1")["label"] == "Магаданская ТЭЦ"
    assert _row(rows, "kium_tes_station_2")["collapsible"] is True
    assert _row(rows, "kium_tes_machine_11")["parent_station_key"] == "kium_tes_station_2"
    hours = _row(rows, ROW_HOURS)
    assert hours["label"] == "Количество часов в месяц"
    assert hours["values"][2] == Decimal("672")
    assert hours["values"]["year"] == Decimal("8760")
    assert tes_forecast_year_tes_total(rows) == Decimal("68")
    assert _row(rows, "tes_station_1")["editable"] is True
    assert _row(rows, "tes_station_1")["collapsible"] is False
    assert _row(rows, "tes_station_2")["editable"] is True
    assert _row(rows, "tes_station_2")["collapsible"] is True
    assert _row(rows, "tes_machine_11")["editable"] is True
    assert _row(rows, "tes_machine_11")["is_machine_row"] is True
    assert _row(rows, "tes_machine_11")["parent_station_key"] == "tes_station_2"
    assert _row(rows, "tes_station_2")["station_id"] == 2
    assert _row(rows, "tes_machine_11")["station_id"] == 2
    assert _row(rows, "tes_machine_11")["machine_id"] == 11
    assert _row(rows, "ges_station_10")["station_id"] == 10
    assert _row(rows, "chiim_tes_machine_11")["parent_station_key"] == "chiim_tes_station_2"
    assert _row(rows, "chiim_tes_station_2")["collapsible"] is True
    assert _row(rows, ROW_CONSUMPTION)["css_class"] == "table-info"
    assert _row(rows, ROW_GES_USED)["css_class"] == ""
    assert _row(rows, ROW_PIVR_SUM)["css_class"] == "tes-ref-row"
    assert _row(rows, ROW_PIVR_SUM)["is_reference"] is True
    assert _row(rows, "ges_station_10")["css_class"] == "tes-ref-row"
    keys = [item["key"] for item in rows]
    assert keys.index(ROW_PRODUCTION) < keys.index(ROW_PIVR_SUM)
    assert keys.index(ROW_PIVR_SUM) < keys.index("ges_station_10")
    assert keys.index("ges_station_11") < keys.index(ROW_GES_USED)
    assert keys.index(ROW_GES_USED) < keys.index(ROW_TES_FACT_AVG)
    assert keys.index(ROW_TES_FACT_AVG) < keys.index("tes_fact_avg_station_1")
    assert keys.index("tes_fact_avg_station_2") < keys.index(ROW_TES_TOTAL)
    assert _row(rows, ROW_TES_FACT_AVG)["css_class"] == "tes-ref-row"
    assert _row(rows, ROW_TES_FACT_AVG)["is_reference"] is True
    assert _row(rows, ROW_TES_FACT_AVG)["label"] == (
        "Выработка ТЭС (среднее за 5 лет)"
    )
    assert _row(rows, "tes_fact_avg_station_1")["css_class"] == "tes-ref-row"
    assert _row(rows, "tes_fact_avg_station_1")["station_id"] == 1
    assert _row(rows, ROW_TES_TOTAL)["css_class"] == ""
    assert _row(rows, "capacity_tes")["css_class"] == ""
    assert "capacity_aes" not in keys
    assert _row(rows, "chiim_tes")["css_class"] == ""
    assert _row(rows, "kium_tes")["css_class"] == ""
    assert _row(rows, "capacity_total")["css_class"] == "table-info"
    assert _row(rows, ROW_PRODUCTION)["label"] == "Выработка электрической энергии"
    assert _row(rows, ROW_CONSUMPTION)["unit"] == "млн.кВт·ч"
    assert _row(rows, ROW_HOURS)["unit"] == "ч."
    assert _row(rows, "capacity_total")["unit"] == "МВт"
    assert _row(rows, "chiim_tes")["unit"] == "ч."
    assert _row(rows, "kium_tes")["unit"] == "%"


def test_capacity_shows_aes_only_when_stations_exist():
    rows = compute_tes_forecast_year(
        year=2026,
        tes_stations=[
            {
                "id": 1,
                "label": "Магаданская ТЭЦ",
                "capacity": Decimal("75"),
                "machines": [],
            }
        ],
    )
    assert "capacity_aes" not in [item["key"] for item in rows]
    with_aes = compute_tes_forecast_year(
        year=2026,
        tes_stations=[
            {
                "id": 1,
                "label": "Магаданская ТЭЦ",
                "capacity": Decimal("75"),
                "machines": [],
            }
        ],
        aes_stations=[
            {
                "id": 50,
                "label": "Новая АЭС",
                "capacity": Decimal("120"),
                "machines": [
                    {"id": 7, "label": "Блок 1", "capacity": Decimal("120")},
                ],
            }
        ],
    )
    aes = _row(with_aes, "capacity_aes")
    assert aes["label"] == "АЭС"
    assert aes["values"]["year"] == Decimal("120")
    station = _row(with_aes, "capacity_aes_station_50")
    assert station["label"] == "Новая АЭС"
    assert station["parent_station_key"] is None
    assert _row(with_aes, "capacity_aes_machine_7")["parent_station_key"] == (
        "capacity_aes_station_50"
    )
    assert _row(with_aes, "capacity_total")["values"]["year"] == Decimal("195")


def test_consumption_from_annual_share_and_ges_used_override():
    rows = compute_tes_forecast_year(
        year=2026,
        stored={
            "consumption_share": {1: Decimal("0.1"), 2: Decimal("0.2")},
            ROW_GES_USED: {1: Decimal("200")},
        },
        annual_consumption=Decimal("3000"),
        ges_stations=[
            {
                "id": 10,
                "label": "Колымская ГЭС",
                "pivr": {1: Decimal("250"), 2: Decimal("100")},
            }
        ],
        tes_stations=[],
    )
    consumption = _row(rows, ROW_CONSUMPTION)["values"]
    assert consumption[1] == Decimal("300")
    assert consumption[2] == Decimal("600")
    ges_used = _row(rows, ROW_GES_USED)["values"]
    assert ges_used[1] == Decimal("200")
    assert ges_used[2] == Decimal("100")


def test_pivr_loads_low_water_forecast_from_ges_station_card():
    station = SimpleNamespace(id=29649)
    by_scenario = {
        "low_95": {1: Decimal("12.5"), 2: Decimal("8")},
        "medium_50": {1: Decimal("99"), 2: Decimal("88")},
    }
    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.is_ges_station",
            return_value=True,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.hydro_forecast_owner_for_station",
            return_value=("station", 29649),
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_hydro_forecast_by_scenario",
            return_value=by_scenario,
        ) as loader,
    ):
        months = _load_ges_pivr_months(station)
    loader.assert_called_once_with("station", 29649)
    assert months[1] == Decimal("12.5")
    assert months[2] == Decimal("8")


def test_single_machine_station_is_collapsible():
    rows = compute_tes_forecast_year(
        year=2026,
        stored={"tes_machine_3": {1: Decimal("8")}},
        tes_stations=[
            {
                "id": 9,
                "label": "Магаданская ТЭЦ",
                "capacity": Decimal("75"),
                "machines": [{"id": 3, "label": "ТГ-1", "capacity": Decimal("75")}],
            }
        ],
    )
    station = _row(rows, "tes_station_9")
    machine = _row(rows, "tes_machine_3")
    assert station["collapsible"] is True
    assert station["editable"] is True
    assert station["values"][1] == Decimal("8")
    assert machine["is_machine_row"] is True
    assert machine["parent_station_key"] == "tes_station_9"


def test_collapsible_station_uses_station_value_when_machines_empty():
    tes_stations = [
        {
            "id": 9,
            "label": "Магаданская ТЭЦ",
            "capacity": Decimal("75"),
            "machines": [{"id": 3, "label": "ТГ-1", "capacity": Decimal("75")}],
        }
    ]
    rows = compute_tes_forecast_year(
        year=2026,
        stored={"tes_station_9": {1: Decimal("15")}},
        tes_stations=tes_stations,
    )
    assert _row(rows, "tes_station_9")["values"][1] == Decimal("15")
    assert _row(rows, "tes_machine_3")["values"][1] is None
    mixed = compute_tes_forecast_year(
        year=2026,
        stored={
            "tes_station_9": {1: Decimal("15")},
            "tes_machine_3": {1: Decimal("8")},
        },
        tes_stations=tes_stations,
    )
    assert _row(mixed, "tes_station_9")["values"][1] == Decimal("8")
    assert tes_forecast_year_has_tes_input(
        {"tes_station_9": {1: Decimal("15")}}, tes_stations
    )


def test_hours_row_uses_leap_february():
    rows = compute_tes_forecast_year(year=2028)
    hours = _row(rows, ROW_HOURS)
    assert hours["label"] == "Количество часов в месяц"
    assert hours["values"][2] == Decimal("696")
    assert hours["values"]["year"] == Decimal("8784")


def test_overlay_replaces_magadan_plan_tes_when_monthly_input_exists():
    sheets = [
        {
            "slug": "eu-257",
            "sheet_name": "Центральный энергорайон Магаданской области",
            "territory": {
                "kind": "eu",
                "id": 257,
                "name": "Центральный энергорайон Магаданской области",
            },
        }
    ]
    inputs = {
        "eu-257": {GENERATION_TES_KEY: {2026: Decimal("999"), 2024: Decimal("80")}}
    }
    tes_stations = [
        {"id": 1, "label": "Магаданская ТЭЦ", "capacity": Decimal("75"), "machines": []}
    ]
    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.classify_ee_balance_generation_years",
            return_value=([2024], [2026]),
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_tes_forecast_stored_years",
            return_value={2026: {"tes_station_1": {1: Decimal("12.5"), 2: Decimal("7.5")}}},
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_tes_forecast_entities",
            return_value={
                "ges_stations": [],
                "tes_stations": tes_stations,
                "aes_capacity": None,
                "ges_capacity": None,
            },
        ),
    ):
        merged = overlay_tes_forecast_generation_inputs(inputs, sheets, [2024, 2026])
    assert merged["eu-257"][GENERATION_TES_KEY][2026] == Decimal("20")
    assert merged["eu-257"][GENERATION_TES_KEY][2024] == Decimal("80")


def test_overlay_keeps_fuel_tes_when_monthly_empty():
    sheets = [
        {
            "slug": "eu-257",
            "sheet_name": "Центральный энергорайон Магаданской области",
            "territory": {"name": "Центральный энергорайон Магаданской области"},
        }
    ]
    inputs = {"eu-257": {GENERATION_TES_KEY: {2026: Decimal("999")}}}
    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.classify_ee_balance_generation_years",
            return_value=([], [2026]),
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_tes_forecast_stored_years",
            return_value={2026: {"consumption": {1: Decimal("10")}}},
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_tes_forecast_entities",
            return_value={
                "ges_stations": [],
                "tes_stations": [
                    {"id": 1, "label": "ТЭЦ", "capacity": Decimal("75"), "machines": []}
                ],
                "aes_capacity": None,
                "ges_capacity": None,
            },
        ),
    ):
        merged = overlay_tes_forecast_generation_inputs(inputs, sheets, [2026])
    assert merged["eu-257"][GENERATION_TES_KEY][2026] == Decimal("999")
    assert merged["eu-257"]["consumption"][2026] == Decimal("10")


def test_overlay_copies_ges_and_consumption_year_totals():
    sheets = [
        {
            "slug": "eu-257",
            "sheet_name": "Центральный энергорайон Магаданской области",
            "territory": {"name": "Центральный энергорайон Магаданской области"},
        }
    ]
    inputs = {
        "eu-257": {
            GENERATION_TES_KEY: {2026: Decimal("999")},
            GENERATION_GES_KEY: {2026: Decimal("1")},
            "consumption": {2026: Decimal("100")},
        }
    }
    tes_stations = [
        {"id": 1, "label": "Магаданская ТЭЦ", "capacity": Decimal("75"), "machines": []}
    ]
    ges_stations = [
        {
            "id": 10,
            "label": "Колымская ГЭС",
            "capacity": Decimal("300"),
            "machines": [],
            "pivr": {1: Decimal("12"), 2: Decimal("8")},
        }
    ]
    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.classify_ee_balance_generation_years",
            return_value=([], [2026]),
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_tes_forecast_stored_years",
            return_value={
                2026: {
                    "tes_station_1": {1: Decimal("5"), 2: Decimal("7")},
                    "consumption": {1: Decimal("40"), 2: Decimal("15")},
                    "ges_used": {1: Decimal("10")},
                }
            },
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_tes_forecast_entities",
            return_value={
                "ges_stations": ges_stations,
                "tes_stations": tes_stations,
                "aes_capacity": None,
                "ges_capacity": None,
            },
        ),
    ):
        merged = overlay_tes_forecast_generation_inputs(inputs, sheets, [2026])
    assert merged["eu-257"][GENERATION_TES_KEY][2026] == Decimal("12")
    assert merged["eu-257"][GENERATION_GES_KEY][2026] == Decimal("18")
    assert merged["eu-257"]["consumption"][2026] == Decimal("55")


_FACT_FEATURES = {
    2019: "факт",
    2020: "факт",
    2021: "факт",
    2022: "факт",
    2023: "факт",
    2024: "факт",
    2025: "текущий (оценка)",
    2026: "план",
}


def test_tes_fact_average_uses_five_fact_years_without_current():
    assert tes_fact_average_sample_years(_FACT_FEATURES, has_current_data=False) == [
        2020,
        2021,
        2022,
        2023,
        2024,
    ]


def test_tes_fact_average_uses_four_fact_and_current_when_current_has_data():
    assert tes_fact_average_sample_years(_FACT_FEATURES, has_current_data=True) == [
        2021,
        2022,
        2023,
        2024,
        2025,
    ]


def test_tes_fact_avg_block_averages_monthly_generation():
    rows = compute_tes_forecast_year(
        year=2026,
        tes_stations=[
            {
                "id": 1,
                "label": "Магаданская ТЭЦ",
                "capacity": Decimal("75"),
                "machines": [],
                "fact_avg": {1: Decimal("20"), 2: Decimal("10")},
            },
            {
                "id": 2,
                "label": "Аркагалинская ГРЭС",
                "capacity": Decimal("47"),
                "machines": [],
                "fact_avg": {1: Decimal("4"), 2: Decimal("8")},
            },
        ],
    )
    header = _row(rows, ROW_TES_FACT_AVG)
    assert header["values"][1] == Decimal("24")
    assert header["values"][2] == Decimal("18")
    assert header["values"]["year"] == Decimal("42")
    assert _row(rows, "tes_fact_avg_station_1")["values"][1] == Decimal("20")
    assert _row(rows, "tes_fact_avg_station_2")["values"][2] == Decimal("8")
    assert _row(rows, "tes_fact_avg_station_1")["editable"] is not True


def test_tes_fact_avg_station_expands_sample_years():
    parent_key = "tes_fact_avg_station_1"
    year_key = tes_fact_avg_year_row_key(1, 2020)
    rows = compute_tes_forecast_year(
        year=2026,
        tes_stations=[
            {
                "id": 1,
                "label": "Магаданская ТЭЦ",
                "capacity": Decimal("75"),
                "machines": [],
                "fact_avg": {1: Decimal("15")},
                "fact_avg_years": [
                    {"year": 2020, "values": {1: Decimal("10"), 2: Decimal("12")}},
                    {"year": 2021, "values": {1: Decimal("20")}},
                ],
            }
        ],
    )
    station = _row(rows, parent_key)
    assert station["collapsible"] is True
    assert station["collapse_expand_title"] == "Показать годы"
    year_row = _row(rows, year_key)
    assert year_row["label"] == "2020"
    assert year_row["parent_station_key"] == parent_key
    assert year_row["indent"] == 2
    assert year_row["values"][1] == Decimal("10")
    assert year_row["values"][2] == Decimal("12")
    assert year_row["values"]["year"] == Decimal("22")
    assert _row(rows, tes_fact_avg_year_row_key(1, 2021))["values"][1] == Decimal("20")
    keys = [item["key"] for item in rows]
    assert keys.index(parent_key) < keys.index(year_key)
    assert keys.index(tes_fact_avg_year_row_key(1, 2021)) < keys.index(ROW_TES_TOTAL)


def test_load_tes_fact_avg_uses_current_year_when_station_has_data():
    from app.energy_balance.services.ee_balance_tes_forecast_services import (
        _load_tes_fact_avg_by_station,
    )

    monthly = {
        2021: {1: {1: Decimal("10")}},
        2022: {1: {1: Decimal("20")}},
        2023: {1: {1: Decimal("30")}},
        2024: {1: {1: Decimal("40")}},
        2025: {1: {1: Decimal("50")}},
        2020: {1: {1: Decimal("5")}},
    }

    def _monthly(station_ids, year):
        return monthly.get(int(year), {})

    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.get_power_balance_year_features",
            return_value=_FACT_FEATURES,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_monthly_generation_by_station",
            side_effect=_monthly,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_annual_generation_by_station",
            return_value={},
        ),
    ):
        result = _load_tes_fact_avg_by_station([1])
    # 2021..2024 + 2025 current: (10+20+30+40+50)/5 = 30
    assert result[1]["avg"][1] == Decimal("30")
    assert [item["year"] for item in result[1]["years"]] == [
        2021,
        2022,
        2023,
        2024,
        2025,
    ]
    assert result[1]["years"][-1]["values"][1] == Decimal("50")


def test_load_tes_fact_avg_skips_current_year_without_data():
    from app.energy_balance.services.ee_balance_tes_forecast_services import (
        _load_tes_fact_avg_by_station,
    )

    monthly = {
        2020: {1: {1: Decimal("5")}},
        2021: {1: {1: Decimal("10")}},
        2022: {1: {1: Decimal("20")}},
        2023: {1: {1: Decimal("30")}},
        2024: {1: {1: Decimal("40")}},
    }

    def _monthly(station_ids, year):
        return monthly.get(int(year), {})

    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.get_power_balance_year_features",
            return_value=_FACT_FEATURES,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_monthly_generation_by_station",
            side_effect=_monthly,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_annual_generation_by_station",
            return_value={},
        ),
    ):
        result = _load_tes_fact_avg_by_station([1])
    # 2020..2024, no 2025: (5+10+20+30+40)/5 = 21
    assert result[1]["avg"][1] == Decimal("21")
    assert [item["year"] for item in result[1]["years"]] == [
        2020,
        2021,
        2022,
        2023,
        2024,
    ]
    assert result[1]["years"][0]["values"][1] == Decimal("5")


def test_load_tes_fact_avg_omits_years_without_generation():
    from app.energy_balance.services.ee_balance_tes_forecast_services import (
        _load_tes_fact_avg_by_station,
    )

    def _monthly(station_ids, year):
        if int(year) == 2024:
            return {1: {1: Decimal("40")}}
        return {}

    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.get_power_balance_year_features",
            return_value=_FACT_FEATURES,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_monthly_generation_by_station",
            side_effect=_monthly,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_annual_generation_by_station",
            return_value={},
        ),
    ):
        result = _load_tes_fact_avg_by_station([1])
    assert result[1]["avg"][1] == Decimal("40")
    assert [item["year"] for item in result[1]["years"]] == [2024]
    assert result[1]["years"][0]["values"][1] == Decimal("40")


def test_load_tes_fact_avg_splits_annual_when_monthly_empty():
    from app.energy_balance.services.ee_balance_tes_forecast_services import (
        _load_tes_fact_avg_by_station,
    )

    annual = Decimal("8784")
    with (
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.get_power_balance_year_features",
            return_value=_FACT_FEATURES,
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_monthly_generation_by_station",
            return_value={},
        ),
        patch(
            "app.energy_balance.services.ee_balance_tes_forecast_services.load_annual_generation_by_station",
            return_value={1: {2024: annual}},
        ),
    ):
        result = _load_tes_fact_avg_by_station([1])
    hours_year = year_hours_total(2024)
    assert [item["year"] for item in result[1]["years"]] == [2024]
    assert result[1]["years"][0]["values"][1] == annual * hours_in_month(1, 2024) / hours_year
    assert result[1]["avg"][1] == result[1]["years"][0]["values"][1]


def test_station_machine_groups_keeps_named_together():
    machines = [
        {"id": 1, "machine_group": "1 очередь"},
        {"id": 2, "machine_group": ""},
        {"id": 3, "machine_group": "1 очередь"},
        {"id": 4, "machine_group": "2 очередь"},
    ]
    groups = _station_machine_groups(machines)
    assert groups[0] == ("1 очередь", [0, 2])
    assert groups[1] == ("2 очередь", [3])
    assert groups[2] == (None, [1])


def test_tes_forecast_adds_machine_group_subtotals():
    group_key = machine_group_row_key("tes", 2, "ТЭЦ-1")
    rows = compute_tes_forecast_year(
        year=2026,
        stored={
            "tes_machine_11": {1: Decimal("5"), 2: Decimal("7")},
            "tes_machine_12": {1: Decimal("6")},
        },
        tes_stations=[
            {
                "id": 2,
                "label": "Аркагалинская ГРЭС",
                "capacity": Decimal("47"),
                "machines": [
                    {
                        "id": 11,
                        "label": "5 АПТ-12-1",
                        "capacity": Decimal("12"),
                        "machine_group": "ТЭЦ-1",
                    },
                    {
                        "id": 12,
                        "label": "2 К-35-29",
                        "capacity": Decimal("35"),
                        "machine_group": "ТЭЦ-1",
                    },
                ],
            }
        ],
    )
    group = _row(rows, group_key)
    assert group["label"] == "ТЭЦ-1"
    assert group["is_group_row"] is True
    assert group["parent_station_key"] == "tes_station_2"
    assert group["collapsible"] is True
    assert group["values"][1] == Decimal("11")
    assert group["values"][2] == Decimal("7")
    assert _row(rows, "tes_machine_11")["parent_station_key"] == group_key
    assert _row(rows, "tes_machine_11")["indent"] == 3
    cap_group = _row(rows, machine_group_row_key("capacity_tes", 2, "ТЭЦ-1"))
    assert cap_group["values"]["year"] == Decimal("47")
    chiim_group = _row(rows, machine_group_row_key("chiim_tes", 2, "ТЭЦ-1"))
    assert chiim_group["parent_station_key"] == "chiim_tes_station_2"
