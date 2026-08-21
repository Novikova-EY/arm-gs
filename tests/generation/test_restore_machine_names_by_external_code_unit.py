# -*- coding: utf-8 -*-
from app.generation.services.machine_services.machine_name_sync_services import (
    _is_blank_name,
    _pick_name_from_year_map,
    _version_rank,
)


def test_blank_and_version_rank_helpers():
    assert _is_blank_name(None) is True
    assert _is_blank_name("") is True
    assert _is_blank_name("  ") is True
    assert _is_blank_name("РО-1") is False
    assert _version_rank(None) == -1
    assert _version_rank(46) > _version_rank(20)


def test_pick_name_from_year_map():
    year_map = {
        2021: (20, "ДО"),
        2029: (41, "ПОСЛЕ"),
    }
    assert _pick_name_from_year_map(year_map, 2021, None) == "ДО"
    assert _pick_name_from_year_map(year_map, 2029, None) == "ПОСЛЕ"
    assert _pick_name_from_year_map(year_map, 2025, None) == "ДО"
    assert _pick_name_from_year_map(year_map, 2035, None) == "ПОСЛЕ"
    assert _pick_name_from_year_map({}, 2025, "FALLBACK") == "FALLBACK"
    assert _pick_name_from_year_map({}, 2025, None) is None
