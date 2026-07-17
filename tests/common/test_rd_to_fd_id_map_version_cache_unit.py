# -*- coding: utf-8 -*-
"""Маппинг rd→fd для station_list."""

from types import SimpleNamespace

from app.generation.services.station_services.station_services import (
    _enrich_rd_to_fd_mapping_from_stations,
)


def test_enrich_rd_to_fd_mapping_from_stations_fills_missing_fd():
    station = SimpleNamespace(
        id_regional_district=703,
        regional_district=SimpleNamespace(id_federal_district=86),
    )
    result = _enrich_rd_to_fd_mapping_from_stations({}, [station])

    assert result[703] == 86


def test_enrich_rd_to_fd_mapping_from_stations_keeps_existing_mapping():
    station = SimpleNamespace(
        id_regional_district=703,
        regional_district=SimpleNamespace(id_federal_district=86),
    )
    result = _enrich_rd_to_fd_mapping_from_stations({703: 99}, [station])

    assert result[703] == 99


def test_enrich_rd_to_fd_mapping_json_serializable_with_sort_keys():
    import json

    station = SimpleNamespace(
        id_regional_district=703,
        regional_district=SimpleNamespace(id_federal_district=86),
    )
    result = _enrich_rd_to_fd_mapping_from_stations({1: 2}, [station])

    serialized = json.dumps(result, sort_keys=True)
    assert json.loads(serialized) == {"1": 2, "703": 86}
