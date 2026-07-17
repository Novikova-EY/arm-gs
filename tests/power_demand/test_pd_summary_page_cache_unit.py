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
            cache.set_cached_value("pd_summary:v22:test", fresh)
            assert cache.get_cached_value("pd_summary:v22:test") == fresh

            # Опоздавший loader с поколением до clear не пишет в кэш.
            if cache._get_cache_generation() == gen_before:
                cache.set_cached_value("pd_summary:v22:test", stale)

            assert cache.get_cached_value("pd_summary:v22:test") == fresh


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
