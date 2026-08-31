# -*- coding: utf-8 -*-
"""Прогрев кэша data.json сводок «Нагрузки» (как warmup_station_cache)."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# Совпадает с первым запросом demand_summary_client_render.js (core + первая страница).
_DEFAULT_QUERY = "pd_data_segments=core&pd_page=1&pd_page_size=2"

# (cache_scope, parse_scope, path, builder name on demand_summary_routes)
_WARMUP_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("oes", "oes", "/power_demand/summary/oes/data.json", "_build_oes_max_summary_context"),
    (
        "fo",
        "fo",
        "/power_demand/summary/federal_districts/data.json",
        "_build_fo_max_summary_context",
    ),
    (
        "ez",
        "ez",
        "/power_demand/summary/energy_zones/data.json",
        "_build_ez_max_summary_context",
    ),
    (
        "coeff_oes",
        "oes",
        "/power_demand/summary/coeff/oes/data.json",
        "_build_oes_coeff_summary_context",
    ),
    (
        "coeff_fo",
        "fo",
        "/power_demand/summary/coeff/federal_districts/data.json",
        "_build_fo_coeff_summary_context",
    ),
    (
        "coeff_ez",
        "ez",
        "/power_demand/summary/coeff/energy_zones/data.json",
        "_build_ez_coeff_summary_context",
    ),
)


def warmup_pd_summary_page_cache() -> None:
    """Строит и кэширует JSON первой страницы core для всех шести сводок."""
    t0 = time.perf_counter()
    try:
        from flask import current_app

        from app.power_demand.routes import demand_summary_routes as routes
        from app.power_demand.services.pd_summary_page_cache import (
            get_cached_value,
            make_pd_summary_data_cache_key,
        )
    except Exception as exc:
        logger.warning("[PD SUMMARY WARMUP] import failed: %s", exc)
        return

    warmed = 0
    skipped = 0
    for cache_scope, parse_scope, path, builder_name in _WARMUP_SPECS:
        cache_key = make_pd_summary_data_cache_key(cache_scope, _DEFAULT_QUERY)
        if get_cached_value(cache_key) is not None:
            skipped += 1
            continue
        builder = getattr(routes, builder_name)
        try:
            with current_app.test_request_context(f"{path}?{_DEFAULT_QUERY}"):
                routes._build_summary_data_json_response(
                    scope=parse_scope,
                    context_builder=builder,
                    cache_scope=cache_scope,
                )
            warmed += 1
        except Exception as exc:
            logger.warning("[PD SUMMARY WARMUP] %s failed: %s", cache_scope, exc)

    elapsed = time.perf_counter() - t0
    msg = (
        f"[PD SUMMARY WARMUP] done in {elapsed:.2f}s "
        f"(warmed={warmed} skipped={skipped})"
    )
    logger.info(msg)
    print(msg)
