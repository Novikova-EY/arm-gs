# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.fuel.services.equipment_groups.equipment_group_merge_services import (
    _is_group_in_version,
    merge_candidates_for_version,
)


def test_is_group_in_version_does_not_mix_legacy_with_versioned():
    versioned = SimpleNamespace(id=1, database_version_id=37)
    other_version = SimpleNamespace(id=2, database_version_id=20)
    legacy = SimpleNamespace(id=3, database_version_id=None)

    assert _is_group_in_version(versioned, 37) is True
    assert _is_group_in_version(other_version, 37) is False
    assert _is_group_in_version(legacy, 37) is False
    assert _is_group_in_version(legacy, None) is True
    assert _is_group_in_version(versioned, None) is False


def test_merge_candidates_for_version_keeps_only_same_version_groups():
    current = SimpleNamespace(id=17348, database_version_id=37, name="ТЭЦ-4")
    other_station_same_version = SimpleNamespace(
        id=17347, database_version_id=37, name="ТЭЦ-3 и ТЭЦ-4"
    )
    fuel_version = SimpleNamespace(id=13113, database_version_id=20, name="ТЭЦ-3 и ТЭЦ-4")
    legacy = SimpleNamespace(id=17136, database_version_id=None, name="ТЭЦ-3 и ТЭЦ-4")

    candidates = merge_candidates_for_version(
        [current, fuel_version],
        [other_station_same_version, fuel_version, legacy],
        37,
    )

    assert [g.id for g in candidates] == [17348, 17347]


def test_merge_candidates_for_version_legacy_scope_excludes_versioned():
    current = SimpleNamespace(id=17136, database_version_id=None, name="ТЭЦ-4")
    versioned = SimpleNamespace(id=13113, database_version_id=20, name="ТЭЦ-3 и ТЭЦ-4")

    candidates = merge_candidates_for_version([current], [versioned, current], None)

    assert [g.id for g in candidates] == [17136]
