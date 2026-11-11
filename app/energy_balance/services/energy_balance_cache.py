# -*- coding: utf-8 -*-
"""Кэш данных страниц энергобаланса (выработка ЭЭ, перетоки)."""

from __future__ import annotations

import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Any, Callable

from redis.exceptions import RedisError

from app.common.services.cache_counters import get_shared_counter
from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.services.station_services.aggregation_cache import get_redis_client

ENERGY_BALANCE_CACHE_KEY_VERSION = 2
_CACHE_TIMEOUT = timedelta(minutes=30)
_memory_cache: dict[str, tuple[Any, datetime]] = {}
_cache_generation = 0
_data_revision = 0
_REDIS_GENERATION_KEY = "eb:cache_generation"
_REDIS_DATA_REVISION_KEY = "eb:data_revision"


def _cache_ttl_seconds() -> int:
    return int(_CACHE_TIMEOUT.total_seconds())


def get_energy_balance_cache_generation() -> int:
    return get_shared_counter(get_redis_client(), _REDIS_GENERATION_KEY, _cache_generation)


def get_energy_balance_data_revision() -> int:
    """Версия сохраненных исходных данных, независимая от очистки кеша."""
    return get_shared_counter(get_redis_client(), _REDIS_DATA_REVISION_KEY, _data_revision)


def publish_energy_balance_data_change() -> None:
    """Публикует успешное сохранение источников и обновляет связанные кеши."""
    global _data_revision

    # Новая версия данных не должна указывать на еще не сброшенный кеш.
    clear_energy_balance_cache()
    _data_revision += 1
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.incr(_REDIS_DATA_REVISION_KEY)
        except RedisError:
            pass


def make_energy_balance_cache_key(prefix: str, *parts: Any) -> str:
    """Строит ключ кэша с учетом версии БД."""
    from app.generation.services.station_services.generation_only_visibility import generation_visibility_cache_key
    parts = (*parts, generation_visibility_cache_key())
    version_id = get_current_db_version_id()
    generation = get_energy_balance_cache_generation()
    prefix = f"g{generation}:{prefix}"
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
    global _memory_cache, _cache_generation

    _cache_generation += 1
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.incr(_REDIS_GENERATION_KEY)
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
