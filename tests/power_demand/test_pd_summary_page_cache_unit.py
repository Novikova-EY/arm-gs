# -*- coding: utf-8 -*-
"""Кэш JSON сводок нагрузок: поколение отсекает устаревшие записи после clear."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services import pd_summary_page_cache as cache


def test_stale_loader_does_not_overwrite_cache_after_clear(app):
    """Поток A начал loader до save; после clear его set не должен вернуть старые данные."""
    with app.app_context():
        cache._memory_cache = {}
        cache._cache_generation = 0

        with patch.object(cache, "get_redis_client", return_value=None):
            gen_before = cache._get_cache_generation()
            assert cache.get_cached_value("k") is None

            # Имитация: clear во время медленного loader (сохранение ячейки).
            cache.clear_pd_summary_page_cache()
            assert cache._get_cache_generation() == gen_before + 1

            stale = {"summary_rows": [{"v": 100}]}
            fresh = {"summary_rows": [{"v": 110}]}

            # Свежий запрос после save успевает записать актуальные данные.
            cache.set_cached_value("pd_summary:v29:test", fresh)
            assert cache.get_cached_value("pd_summary:v29:test") == fresh

            # Опоздавший loader с поколением до clear не пишет в кэш.
            if cache._get_cache_generation() == gen_before:
                cache.set_cached_value("pd_summary:v29:test", stale)

            assert cache.get_cached_value("pd_summary:v29:test") == fresh


def test_cached_load_skips_set_when_generation_bumped(app):
    with app.app_context():
        cache._memory_cache = {}
        cache._cache_generation = 0

        calls = {"n": 0}

        def slow_loader():
            calls["n"] += 1
            # clear посередине «долгой» загрузки
            cache.clear_pd_summary_page_cache()
            return {"summary_rows": [{"v": "stale"}]}

        with patch.object(cache, "get_redis_client", return_value=None):
            with patch.object(cache, "get_current_db_version_id", return_value=20):
                with app.test_request_context(
                    "/power_demand/summary/oes/data.json?pd_page=1&pd_page_size=2"
                ):
                    result = cache.cached_load_pd_summary_data("oes", slow_loader)
                    assert result == {"summary_rows": [{"v": "stale"}]}
                    assert calls["n"] == 1
                    # В кэш не попало — generation сменился во время loader.
                    key = cache.make_pd_summary_data_cache_key(
                        "oes", "pd_page=1&pd_page_size=2"
                    )
                    assert cache.get_cached_value(key) is None

                    fresh = {"summary_rows": [{"v": "fresh"}]}
                    result2 = cache.cached_load_pd_summary_data("oes", lambda: fresh)
                    assert result2 == fresh
                    assert cache.get_cached_value(key) == fresh


def test_get_rejects_entry_from_previous_generation_without_redis_delete(app):
    """После clear get не отдаёт старую запись, даже если ключ остался в memory."""
    with app.app_context():
        cache._memory_cache = {}
        cache._cache_generation = 5

        with patch.object(cache, "get_redis_client", return_value=None):
            cache.set_cached_value("k1", {"v": "old"}, generation=5)
            assert cache.get_cached_value("k1") == {"v": "old"}

            # Bump generation без очистки memory (имитация сбоя SCAN/delete).
            cache._cache_generation = 6
            assert cache.get_cached_value("k1") is None
            assert "k1" not in cache._memory_cache


def test_query_string_combinations_produce_distinct_keys(app):
    """Любое сочетание фильтров/кнопок (query) — отдельный ключ кэша."""
    with app.app_context():
        with patch.object(cache, "get_current_db_version_id", return_value=1):
            queries = [
                "",
                "start_year=2020&end_year=2025",
                "start_year=2020&end_year=2025&pd_medium=1",
                "ds_ues=1&ds_res=2",
                "ds_ues=1&ds_res=2&rounding_digits=1",
                "segments=core,chi,ee",
                "coeff_include_long=1&rounding_digits_k=2",
                "pd_page=1&pd_page_size=50",
            ]
            keys = {
                cache.make_pd_summary_data_cache_key("oes", q) for q in queries
            }
            assert len(keys) == len(queries)

            # Скоупы ОЭС/ФО/ЭЗ и коэффициенты не пересекаются.
            scopes = sorted(cache.PD_SUMMARY_CACHE_SCOPES)
            assert scopes == [
                "coeff_ez",
                "coeff_fo",
                "coeff_oes",
                "ez",
                "fo",
                "oes",
            ]
            scope_keys = {
                cache.make_pd_summary_data_cache_key(s, "start_year=2024")
                for s in scopes
            }
            assert len(scope_keys) == len(scopes)


def test_invalidate_power_demand_display_caches_bumps_and_clears_memory(app):
    with app.app_context():
        cache._memory_cache = {}
        cache._cache_generation = 0
        with patch.object(cache, "get_redis_client", return_value=None):
            cache.set_cached_value("k", {"ok": 1})
            assert cache.get_cached_value("k") == {"ok": 1}
            gen0 = cache._get_cache_generation()
            cache.invalidate_power_demand_display_caches()
            assert cache._get_cache_generation() == gen0 + 1
            assert cache._memory_cache == {}
            assert cache.get_cached_value("k") is None
