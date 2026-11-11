"""Shared Redis caching for expensive station aggregations."""

import pickle

from app.generation.services.station_services import aggregation_cache


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.deleted = []

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    def scan(self, cursor, match, count):
        prefix = match[:-1]
        matching = [
            key
            for key in self.values
            if (key.decode() if isinstance(key, bytes) else key).startswith(prefix)
        ]
        return 0, matching

    def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)


def test_aggregation_result_is_shared_through_redis_between_workers(monkeypatch):
    redis_client = FakeRedis()
    calls = []
    monkeypatch.setattr(aggregation_cache, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(aggregation_cache, "get_cache_key", lambda *args: "shared-key")
    aggregation_cache._cache.clear()

    @aggregation_cache.cache_aggregation
    def load_rows(start_year, end_year, station_ids, filters=None):
        calls.append(1)
        return [(start_year, end_year, tuple(station_ids))]

    result = load_rows(2026, 2028, [1, 2])
    aggregation_cache._cache.clear()  # Simulate a different application worker.
    restored = load_rows(2026, 2028, [1, 2])

    redis_key = "stations:aggregation:shared-key"
    assert result == restored == [(2026, 2028, (1, 2))]
    assert calls == [1]
    assert pickle.loads(redis_client.values[redis_key]) == result
    assert redis_client.ttls[redis_key] == 1800


def test_clear_aggregation_cache_deletes_shared_redis_entries(monkeypatch):
    redis_client = FakeRedis()
    cache_key = "stations:aggregation:some-key"
    redis_client.values[cache_key] = pickle.dumps(["cached"])
    monkeypatch.setattr(aggregation_cache, "get_redis_client", lambda: redis_client)

    aggregation_cache.clear_aggregation_cache()

    assert cache_key in redis_client.deleted
    assert cache_key not in redis_client.values
