# -*- coding: utf-8 -*-
"""Кэш данных страниц энергобаланса (выработка ЭЭ, перетоки)."""

from __future__ import annotations

import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Any, Callable

from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.services.station_services.aggregation_cache import get_redis_client

ENERGY_BALANCE_CACHE_KEY_VERSION = 2
_CACHE_TIMEOUT = timedelta(minutes=30)
_memory_cache: dict[str, tuple[Any, datetime]] = {}


def _cache_ttl_seconds() -> int:
    return int(_CACHE_TIMEOUT.total_seconds())


def make_energy_balance_cache_key(prefix: str, *parts: Any) -> str:
    """Строит ключ кэша с учётом версии БД."""
    version_id = get_current_db_version_id()
    raw = (
        f"eb:v{ENERGY_BALANCE_CACHE_KEY_VERSION}:"
        f"db{version_id or 'all'}:{prefix}:"
        + "|".join(str(part) for part in parts)
    )
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"eb:v{ENERGY_BALANCE_CACHE_KEY_VERSION}:db{version_id or 'all'}:{prefix}:{digest}"


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


def cached_load(prefix: str, key_parts: tuple[Any, ...], loader: Callable[[], Any]) -> Any:
    cache_key = make_energy_balance_cache_key(prefix, *key_parts)
    cached = get_cached_value(cache_key)
    if cached is not None:
        return cached
    value = loader()
    set_cached_value(cache_key, value)
    return value


def clear_energy_balance_cache() -> None:
    """Сбрасывает кэш страниц энергобаланса (Redis + in-memory)."""
    global _memory_cache

    redis_client = get_redis_client()
    if redis_client:
        try:
            keys_to_delete: list[bytes] = []
            for pattern in [f"eb:v{ENERGY_BALANCE_CACHE_KEY_VERSION}:*"]:
                cursor = 0
                while True:
                    cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
                    keys_to_delete.extend(keys)
                    if cursor == 0:
                        break
            if keys_to_delete:
                batch_size = 100
                for index in range(0, len(keys_to_delete), batch_size):
                    redis_client.delete(*keys_to_delete[index : index + batch_size])
        except Exception:
            pass

    _memory_cache = {}
