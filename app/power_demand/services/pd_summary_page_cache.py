# -*- coding: utf-8 -*-
"""Кэш JSON-данных сводок «Максимумы» (ОЭС / ФО / энергозоны)."""

from __future__ import annotations

import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Any, Callable

from flask import request

from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.services.station_services.aggregation_cache import get_redis_client

# v29: в значении кэша хранится поколение — get отбрасывает записи после clear,
# даже если SCAN/delete по Redis не удалил ключ.
PD_SUMMARY_PAGE_CACHE_KEY_VERSION = 29
_CACHE_TIMEOUT = timedelta(minutes=30)
_memory_cache: dict[str, tuple[int, Any, datetime]] = {}
# Поколение кэша: отсекает «опоздавшие» записи после clear (threaded/gunicorn).
_cache_generation: int = 0
_REDIS_GENERATION_KEY = f"pd_summary:cache_gen:v{PD_SUMMARY_PAGE_CACHE_KEY_VERSION}"

# Скоупы data.json (любая комбинация query → отдельный ключ внутри скоупа).
PD_SUMMARY_CACHE_SCOPES: frozenset[str] = frozenset(
    {
        "oes",
        "fo",
        "ez",
        "coeff_oes",
        "coeff_fo",
        "coeff_ez",
    }
)


def _cache_ttl_seconds() -> int:
    return int(_CACHE_TIMEOUT.total_seconds())


def _get_cache_generation() -> int:
    redis_client = get_redis_client()
    if redis_client:
        try:
            raw = redis_client.get(_REDIS_GENERATION_KEY)
            if raw is not None:
                return int(raw)
        except Exception:
            pass
    return _cache_generation


def _bump_cache_generation() -> int:
    global _cache_generation
    redis_client = get_redis_client()
    if redis_client:
        try:
            return int(redis_client.incr(_REDIS_GENERATION_KEY))
        except Exception:
            pass
    _cache_generation += 1
    return _cache_generation


def make_pd_summary_data_cache_key(scope: str, query_string: str) -> str:
    version_id = get_current_db_version_id()
    raw = (
        f"pd_summary:v{PD_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
        f"db{version_id or 'all'}:{scope}:"
        + query_string
    )
    digest = hashlib.md5(raw.encode()).hexdigest()
    return (
        f"pd_summary:v{PD_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
        f"db{version_id or 'all'}:{scope}:{digest}"
    )


def _unpack_cached_entry(raw: Any) -> tuple[int | None, Any]:
    """Возвращает (generation|None, value). Старый формат без поколения → generation=None."""
    if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], int):
        return int(raw[0]), raw[1]
    return None, raw


def get_cached_value(cache_key: str) -> Any | None:
    current_gen = _get_cache_generation()
    redis_client = get_redis_client()
    if redis_client:
        try:
            serialized = redis_client.get(cache_key)
            if serialized:
                entry_gen, value = _unpack_cached_entry(pickle.loads(serialized))
                if entry_gen is None or entry_gen != current_gen:
                    try:
                        redis_client.delete(cache_key)
                    except Exception:
                        pass
                    return None
                return value
        except Exception:
            pass

    cached = _memory_cache.get(cache_key)
    if cached is None:
        return None
    entry_gen, value, cached_at = cached
    if entry_gen != current_gen:
        del _memory_cache[cache_key]
        return None
    if datetime.now() - cached_at >= _CACHE_TIMEOUT:
        del _memory_cache[cache_key]
        return None
    return value


def set_cached_value(cache_key: str, value: Any, *, generation: int | None = None) -> None:
    gen = _get_cache_generation() if generation is None else int(generation)
    payload = (gen, value)
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.setex(cache_key, _cache_ttl_seconds(), pickle.dumps(payload))
            return
        except Exception:
            pass
    _memory_cache[cache_key] = (gen, value, datetime.now())


def cached_load_pd_summary_data(
    scope: str,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    query_string = request.query_string.decode("utf-8") if request.query_string else ""
    cache_key = make_pd_summary_data_cache_key(scope, query_string)
    generation = _get_cache_generation()
    cached = get_cached_value(cache_key)
    if cached is not None:
        return cached
    value = loader()
    # Не писать в кэш, если за время loader() был clear_pd_summary_page_cache()
    # (иначе устаревший ответ перетирает свежие данные после сохранения ячейки).
    if _get_cache_generation() == generation:
        set_cached_value(cache_key, value, generation=generation)
    return value


def clear_pd_summary_page_cache() -> None:
    """Сбрасывает кэш JSON-данных сводок нагрузок (Redis + in-memory)."""
    global _memory_cache

    _bump_cache_generation()
    redis_client = get_redis_client()
    if redis_client:
        try:
            prefix = f"pd_summary:v{PD_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
            for key in redis_client.scan_iter(match=f"{prefix}*"):
                redis_client.delete(key)
        except Exception:
            pass
    _memory_cache = {}


def invalidate_power_demand_display_caches() -> None:
    """
    Полный сброс кэшей отображения сводок «Нагрузки» после любого изменения данных.
    Вызывать после commit на всех путях записи (сводка, детальные страницы, формулы, EC).
    """
    clear_pd_summary_page_cache()
    from app.power_demand.services.pd_demand_rows_bulk_cache import (
        clear_power_demand_rows_bulk_cache,
    )

    clear_power_demand_rows_bulk_cache()
