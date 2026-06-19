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

PD_SUMMARY_PAGE_CACHE_KEY_VERSION = 1
_CACHE_TIMEOUT = timedelta(minutes=30)
_memory_cache: dict[str, tuple[Any, datetime]] = {}


def _cache_ttl_seconds() -> int:
    return int(_CACHE_TIMEOUT.total_seconds())


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


def get_cached_value(cache_key: str) -> Any | None:
    redis_client = get_redis_client()
    if redis_client:
        try:
            serialized = redis_client.get(cache_key)
            if serialized:
                return pickle.loads(serialized)
        except Exception:
            pass

    cached = _memory_cache.get(cache_key)
    if cached is None:
        return None
    value, cached_at = cached
    if datetime.now() - cached_at >= _CACHE_TIMEOUT:
        del _memory_cache[cache_key]
        return None
    return value


def set_cached_value(cache_key: str, value: Any) -> None:
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.setex(cache_key, _cache_ttl_seconds(), pickle.dumps(value))
            return
        except Exception:
            pass
    _memory_cache[cache_key] = (value, datetime.now())


def cached_load_pd_summary_data(
    scope: str,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    query_string = request.query_string.decode("utf-8") if request.query_string else ""
    cache_key = make_pd_summary_data_cache_key(scope, query_string)
    cached = get_cached_value(cache_key)
    if cached is not None:
        return cached
    value = loader()
    set_cached_value(cache_key, value)
    return value


def clear_pd_summary_page_cache() -> None:
    """Сбрасывает кэш JSON-данных сводок нагрузок (Redis + in-memory)."""
    global _memory_cache

    redis_client = get_redis_client()
    if redis_client:
        try:
            prefix = f"pd_summary:v{PD_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
            for key in redis_client.scan_iter(match=f"{prefix}*"):
                redis_client.delete(key)
        except Exception:
            pass
    _memory_cache = {}
