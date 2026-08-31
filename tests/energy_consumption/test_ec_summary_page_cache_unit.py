# -*- coding: utf-8 -*-
"""Кэш JSON сводок потребления: поколение отсекает устаревшие записи после clear."""

from __future__ import annotations

from unittest.mock import patch

from app.energy_consumption.services import ec_summary_page_cache as cache


def test_cached_load_skips_set_when_generation_bumped(app):
    with app.app_context():
        cache._memory_cache = {}
        cache._cache_generation = 0

        calls = {"n": 0}

        def slow_loader():
            calls["n"] += 1
            cache.clear_ec_summary_page_cache()
            return {"summary_rows": [{"v": "stale"}]}

        with patch.object(cache, "get_redis_client", return_value=None):
            with patch.object(cache, "get_current_db_version_id", return_value=20):
                with app.test_request_context(
                    "/energy_consumption/summary/oes/data.json"
                ):
                    result = cache.cached_load_ec_summary_data("oes", slow_loader)
                    assert result == {"summary_rows": [{"v": "stale"}]}
                    assert calls["n"] == 1
                    key = cache.make_ec_summary_data_cache_key("oes", "")
                    assert cache.get_cached_value(key) is None

                    fresh = {"summary_rows": [{"v": "fresh"}]}
                    result2 = cache.cached_load_ec_summary_data("oes", lambda: fresh)
                    assert result2 == fresh
                    assert cache.get_cached_value(key) == fresh


def test_get_rejects_entry_from_previous_generation_without_redis_delete(app):
    with app.app_context():
        cache._memory_cache = {}
        cache._cache_generation = 5

        with patch.object(cache, "get_redis_client", return_value=None):
            cache.set_cached_value("k1", {"v": "old"}, generation=5)
            assert cache.get_cached_value("k1") == {"v": "old"}

            cache._cache_generation = 6
            assert cache.get_cached_value("k1") is None
            assert "k1" not in cache._memory_cache


def test_query_string_combinations_produce_distinct_keys(app):
    with app.app_context():
        with patch.object(cache, "get_current_db_version_id", return_value=1):
            queries = [
                "",
                "start_year=2020&end_year=2025",
                "start_year=2020&end_year=2025&pd_medium=1",
                "ds_ues=1&ds_res=2",
                "ds_ues=1&ds_res=2&rounding_digits=1",
            ]
            keys = {
                cache.make_ec_summary_data_cache_key("oes", q) for q in queries
            }
            assert len(keys) == len(queries)
            scopes = sorted(cache.EC_SUMMARY_CACHE_SCOPES)
            assert scopes == ["ez", "fo", "oes"]
            scope_keys = {
                cache.make_ec_summary_data_cache_key(s, "start_year=2024")
                for s in scopes
            }
            assert len(scope_keys) == len(scopes)


def test_build_cache_key_ignores_pagination_params(app):
    with app.app_context():
        with patch.object(cache, "get_current_db_version_id", return_value=1):
            k1 = cache.make_ec_summary_build_cache_key(
                "oes", "start_year=2020&pd_page=1&pd_page_size=2"
            )
            k2 = cache.make_ec_summary_build_cache_key(
                "oes", "start_year=2020&pd_page=2&pd_page_size=2"
            )
            k3 = cache.make_ec_summary_build_cache_key("oes", "start_year=2020")
            assert k1 == k2 == k3
            d1 = cache.make_ec_summary_data_cache_key(
                "oes", "pd_page=1&pd_page_size=2"
            )
            d2 = cache.make_ec_summary_data_cache_key(
                "oes", "pd_page=2&pd_page_size=2"
            )
            assert d1 != d2
            assert cache.strip_pd_pagination_from_query_string(
                "start_year=2020&pd_page=1&pd_page_size=2"
            ) == "start_year=2020"
            k4 = cache.make_ec_summary_build_cache_key(
                "oes", "start_year=2020&pd_ec_sipr=1&pd_page=1&pd_page_size=2"
            )
            assert k4 == k3
            d_sipr = cache.make_ec_summary_data_cache_key(
                "oes", "pd_page=1&pd_page_size=2&pd_ec_sipr=1"
            )
            assert d_sipr != d1


def test_full_build_cache_stays_in_memory_even_with_redis(app):
    with app.app_context():
        cache._memory_cache = {}
        cache._cache_generation = 1
        redis = type("R", (), {})()
        stored = {}

        def setex(key, ttl, payload):
            stored["key"] = key
            stored["payload"] = payload

        redis.setex = setex
        redis.get = lambda key: stored.get("payload")
        redis.delete = lambda key: None

        with patch.object(cache, "get_redis_client", return_value=redis):
            cache.set_cached_value("build1", {"rows": [1]}, generation=1, use_redis=False)
            assert "build1" in cache._memory_cache
            assert stored == {}
            cache.set_cached_value("page1", {"ok": True}, generation=1, use_redis=True)
            assert "page1" in cache._memory_cache
            assert "payload" in stored
            # Повторное чтение не ходит в Redis unpickle, если память уже есть.
            stored["payload"] = b"not-a-pickle"
            assert cache.get_cached_value("page1") == {"ok": True}
