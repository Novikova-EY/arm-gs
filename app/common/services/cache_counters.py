"""Общие счетчики Redis с локальным резервным значением."""

from redis.exceptions import RedisError


def get_shared_counter(redis_client, key: str, fallback: int) -> int:
    if redis_client:
        try:
            return int(redis_client.get(key) or 0)
        except (RedisError, ValueError, TypeError):
            pass
    return fallback
