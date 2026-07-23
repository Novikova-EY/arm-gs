# -*- coding: utf-8 -*-
"""Юнит-тесты агрегации выработки ЭЭ на странице ee_generation."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.energy_balance.services import station_ee_generation_page_services as page_services
from app.energy_balance.services.station_ee_generation_page_services import (
    _build_sign_groups_for_stations,
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


def test_build_generation_aggregates_after_2018_keeps_espp_stations():
    regular = _station(1, station_sign=None)
    espp = _station(2, station_sign=STATION_SIGN_ESPP)
    values = {
        1: {2024: Decimal("100")},
        2: {2024: Decimal("40")},
    }

    aggregates = build_generation_aggregates(
        [regular, espp],
        values,
        espp_by_res={5: {2024: Decimal("999")}},
        period_columns=[(2024, "2024")],
    )

    # С 2019 свод ЭСПП не добавляем — только станции, включая ЭСПП.
    assert aggregates["total"][2024] == Decimal("140")


def test_build_generation_aggregates_through_2018_uses_espp_svod():
    regular = _station(1, station_sign=None)
    espp = _station(2, station_sign=STATION_SIGN_ESPP)
    values = {
        1: {2018: Decimal("100")},
        2: {2018: Decimal("40")},  # станция ЭСПП в годы свода не должна попасть в сумму
    }

    aggregates = build_generation_aggregates(
        [regular, espp],
        values,
        espp_by_res={5: {2018: Decimal("55")}},
        period_columns=[(2018, "2018")],
    )

    assert aggregates["total"][2018] == Decimal("155")
    assert aggregates["regional_energy_systems"][5][2018] == Decimal("155")
    assert aggregates["union_energy_systems"][10][2018] == Decimal("155")


def test_build_stations_sum_by_res_includes_espp_stations_after_2018():
    regular = _station(1, station_sign=None)
    espp = _station(2, station_sign=STATION_SIGN_ESPP)
    values = {
        1: {2024: Decimal("100")},
        2: {2024: Decimal("40")},
    }

    by_res = build_stations_sum_by_res([regular, espp], values)

    assert by_res[5][2024] == Decimal("140")


def test_build_stations_sum_by_res_excludes_espp_stations_through_2018():
    regular = _station(1, station_sign=None)
    espp = _station(2, station_sign=STATION_SIGN_ESPP)
    values = {
        1: {2018: Decimal("100")},
        2: {2018: Decimal("40")},
    }

    by_res = build_stations_sum_by_res([regular, espp], values)

    assert by_res[5][2018] == Decimal("100")


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


def test_build_res_verification_through_2018_adds_espp_svod():
    period_columns = [(2018, "2018")]
    control = {5: {2018: Decimal("155")}}
    stations_by_res = {5: {2018: Decimal("100")}}  # без станций ЭСПП
    espp_by_res = {5: {2018: Decimal("55")}}

    verification = build_res_verification_by_res(
        control,
        stations_by_res,
        period_columns,
        espp_by_res,
    )

    assert verification[5][2018] == Decimal("0")


def test_build_res_verification_months_mode_uses_selected_year_cutoff():
    period_columns = [(1, "янв"), (2, "фев")]
    control = {5: {1: Decimal("20"), 2: Decimal("30")}}
    stations_by_res = {5: {1: Decimal("10"), 2: Decimal("10")}}
    espp_by_res = {5: {1: Decimal("10"), 2: Decimal("20")}}

    verification_2018 = build_res_verification_by_res(
        control,
        stations_by_res,
        period_columns,
        espp_by_res,
        months_calendar_year=2018,
    )
    assert verification_2018[5][1] == Decimal("0")
    assert verification_2018[5][2] == Decimal("0")

    verification_2019 = build_res_verification_by_res(
        control,
        stations_by_res,
        period_columns,
        espp_by_res,
        months_calendar_year=2019,
    )
    # С 2019 свод не добавляем: 10-20 и 10-30.
    assert verification_2019[5][1] == Decimal("-10")
    assert verification_2019[5][2] == Decimal("-20")


def test_build_sign_groups_merges_espp_svod_through_2018_only():
    station_rows = [
        {
            "station_id": 1,
            "station_name": "Обычная",
            "station_sign": STATION_SIGN_UNSPECIFIED,
            "periods": {2018: Decimal("10"), 2019: Decimal("11")},
        },
        {
            "station_id": 2,
            "station_name": "ЭСПП-А",
            "station_sign": STATION_SIGN_ESPP,
            "periods": {2018: Decimal("1"), 2019: Decimal("21")},
        },
        {
            "station_id": 3,
            "station_name": "ЭСПП-Б",
            "station_sign": STATION_SIGN_ESPP,
            "periods": {2018: Decimal("2"), 2019: Decimal("22")},
        },
    ]
    groups = _build_sign_groups_for_stations(
        station_rows,
        res_id=5,
        espp_by_res={5: {2018: Decimal("55"), 2019: Decimal("99")}},
        period_columns=[(2018, "2018"), (2019, "2019")],
    )
    assert len(groups) == 2
    espp_group = groups[1]
    assert espp_group["rowspan"] == 2
    assert espp_group["espp_svod_period_keys"] == [2018]
    assert espp_group["periods"][2018] == Decimal("55")
    assert 2019 not in (espp_group["periods"] or {})
    assert [row["station_name"] for row in espp_group["stations"]] == ["ЭСПП-А", "ЭСПП-Б"]


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
    monkeypatch.setattr(page_services, "load_annual_espp_generation_by_res", lambda ids, sy, ey: {})
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
