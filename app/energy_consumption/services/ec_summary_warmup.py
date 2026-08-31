# -*- coding: utf-8 -*-
"""Прогрев кэша data.json сводок «Спрос» (как warmup_pd_summary_page_cache)."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# Совпадает с первым запросом demand_summary_client_render.js (первая страница).
_DEFAULT_QUERY = "pd_page=1&pd_page_size=2"

_WARMUP_SPECS: tuple[tuple[str, str, str], ...] = (
    ("oes", "/energy_consumption/summary/oes/data.json", "oes"),
    ("fo", "/energy_consumption/summary/federal_districts/data.json", "fo"),
    ("ez", "/energy_consumption/summary/energy_zones/data.json", "ez"),
)


def warmup_ec_summary_page_cache() -> None:
    """Строит и кэширует JSON сводок потребления ОЭС / ФО / ЭЗ.

    Не вызывается при старте приложения: полный расчёт трёх сводок занимает
    минуты и из‑за GIL блокирует логин и остальные запросы.
    """
    t0 = time.perf_counter()
    try:
        from flask import current_app

        from app.energy_consumption.routes import energy_consumption_summary_routes as routes
        from app.energy_consumption.services.ec_summary_page_cache import (
            get_cached_value,
            make_ec_summary_data_cache_key,
        )
    except Exception as exc:
        logger.warning("[EC SUMMARY WARMUP] import failed: %s", exc)
        return

    warmed = 0
    skipped = 0
    for cache_scope, path, parse_scope in _WARMUP_SPECS:
        cache_key = make_ec_summary_data_cache_key(cache_scope, _DEFAULT_QUERY)
        if get_cached_value(cache_key) is not None:
            skipped += 1
            continue
        try:
            with current_app.test_request_context(path + "?" + _DEFAULT_QUERY):
                page_kw = routes._ec_summary_common_page_kwargs(summary_table_page=False)
                if parse_scope == "oes":

                    def _builder(*, for_shell: bool, _page_kw=page_kw):
                        return routes.build_summary_oes_page_context(
                            oes_territory_ordered=routes._parse_oes_territory_ordered(),
                            can_edit_summary_cells=False,
                            for_shell=for_shell,
                            **_page_kw,
                        )

                elif parse_scope == "fo":

                    def _builder(*, for_shell: bool, _page_kw=page_kw):
                        return routes.build_summary_fo_page_context(
                            fo_filter_sets=routes._parse_fo_filter_sets(),
                            can_edit_summary_cells=False,
                            for_shell=for_shell,
                            **_page_kw,
                        )

                else:

                    def _builder(*, for_shell: bool, _page_kw=page_kw):
                        return routes.build_summary_ez_page_context(
                            ez_territory_ordered=routes._parse_ez_territory_ordered(),
                            can_edit_summary_cells=False,
                            for_shell=for_shell,
                            **_page_kw,
                        )

                routes._build_summary_data_json_response(
                    scope=parse_scope,
                    context_builder=_builder,
                )
            warmed += 1
        except Exception as exc:
            logger.warning("[EC SUMMARY WARMUP] %s failed: %s", cache_scope, exc)

    elapsed = time.perf_counter() - t0
    msg = (
        f"[EC SUMMARY WARMUP] done in {elapsed:.2f}s "
        f"(warmed={warmed} skipped={skipped})"
    )
    logger.info(msg)
    print(msg)
