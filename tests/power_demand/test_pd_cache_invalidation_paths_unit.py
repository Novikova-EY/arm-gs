# -*- coding: utf-8 -*-
"""
Инвалидация кэша сводок «Нагрузки» на всех путях изменения данных.

После любого обновления данных data.json не должен отдавать устаревший ответ
при любом сочетании фильтров/кнопок (разные query → разные ключи, clear сбрасывает все).
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

from app.energy_consumption.services import energy_consumption_parameter_services as ec_ps
from app.power_demand.services import demand_parameter_services as dps
from app.power_demand.services import pd_ec_consumption_index_cache as ec_idx
from app.power_demand.services import pd_summary_page_cache as page_cache
from app.power_demand.services.formula_text import (
    power_demand_summary_formula_text_services as formula_svc,
)


def test_pd_detail_save_source_invalidates_display_caches():
    """save_demand_rows_from_post (детальные страницы) вызывает invalidate после commit."""
    src = inspect.getsource(dps.save_demand_rows_from_post)
    assert "invalidate_power_demand_display_caches" in src
    assert "db.session.commit()" in src
    # clear должен идти после успешного commit, не до.
    assert src.index("db.session.commit()") < src.index(
        "invalidate_power_demand_display_caches"
    )


def test_pd_formula_save_reset_clear_summary_page_cache():
    save_src = inspect.getsource(formula_svc.save_formula_text_override)
    reset_src = inspect.getsource(formula_svc.reset_formula_text_override)
    assert "clear_pd_summary_page_cache" in save_src
    assert "clear_pd_summary_page_cache" in reset_src


def test_ec_index_invalidate_also_clears_pd_summary_page_cache():
    src = inspect.getsource(ec_idx.invalidate_pd_ec_consumption_index_cache)
    assert "clear_pd_summary_page_cache" in src


def test_ec_detail_save_invalidates_ec_index_and_thus_pd_summary():
    src = inspect.getsource(ec_ps.save_energy_consumption_rows_from_post)
    assert "invalidate_energy_consumption_display_caches" in src
    assert src.index("db.session.commit()") < src.index(
        "invalidate_energy_consumption_display_caches"
    )


def test_summary_routes_invalidate_after_cell_and_pvc(app):
    """POST сводки (ячейка / PVC / block) сбрасывают display-кэши."""
    from app.power_demand.routes import demand_summary_routes as routes

    for name in (
        "demand_summary_save_cell",
        "demand_summary_save_perimeter_variant",
        "demand_summary_save_block_variant",
    ):
        src = inspect.getsource(getattr(routes, name))
        assert "invalidate_power_demand_display_caches" in src, name


def test_warm_cache_then_invalidate_misses_all_filter_combinations(app):
    """
    Прогрев кэша для типичных сочетаний кнопок → invalidate → все ключи miss.
    Имитирует «то показывает, то нет» из-за неполного clear по одному query.
    """
    with app.app_context():
        page_cache._memory_cache = {}
        page_cache._cache_generation = 0

        filter_combos = [
            ("oes", ""),
            ("oes", "start_year=2020&end_year=2030&pd_medium=1"),
            ("oes", "ds_ues=10&ds_res=20&ds_rd=30&rounding_digits=1"),
            ("oes", "segments=core%2Cchi%2Cee%2Cverify"),
            ("fo", "ds_fd=1&ds_res=2"),
            ("ez", "ds_ez=3&ds_res=4"),
            ("coeff_oes", "coeff_include_long=1&rounding_digits_k=2"),
            ("coeff_fo", "start_year=2024&end_year=2035"),
            ("coeff_ez", "pd_page=2&pd_page_size=25"),
        ]

        with patch.object(page_cache, "get_redis_client", return_value=None):
            with patch.object(page_cache, "get_current_db_version_id", return_value=7):
                keys = []
                for scope, qs in filter_combos:
                    key = page_cache.make_pd_summary_data_cache_key(scope, qs)
                    keys.append(key)
                    page_cache.set_cached_value(
                        key, {"scope": scope, "qs": qs, "rows": [1]}
                    )
                    assert page_cache.get_cached_value(key) is not None

                page_cache.invalidate_power_demand_display_caches()

                for key in keys:
                    assert page_cache.get_cached_value(key) is None


def test_cached_load_after_invalidate_reloads_fresh_payload(app):
    with app.app_context():
        page_cache._memory_cache = {}
        page_cache._cache_generation = 0
        payloads = [{"v": "stale"}, {"v": "fresh"}]
        idx = {"i": 0}

        def loader():
            out = payloads[idx["i"]]
            idx["i"] += 1
            return out

        with patch.object(page_cache, "get_redis_client", return_value=None):
            with patch.object(page_cache, "get_current_db_version_id", return_value=3):
                with app.test_request_context(
                    "/power_demand/summary/oes/data.json?ds_ues=1&pd_medium=1"
                ):
                    assert page_cache.cached_load_pd_summary_data("oes", loader) == {
                        "v": "stale"
                    }
                    # Повтор без invalidate — из кэша, loader не зовётся.
                    assert page_cache.cached_load_pd_summary_data("oes", loader) == {
                        "v": "stale"
                    }
                    assert idx["i"] == 1

                    page_cache.invalidate_power_demand_display_caches()
                    assert page_cache.cached_load_pd_summary_data("oes", loader) == {
                        "v": "fresh"
                    }
                    assert idx["i"] == 2


def test_invalidate_pd_ec_consumption_index_calls_clear_pd_summary(app):
    with app.app_context():
        mock_cache = MagicMock()
        with patch.object(ec_idx, "cache", mock_cache):
            with patch.object(ec_idx, "get_current_version", return_value=11):
                with patch.object(
                    page_cache, "clear_pd_summary_page_cache"
                ) as clear_pd:
                    ec_idx.invalidate_pd_ec_consumption_index_cache()
                    clear_pd.assert_called_once()
                    mock_cache.delete.assert_called_once()
