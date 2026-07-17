# -*- coding: utf-8 -*-
"""Юнит-тесты агрегации выработки ЭЭ на странице ee_generation."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.energy_balance.services import station_ee_generation_page_services as page_services
from app.energy_balance.services.station_ee_generation_page_services import (
    _format_station_sign_display,
    _is_espp_station_sign,
    _resolve_station_sign,
    build_generation_aggregates,
    build_res_verification_by_res,
    build_stations_sum_by_res,
)
from app.generation.models.station.station_constants import (
    STATION_SIGN_ESPP,
    STATION_SIGN_UNSPECIFIED,
)


def _station(station_id: int, *, station_sign=None):
    return SimpleNamespace(id=station_id, station_sign=station_sign)


@pytest.fixture(autouse=True)
def _mock_station_placement(monkeypatch):
    def _placement(station):
        return (1, 10, 5, 100, 0)

    monkeypatch.setattr(page_services, "_resolve_station_placement", _placement)


@pytest.mark.parametrize(
    ("station_sign", "expected_espp", "expected_display"),
    [
        (STATION_SIGN_ESPP, True, "да"),
        ("true", True, STATION_SIGN_ESPP),
        ("false", False, "—"),
        (None, False, "—"),
        ("", False, "—"),
    ],
)
def test_station_sign_display_formats_import_and_native_values(
    station_sign, expected_espp, expected_display
):
    station = _station(1, station_sign=station_sign)
    assert _is_espp_station_sign(station_sign) is expected_espp
    assert _format_station_sign_display(station_sign) == expected_display
    if expected_espp:
        assert _resolve_station_sign(station) == STATION_SIGN_ESPP
    else:
        assert _resolve_station_sign(station) == STATION_SIGN_UNSPECIFIED


def test_build_generation_aggregates_sums_all_stations_regardless_of_sign():
    regular = _station(1, station_sign=None)
    espp = _station(2, station_sign=STATION_SIGN_ESPP)
    values = {
        1: {2024: Decimal("100")},
        2: {2024: Decimal("40")},
    }

    aggregates = build_generation_aggregates([regular, espp], values)

    assert aggregates["total"][2024] == Decimal("140")
    assert aggregates["regional_energy_systems"][5][2024] == Decimal("140")
    assert aggregates["union_energy_systems"][10][2024] == Decimal("140")


def test_build_generation_aggregates_ignores_espp_svod():
    regular = _station(1, station_sign=None)
    espp = _station(2, station_sign=STATION_SIGN_ESPP)
    values = {
        1: {2024: Decimal("100")},
        2: {2024: Decimal("40")},
    }

    aggregates = build_generation_aggregates([regular, espp], values)

    assert aggregates["total"][2024] == Decimal("140")


def test_build_stations_sum_by_res_includes_espp_stations():
    regular = _station(1, station_sign=None)
    espp = _station(2, station_sign=STATION_SIGN_ESPP)
    values = {
        1: {2024: Decimal("100")},
        2: {2024: Decimal("40")},
    }

    by_res = build_stations_sum_by_res([regular, espp], values)

    assert by_res[5][2024] == Decimal("140")


def test_build_res_verification_is_stations_sum_minus_control():
    period_columns = [(2024, "2024")]
    control = {5: {2024: Decimal("140")}}
    stations_by_res = {5: {2024: Decimal("140")}}

    verification = build_res_verification_by_res(
        control,
        stations_by_res,
        period_columns,
    )

    assert verification[5][2024] == Decimal("0")


def test_show_totals_uses_station_list_pagination(monkeypatch):
    """При show_totals пагинация и next_station_info берутся из get_stations_list, как на station_list."""
    page_station = SimpleNamespace(id=1)
    next_info = {"union_energy_system_id": 10, "regional_energy_system_id": 5}
    captured: dict[str, object] = {}

    def fake_get_stations_list(*, page, per_page, **kwargs):
        captured["page"] = page
        captured["per_page"] = per_page
        return {
            "stations": [page_station],
            "total_count": 100,
            "effective_total_pages": 4,
            "next_station_info": next_info,
        }

    def fake_determine_totals_to_show(
        stations_on_page,
        total_count,
        page_num,
        per_page_for_totals,
        filters,
        next_station_info=None,
        force_full_aggregates=False,
    ):
        captured["next_station_info"] = next_station_info
        return {
            "energy_units": {},
            "regional_districts": {},
            "regional_energy_systems": {},
            "union_energy_systems": {},
            "energy_system_types": {},
            "total": False,
        }

    monkeypatch.setattr(page_services, "get_stations_list", fake_get_stations_list)
    monkeypatch.setattr(page_services, "determine_totals_to_show", fake_determine_totals_to_show)
    monkeypatch.setattr(page_services, "ensure_stations_machines_for_display", lambda stations: None)
    monkeypatch.setattr(page_services, "load_annual_generation_by_station", lambda ids, sy, ey: {})
    monkeypatch.setattr(page_services, "load_annual_res_control_generation_by_res", lambda ids, sy, ey: {})
    monkeypatch.setattr(page_services, "build_station_ee_generation_hierarchy", lambda *args, **kwargs: [])
    monkeypatch.setattr(page_services, "get_station_ids_for_aggregation", lambda *args, **kwargs: [])
    monkeypatch.setattr(page_services, "determine_first_headers", lambda *args, **kwargs: {})
    monkeypatch.setattr(page_services, "build_res_show_rd_level_map", lambda filters: {})
    monkeypatch.setattr(page_services, "get_cached_page_position", lambda *args, **kwargs: (None, None))

    page_services.get_station_ee_generation_page_data(
        filters={},
        page=2,
        rounding_digits=1,
        start_year=2024,
        end_year=2024,
        per_page=50,
        show_totals=True,
    )

    assert captured["page"] == 2
    assert captured["per_page"] == 50
    assert captured["next_station_info"] == next_info
