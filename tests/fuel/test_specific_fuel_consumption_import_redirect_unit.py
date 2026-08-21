# -*- coding: utf-8 -*-
from app.fuel.routes.fuel_routes import _specific_fuel_consumption_page_redirect


def test_redirect_to_edit_data_keeps_year_range_and_drops_import_year():
    endpoint, args = _specific_fuel_consumption_page_redirect(
        {
            "redirect_to": "fuel_bp.equipment_group_specific_fuel_consumption_edit_data",
            "union_energy_system_filter": "311",
            "start_year": "2024",
            "end_year": "2026",
            "base_year": "2024",
            "year": "2024",
            "csrf_token": "secret",
            "file": "ignored.xlsx",
        }
    )
    assert endpoint == "fuel_bp.equipment_group_specific_fuel_consumption_edit_data"
    assert args == {
        "union_energy_system_filter": "311",
        "start_year": "2024",
        "end_year": "2026",
        "base_year": "2024",
    }


def test_unknown_redirect_falls_back_to_stations_page():
    endpoint, args = _specific_fuel_consumption_page_redirect(
        {"redirect_to": "fuel_bp.stations_equipment_groups", "year": "2024"}
    )
    assert endpoint == "fuel_bp.stations_equipment_group_specific_fuel_consumption"
    assert args == {"year": "2024"}
