# -*- coding: utf-8 -*-
"""Юнит-тесты заполнения выработки в балансе ЭЭ."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.energy_balance.services.ee_balance_generation_services import (
    GENERATION_AES_KEY,
    GENERATION_GAES_KEY,
    GENERATION_GES_KEY,
    GENERATION_TES_KEY,
    accumulate_hydro_forecast_generation,
    classify_ee_balance_generation_years,
    forecast_scenario_for_hydro_year,
    load_ee_balance_generation_inputs,
    _hydro_forecast_items_from_places,
    _place_territory_ids,
)


def test_classify_ee_balance_generation_years_fact_current_plan():
    years = [2022, 2023, 2024, 2025, 2026]
    features = {
        2022: "факт",
        2023: "факт",
        2024: "текущий (оценка)",
        2025: "план",
        2026: "план",
    }
    fact_current, plan = classify_ee_balance_generation_years(years, features)
    assert fact_current == [2022, 2023, 2024]
    assert plan == [2025, 2026]


def test_load_ee_balance_generation_inputs_merges_sources_by_year_feature():
    groups = [
        {"key": GENERATION_AES_KEY, "label": "АЭС", "type_ids": (1,), "is_ses_ves": False},
        {"key": GENERATION_TES_KEY, "label": "ТЭС", "type_ids": (2,), "is_ses_ves": False},
    ]
    sheets = [
        {
            "slug": "severo-zapad",
            "layout": "oes_standard",
            "territory": {"kind": "ues", "id": 10, "name": "Северо-Запад"},
        }
    ]
    stations = [
        SimpleNamespace(
            id=101,
            id_station_type=1,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=102,
            id_station_type=2,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
    ]
    generation_by_station = {
        101: {2023: Decimal("11"), 2024: Decimal("12"), 2025: Decimal("99")},
        102: {2023: Decimal("21"), 2024: Decimal("22"), 2025: Decimal("88")},
    }
    with (
        patch(
            "app.energy_balance.services.ee_balance_generation_services.generation_type_groups",
            return_value=groups,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.classify_ee_balance_generation_years",
            return_value=([2023, 2024], [2025]),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_stations_for_generation",
            return_value=stations,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._territory_lookups",
            return_value=({5: 10}, {}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.load_annual_generation_by_station",
            return_value=generation_by_station,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_tes_e_from_fuel_params",
            return_value=({10: {2025: Decimal("55.5")}}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_hydro_forecast_generation_by_territory",
            return_value=({}, {}, {}, {}),
        ),
    ):
        result = load_ee_balance_generation_inputs([2023, 2024, 2025], sheets=sheets)

    sheet = result["severo-zapad"]
    assert sheet[GENERATION_AES_KEY][2023] == Decimal("11")
    assert sheet[GENERATION_AES_KEY][2024] == Decimal("12")
    assert sheet[GENERATION_AES_KEY][2025] == Decimal("99")
    assert sheet[GENERATION_TES_KEY][2023] == Decimal("21")
    assert sheet[GENERATION_TES_KEY][2024] == Decimal("22")
    assert sheet[GENERATION_TES_KEY][2025] == Decimal("55.5")


def test_load_ee_balance_generation_inputs_plan_years_non_tes_from_ee_generation():
    groups = [
        {"key": GENERATION_AES_KEY, "label": "АЭС", "type_ids": (1,), "is_ses_ves": False},
        {"key": "generation_ges", "label": "ГЭС", "type_ids": (4,), "is_ses_ves": False},
        {"key": "generation_gaes", "label": "ГАЭС", "type_ids": (3,), "is_ses_ves": False},
        {"key": "generation_snee", "label": "СНЭЭ", "type_ids": (5,), "is_ses_ves": False},
        {"key": "generation_ses_ves", "label": "СЭС, ВЭС", "type_ids": (6, 7), "is_ses_ves": True},
        {"key": GENERATION_TES_KEY, "label": "ТЭС", "type_ids": (2,), "is_ses_ves": False},
    ]
    sheets = [
        {
            "slug": "severo-zapad",
            "layout": "oes_standard",
            "territory": {"kind": "ues", "id": 10, "name": "Северо-Запад"},
        }
    ]
    stations = [
        SimpleNamespace(
            id=101,
            id_station_type=1,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=103,
            id_station_type=3,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=104,
            id_station_type=4,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=105,
            id_station_type=5,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=106,
            id_station_type=6,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=107,
            id_station_type=2,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
    ]
    generation_by_station = {
        101: {2026: Decimal("40")},
        103: {2026: Decimal("7")},
        104: {2026: Decimal("15")},
        105: {2026: Decimal("3")},
        106: {2026: Decimal("9")},
        107: {2026: Decimal("88")},
    }
    with (
        patch(
            "app.energy_balance.services.ee_balance_generation_services.generation_type_groups",
            return_value=groups,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.classify_ee_balance_generation_years",
            return_value=([], [2026]),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_stations_for_generation",
            return_value=stations,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._territory_lookups",
            return_value=({5: 10}, {}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.load_annual_generation_by_station",
            return_value=generation_by_station,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_tes_e_from_fuel_params",
            return_value=({10: {2026: Decimal("55.5")}}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_hydro_forecast_generation_by_territory",
            return_value=({}, {}, {}, {}),
        ),
    ):
        result = load_ee_balance_generation_inputs([2026], sheets=sheets)

    sheet = result["severo-zapad"]
    assert sheet[GENERATION_AES_KEY][2026] == Decimal("40")
    assert sheet["generation_ges"][2026] == Decimal("15")
    assert sheet["generation_gaes"][2026] == Decimal("7")
    assert sheet["generation_snee"][2026] == Decimal("3")
    assert sheet["generation_ses_ves"][2026] == Decimal("9")
    assert sheet[GENERATION_TES_KEY][2026] == Decimal("55.5")


def test_forecast_scenario_for_hydro_year_maps_balance_tabs():
    assert forecast_scenario_for_hydro_year(None) == "medium_50"
    assert forecast_scenario_for_hydro_year("average") == "medium_50"
    assert forecast_scenario_for_hydro_year("low") == "low_95"
    assert forecast_scenario_for_hydro_year("маловодный") == "low_95"


def test_accumulate_hydro_forecast_generation_by_territory():
    items = [
        {
            "group_key": GENERATION_GES_KEY,
            "amount": Decimal("10.5"),
            "res_id": 5,
            "district_id": 8,
            "eu_id": 101,
        }
    ]
    ues, sa, res, eu = accumulate_hydro_forecast_generation(
        items,
        [2026, 2027],
        {5: 10},
        {8: 10},
        {8: 3},
    )
    assert ues[10][GENERATION_GES_KEY][2026] == Decimal("10.5")
    assert ues[10][GENERATION_GES_KEY][2027] == Decimal("10.5")
    assert sa[3][GENERATION_GES_KEY][2026] == Decimal("10.5")
    assert res[5][GENERATION_GES_KEY][2026] == Decimal("10.5")
    assert eu[101][GENERATION_GES_KEY][2026] == Decimal("10.5")


def test_place_territory_ids_prefers_linked_station():
    station = SimpleNamespace(
        id_regional_energy_system=7,
        id_regional_district=9,
        id_energy_unit=101,
    )
    place = SimpleNamespace(
        id_regional_energy_system=1,
        id_regional_district=2,
        station=station,
    )
    res_id, district_id, eu_id = _place_territory_ids(place, {1: 55})
    assert (res_id, district_id, eu_id) == (7, 9, 101)


def test_place_territory_ids_falls_back_to_place_and_single_eu():
    place = SimpleNamespace(
        id_regional_energy_system=1,
        id_regional_district=2,
        station=None,
    )
    res_id, district_id, eu_id = _place_territory_ids(place, {1: 55})
    assert (res_id, district_id, eu_id) == (1, 2, 55)


def test_hydro_forecast_items_from_places_maps_ges_and_gaes():
    groups = [
        {"key": GENERATION_GES_KEY, "label": "ГЭС"},
        {"key": GENERATION_GAES_KEY, "label": "ГАЭС"},
    ]
    totals = {("ges", 9): Decimal("12"), ("gaes", 4): Decimal("3")}
    ges_places = [
        SimpleNamespace(
            id=9,
            id_regional_energy_system=5,
            id_regional_district=None,
            station=None,
        )
    ]
    gaes_places = [
        SimpleNamespace(
            id=4,
            id_regional_energy_system=5,
            id_regional_district=8,
            station=SimpleNamespace(
                id_regional_energy_system=5,
                id_regional_district=8,
                id_energy_unit=101,
            ),
        )
    ]
    items = _hydro_forecast_items_from_places(
        groups=groups,
        totals=totals,
        ges_places=ges_places,
        gaes_places=gaes_places,
        single_eu_by_res={5: 77},
    )
    by_key = {item["group_key"]: item for item in items}
    assert by_key[GENERATION_GES_KEY]["amount"] == Decimal("12")
    assert by_key[GENERATION_GES_KEY]["eu_id"] == 77
    assert by_key[GENERATION_GAES_KEY]["amount"] == Decimal("3")
    assert by_key[GENERATION_GAES_KEY]["eu_id"] == 101


def test_load_ee_balance_generation_inputs_adds_hydro_forecast_to_ges_gaes():
    groups = [
        {"key": GENERATION_GES_KEY, "label": "ГЭС", "type_ids": (4,), "is_ses_ves": False},
        {"key": GENERATION_GAES_KEY, "label": "ГАЭС", "type_ids": (3,), "is_ses_ves": False},
        {"key": GENERATION_TES_KEY, "label": "ТЭС", "type_ids": (2,), "is_ses_ves": False},
    ]
    sheets = [
        {
            "slug": "severo-zapad",
            "layout": "oes_standard",
            "territory": {"kind": "ues", "id": 10, "name": "Северо-Запад"},
        }
    ]
    stations = [
        SimpleNamespace(
            id=104,
            id_station_type=4,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=103,
            id_station_type=3,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
    ]
    generation_by_station = {
        104: {2026: Decimal("15")},
        103: {2026: Decimal("7")},
    }
    hydro = (
        {
            10: {
                GENERATION_GES_KEY: {2026: Decimal("4")},
                GENERATION_GAES_KEY: {2026: Decimal("2")},
            }
        },
        {},
        {},
        {},
    )
    with (
        patch(
            "app.energy_balance.services.ee_balance_generation_services.generation_type_groups",
            return_value=groups,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.classify_ee_balance_generation_years",
            return_value=([], [2026]),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_stations_for_generation",
            return_value=stations,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._territory_lookups",
            return_value=({5: 10}, {}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.load_annual_generation_by_station",
            return_value=generation_by_station,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_tes_e_from_fuel_params",
            return_value=({}, {}, {}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_hydro_forecast_generation_by_territory",
            return_value=hydro,
        ),
    ):
        result = load_ee_balance_generation_inputs(
            [2026], sheets=sheets, hydro_year="average"
        )

    sheet = result["severo-zapad"]
    assert sheet[GENERATION_GES_KEY][2026] == Decimal("19")
    assert sheet[GENERATION_GAES_KEY][2026] == Decimal("9")


def test_load_ee_balance_generation_inputs_forwards_hydro_year_and_fills_eu():
    groups = [
        {"key": GENERATION_GES_KEY, "label": "ГЭС", "type_ids": (4,), "is_ses_ves": False},
    ]
    sheets = [
        {
            "slug": "eu-101",
            "layout": "oes_standard",
            "territory": {"kind": "eu", "id": 101, "name": "Энергорайон"},
        }
    ]
    seen: dict[str, Any] = {}

    def fake_hydro(years, groups_arg, hydro_year):
        seen["hydro_year"] = hydro_year
        seen["years"] = list(years)
        return (
            {},
            {},
            {},
            {101: {GENERATION_GES_KEY: {2026: Decimal("8")}}},
        )

    with (
        patch(
            "app.energy_balance.services.ee_balance_generation_services.generation_type_groups",
            return_value=groups,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.classify_ee_balance_generation_years",
            return_value=([], [2026]),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_stations_for_generation",
            return_value=[],
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_tes_e_from_fuel_params",
            return_value=({}, {}, {}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_hydro_forecast_generation_by_territory",
            side_effect=fake_hydro,
        ),
    ):
        result = load_ee_balance_generation_inputs(
            [2026], sheets=sheets, hydro_year="low"
        )

    assert seen["hydro_year"] == "low"
    assert seen["years"] == [2026]
    assert result["eu-101"][GENERATION_GES_KEY][2026] == Decimal("8")
