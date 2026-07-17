# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from app.fuel.services.stations.stations_equipment_groups_services import (
    _hierarchy_key_from_station,
    _station_matches_selected_territory_filters,
)


def _dz_station(station_id=36873, rd_id=715, res_id=100):
    return SimpleNamespace(
        id=station_id,
        name="Николаевская ТЭЦ",
        database_version_id=20,
        id_regional_district=rd_id,
        id_regional_energy_system=res_id,
        regional_district=SimpleNamespace(
            id=rd_id,
            id_federal_district=1,
            name="Хабаровский край",
        ),
        regional_energy_system_obj=SimpleNamespace(
            id=res_id,
            name="не указано",
            union_energy_system=None,
        ),
    )


def test_hierarchy_key_from_station_uses_dz_synthetic_branch():
    station = _dz_station()
    with (
        patch(
            "app.generation.services.station_services.station_access_services.is_decentralized_zone_station",
            return_value=True,
        ),
        patch(
            "app.generation.services.station_services.station_access_services.get_decentralized_zone_energy_system_type_id",
            return_value=74,
        ),
    ):
        key = _hierarchy_key_from_station(station)

    assert key == (74, -1, -1, 715, 715)


def test_station_matches_dz_when_est_filter_is_decentralized_zone():
    station = _dz_station()
    with (
        patch(
            "app.generation.services.station_services.station_access_services.is_decentralized_zone_station",
            return_value=True,
        ),
        patch(
            "app.generation.services.station_services.station_access_services.get_decentralized_zone_energy_system_type_id",
            return_value=74,
        ),
    ):
        assert _station_matches_selected_territory_filters(
            station, {"energy_system_type_filter": [74]}
        )
        assert not _station_matches_selected_territory_filters(
            station, {"energy_system_type_filter": [72]}
        )
