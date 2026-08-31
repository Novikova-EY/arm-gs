# -*- coding: utf-8 -*-
"""Кэш JSON-данных сводок потребления (ОЭС / ФО / энергозоны)."""

from __future__ import annotations

import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode

from flask import request

from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.services.station_services.aggregation_cache import get_redis_client

EC_SUMMARY_PAGE_CACHE_KEY_VERSION = 5
_PAGINATION_QUERY_KEYS = frozenset({"pd_page", "pd_page_size"})
_CLIENT_ROW_FLAG_QUERY_KEYS = frozenset(
    {
        "pd_ec_sipr",
        "pd_ec_gaes",
        "pd_ec_nt",
        "pd_ec_verify",
        "pd_ec_o1",
        "pd_ec_compact",
    }
)
_BUILD_STRIP_QUERY_KEYS = _PAGINATION_QUERY_KEYS | _CLIENT_ROW_FLAG_QUERY_KEYS
_CACHE_TIMEOUT = timedelta(minutes=30)
_memory_cache: dict[str, tuple[int, Any, datetime]] = {}
_cache_generation: int = 0
_REDIS_GENERATION_KEY = f"ec_summary:cache_gen:v{EC_SUMMARY_PAGE_CACHE_KEY_VERSION}"

EC_SUMMARY_CACHE_SCOPES: frozenset[str] = frozenset(
    {
        "oes",
        "fo",
        "ez",
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


def strip_pd_pagination_from_query_string(query_string: str) -> str:
    """Убирает pd_page / pd_page_size — ключ полного build общий для всех страниц."""
    if not query_string:
        return ""
    pairs = [
        (k, v)
        for k, v in parse_qsl(query_string, keep_blank_values=True)
        if k not in _PAGINATION_QUERY_KEYS
    ]
    return urlencode(pairs)


def strip_ec_summary_build_irrelevant_query(query_string: str) -> str:
    """Пагинация и флаги переключателей не меняют полное дерево."""
    if not query_string:
        return ""
    pairs = [
        (k, v)
        for k, v in parse_qsl(query_string, keep_blank_values=True)
        if k not in _BUILD_STRIP_QUERY_KEYS
    ]
    return urlencode(pairs)


def make_ec_summary_data_cache_key(scope: str, query_string: str) -> str:
    version_id = get_current_db_version_id()
    raw = (
        f"ec_summary:v{EC_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
        f"db{version_id or 'all'}:{scope}:"
        + query_string
    )
    digest = hashlib.md5(raw.encode()).hexdigest()
    return (
        f"ec_summary:v{EC_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
        f"db{version_id or 'all'}:{scope}:{digest}"
    )


def make_ec_summary_build_cache_key(scope: str, query_string: str) -> str:
    """Ключ полного дерева (без пагинации и флагов видимости строк)."""
    stripped = strip_ec_summary_build_irrelevant_query(query_string)
    version_id = get_current_db_version_id()
    raw = (
        f"ec_summary_build:v{EC_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
        f"db{version_id or 'all'}:{scope}:"
        + stripped
    )
    digest = hashlib.md5(raw.encode()).hexdigest()
    return (
        f"ec_summary_build:v{EC_SUMMARY_PAGE_CACHE_KEY_VERSION}:"
        f"db{version_id or 'all'}:{scope}:{digest}"
    )


def _unpack_cached_entry(raw: Any) -> tuple[int | None, Any]:
    if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], int):
        return int(raw[0]), raw[1]
    return None, raw


def get_cached_value(cache_key: str) -> Any | None:
    current_gen = _get_cache_generation()
    cached = _memory_cache.get(cache_key)
    if cached is not None:
        entry_gen, value, cached_at = cached
        if entry_gen != current_gen:
            del _memory_cache[cache_key]
        elif datetime.now() - cached_at >= _CACHE_TIMEOUT:
            del _memory_cache[cache_key]
        else:
            return value

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
                _memory_cache[cache_key] = (entry_gen, value, datetime.now())
                return value
        except Exception:
            pass
    return None


def set_cached_value(
    cache_key: str,
    value: Any,
    *,
    generation: int | None = None,
    use_redis: bool = True,
) -> None:
    gen = _get_cache_generation() if generation is None else int(generation)
    _memory_cache[cache_key] = (gen, value, datetime.now())
    if not use_redis:
        return
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.setex(
                cache_key, _cache_ttl_seconds(), pickle.dumps((gen, value))
            )
        except Exception:
            pass


def cached_load_ec_summary_full_build(
    scope: str,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    query_string = request.query_string.decode("utf-8") if request.query_string else ""
    cache_key = make_ec_summary_build_cache_key(scope, query_string)
    generation = _get_cache_generation()
    cached = get_cached_value(cache_key)
    if cached is not None:
        return cached
    value = loader()
    if _get_cache_generation() == generation:
        # Полное дерево слишком большое для pickle в Redis (блокирует GIL и логин).
        set_cached_value(cache_key, value, generation=generation, use_redis=False)
    return value


def cached_load_ec_summary_data(
    scope: str,
    loader: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    query_string = request.query_string.decode("utf-8") if request.query_string else ""
    cache_key = make_ec_summary_data_cache_key(scope, query_string)
    generation = _get_cache_generation()
    cached = get_cached_value(cache_key)
    if cached is not None:
        return cached
    value = loader()
    if _get_cache_generation() == generation:
        set_cached_value(cache_key, value, generation=generation)
    return value


def clear_ec_summary_page_cache() -> None:
    """Сбрасывает кэш JSON-данных сводок потребления (память + поколение Redis)."""
    global _memory_cache

    _bump_cache_generation()
    _memory_cache = {}
