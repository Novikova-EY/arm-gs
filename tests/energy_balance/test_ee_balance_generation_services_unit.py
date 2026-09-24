# -*- coding: utf-8 -*-
"""Юнит-тесты заполнения выработки в балансе ЭЭ."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.energy_balance.services.ee_balance_generation_services import (
    GENERATION_AES_KEY,
    GENERATION_GAES_KEY,
    GENERATION_GES_KEY,
    GENERATION_TES_KEY,
    HYDRO_YEAR_AVERAGE,
    HYDRO_YEAR_LOW,
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


def test_load_ee_balance_generation_inputs_fills_ses_ves_children():
    groups = [
        {
            "key": "generation_ses_ves",
            "label": "СЭС, ВЭС",
            "type_ids": (6, 7),
            "is_ses_ves": True,
            "children": [
                {"key": "generation_ses", "label": "СЭС", "type_ids": (6,)},
                {"key": "generation_ves", "label": "ВЭС", "type_ids": (7,)},
            ],
        },
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
            id=106,
            id_station_type=6,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
        SimpleNamespace(
            id=107,
            id_station_type=7,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
    ]
    generation_by_station = {
        106: {2026: Decimal("9")},
        107: {2026: Decimal("4")},
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
    assert sheet["generation_ses"][2026] == Decimal("9")
    assert sheet["generation_ves"][2026] == Decimal("4")
    assert sheet[GENERATION_TES_KEY][2026] == Decimal("55.5")


def test_apply_ves_ses_plan_generation_fills_missing_plan_years():
    from app.energy_balance.services.ee_balance_generation_services import (
        apply_ves_ses_plan_generation_to_station_map,
    )

    stations = [
        SimpleNamespace(
            id=201,
            id_station_type=6,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
    ]
    type_to_key = {6: "generation_ses"}
    generation_by_station = {
        201: {2023: Decimal("10"), 2024: Decimal("12")},
    }
    with (
        patch(
            "app.common.services.get_services.years.year_feature_services.get_year_feature_dict",
            return_value={2024: "текущий", 2025: "план", 2026: "план"},
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.load_annual_generation_by_station",
            return_value={201: {2023: Decimal("10"), 2024: Decimal("12")}},
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_owner_generation_by_station",
            return_value={},
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.get_current_db_version_id",
            return_value=1,
        ),
        patch(
            "app.generation.services.station_services.ves_ses_plan_generation_services.load_station_commission_years",
            return_value={},
        ),
        patch(
            "app.generation.services.station_services.ves_ses_plan_generation_services.load_station_exploitation_dates",
            return_value={},
        ),
        patch(
            "app.energy_balance.services.ee_balance_ves_ses_page_services._load_stations_p_ust",
            return_value={201: {2025: Decimal("4"), 2026: Decimal("4")}},
        ),
        patch(
            "app.generation.services.station_services.ves_ses_plan_generation_services.compute_ves_ses_plan_generation",
            return_value=(
                Decimal("10"),
                {2025: Decimal("15"), 2026: Decimal("18")},
                {2025: "rule", 2026: "rule"},
            ),
        ),
    ):
        result = apply_ves_ses_plan_generation_to_station_map(
            stations,
            generation_by_station,
            type_to_key,
            years=[2023, 2024, 2025, 2026],
            year_features={2024: "текущий", 2025: "план", 2026: "план"},
        )

    assert result[201][2023] == Decimal("10")
    assert result[201][2024] == Decimal("12")
    assert result[201][2025] == Decimal("15")
    assert result[201][2026] == Decimal("18")


def test_apply_ves_ses_plan_uses_seven_year_min_when_capacity_exists_before_plan():
    """Лист 2026–2031 не должен считать станцию новой из‑за усечённого ряда Руст."""
    from app.energy_balance.services.ee_balance_generation_services import (
        apply_ves_ses_plan_generation_to_station_map,
    )

    stations = [
        SimpleNamespace(
            id=201,
            id_station_type=6,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
    ]
    type_to_key = {6: "generation_ses"}
    fact = {year: Decimal("10") for year in range(2018, 2025)}
    year_features = {2025: "текущий"}
    year_features.update({year: "план" for year in range(2026, 2032)})

    captured_capacity_years: dict[str, list[int]] = {}

    def _capture_p_ust(_ids, years, _version_id):
        captured_capacity_years["years"] = [int(year) for year in years]
        return {
            201: {
                int(year): Decimal("4")
                for year in years
                if int(year) >= 2020
            }
        }

    with (
        patch(
            "app.common.services.get_services.years.year_feature_services.get_year_feature_dict",
            return_value=year_features,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.load_annual_generation_by_station",
            return_value={201: dict(fact)},
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_owner_generation_by_station",
            return_value={},
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.get_current_db_version_id",
            return_value=1,
        ),
        patch(
            "app.generation.services.station_services.ves_ses_plan_generation_services.load_station_commission_years",
            return_value={201: 2020},
        ),
        patch(
            "app.generation.services.station_services.ves_ses_plan_generation_services.load_station_exploitation_dates",
            return_value={},
        ),
        patch(
            "app.energy_balance.services.ee_balance_ves_ses_page_services._load_stations_p_ust",
            side_effect=_capture_p_ust,
        ),
    ):
        result = apply_ves_ses_plan_generation_to_station_map(
            stations,
            {201: {}},
            type_to_key,
            years=[2026, 2027],
            year_features=year_features,
        )

    assert 2018 in captured_capacity_years["years"]
    assert 2020 in captured_capacity_years["years"]
    assert 2025 in captured_capacity_years["years"]
    assert result[201][2026] == Decimal("10")
    assert result[201][2027] == Decimal("10")


def test_load_ee_balance_generation_inputs_uses_ves_ses_plan_when_stored_empty():
    groups = [
        {
            "key": "generation_ses_ves",
            "label": "СЭС, ВЭС",
            "type_ids": (6,),
            "is_ses_ves": True,
            "children": [
                {"key": "generation_ses", "label": "СЭС", "type_ids": (6,)},
            ],
        },
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
            id=301,
            id_station_type=6,
            id_regional_energy_system=5,
            id_regional_district=None,
        ),
    ]
    with (
        patch(
            "app.energy_balance.services.ee_balance_generation_services.generation_type_groups",
            return_value=groups,
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.classify_ee_balance_generation_years",
            return_value=([2024], [2026]),
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
            return_value={301: {2024: Decimal("12")}},
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services.apply_ves_ses_plan_generation_to_station_map",
            side_effect=lambda stations, gen_map, type_to_key, years, year_features=None: (
                gen_map.__setitem__(
                    301, {**(gen_map.get(301) or {}), 2026: Decimal("42")}
                )
                or gen_map
            ),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_tes_e_from_fuel_params",
            return_value=({}, {}, {}, {}),
        ),
        patch(
            "app.energy_balance.services.ee_balance_generation_services._load_hydro_forecast_generation_by_territory",
            return_value=({}, {}, {}, {}),
        ),
    ):
        result = load_ee_balance_generation_inputs([2024, 2026], sheets=sheets)

    sheet = result["severo-zapad"]
    assert sheet["generation_ses"][2024] == Decimal("12")
    assert sheet["generation_ses"][2026] == Decimal("42")


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


def test_load_ee_balance_generation_inputs_applies_hydro_year_per_oes():
    groups = [
        {"key": GENERATION_GES_KEY, "label": "ГЭС", "type_ids": (4,), "is_ses_ves": False},
    ]
    sheets = [
        {
            "slug": "centr",
            "group": "oes",
            "layout": "oes_standard",
            "territory": {"kind": "ues", "id": 2, "name": "Центр"},
        },
        {
            "slug": "sibir",
            "group": "oes",
            "layout": "oes_sibir",
            "territory": {"kind": "ues", "id": 6, "name": "Сибирь"},
        },
        {
            "slug": "eu-101",
            "group": "eu",
            "layout": "oes_standard",
            "parent_slug": "sibir",
            "territory": {"kind": "eu", "id": 101, "name": "Энергорайон"},
        },
    ]
    seen: list[str] = []

    def fake_hydro(years, groups_arg, hydro_year):
        seen.append(str(hydro_year))
        if hydro_year == HYDRO_YEAR_AVERAGE:
            return (
                {2: {GENERATION_GES_KEY: {2026: Decimal("10")}}},
                {},
                {},
                {101: {GENERATION_GES_KEY: {2026: Decimal("1")}}},
            )
        return (
            {6: {GENERATION_GES_KEY: {2026: Decimal("7")}}},
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

    assert set(seen) == {HYDRO_YEAR_AVERAGE, HYDRO_YEAR_LOW}
    assert result["centr"][GENERATION_GES_KEY][2026] == Decimal("10")
    assert result["sibir"][GENERATION_GES_KEY][2026] == Decimal("7")
    assert result["eu-101"][GENERATION_GES_KEY][2026] == Decimal("8")
