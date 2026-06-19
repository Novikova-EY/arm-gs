# -*- coding: utf-8 -*-
"""Юнит-тесты кэша страниц энергобаланса."""

from unittest.mock import patch

from app.energy_balance.services.energy_balance_cache import (
    cached_load,
    clear_energy_balance_cache,
    make_energy_balance_cache_key,
)


def test_make_energy_balance_cache_key_includes_version():
    with patch(
        "app.energy_balance.services.energy_balance_cache.get_current_db_version_id",
        return_value=7,
    ):
        key = make_energy_balance_cache_key("transfer_pairs", "years", 2024, 2024, 2026)
    assert "db7" in key
    assert key.startswith("eb:v1:")


def test_cached_load_reuses_value_until_cleared():
    clear_energy_balance_cache()
    calls = {"count": 0}

    def loader():
        calls["count"] += 1
        return {"value": calls["count"]}

    with patch(
        "app.energy_balance.services.energy_balance_cache.get_current_db_version_id",
        return_value=1,
    ):
        first = cached_load("test_prefix", ("a",), loader)
        second = cached_load("test_prefix", ("a",), loader)
        clear_energy_balance_cache()
        third = cached_load("test_prefix", ("a",), loader)

    assert first == {"value": 1}
    assert second == {"value": 1}
    assert third == {"value": 2}
    assert calls["count"] == 2
