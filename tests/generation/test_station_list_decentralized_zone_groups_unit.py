# -*- coding: utf-8 -*-
"""Группировка станций децентрализованной зоны для station_list."""

from collections import defaultdict

from app.generation.services.station_services.station_access_services import (
    DECENTRALIZED_ZONE_SYNTHETIC_RES_ID,
    DECENTRALIZED_ZONE_SYNTHETIC_UES_ID,
)
from app.generation.services.station_services.station_services import (
    _extract_decentralized_zone_rd_groups,
    _normalize_stations_grouped_for_template,
)


def _sample_grouped():
    grouped = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(lambda: defaultdict(list))
            )
        )
    )
    grouped[89][DECENTRALIZED_ZONE_SYNTHETIC_UES_ID][DECENTRALIZED_ZONE_SYNTHETIC_RES_ID][908][0] = [
        object()
    ]
    return grouped


def test_normalize_stations_grouped_preserves_negative_synthetic_keys():
    grouped = _sample_grouped()
    normalized = _normalize_stations_grouped_for_template(grouped)

    assert isinstance(normalized, dict)
    assert not isinstance(normalized, defaultdict)
    assert -1 in normalized[89]
    assert -1 in normalized[89][-1]
    assert 908 in normalized[89][-1][-1]


def test_extract_decentralized_zone_rd_groups_from_defaultdict():
    grouped = _sample_grouped()
    rd_groups = _extract_decentralized_zone_rd_groups(grouped, 89)

    assert 908 in rd_groups
    assert 0 in rd_groups[908]
    assert len(rd_groups[908][0]) == 1


def test_extract_decentralized_zone_rd_groups_from_normalized_dict():
    grouped = _normalize_stations_grouped_for_template(_sample_grouped())
    rd_groups = _extract_decentralized_zone_rd_groups(grouped, 89)

    assert 908 in rd_groups
    assert len(rd_groups[908][0]) == 1
