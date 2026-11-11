from app.energy_balance.services import energy_balance_cache as cache


class RedisStub:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def setex(self, key, ttl, value):
        self.values[key] = value

    def scan(self, cursor, match, count):
        return 0, []


def test_other_worker_generation_invalidates_local_memory(monkeypatch):
    redis = RedisStub()
    monkeypatch.setattr(cache, "get_redis_client", lambda: redis)
    monkeypatch.setattr(cache, "get_current_db_version_id", lambda: 7)
    monkeypatch.setattr(cache, "_memory_cache", {})
    key = cache.make_energy_balance_cache_key("consumption")
    from datetime import datetime
    cache._memory_cache[key] = ({"value": "old"}, datetime.now())
    assert cache.cached_load("consumption", (), lambda: {"value": "new"}) == {"value": "old"}
    redis.incr(cache._REDIS_GENERATION_KEY)
    assert cache.cached_load("consumption", (), lambda: {"value": "new"}) == {"value": "new"}


def test_inflight_loader_cannot_repopulate_current_generation(monkeypatch):
    monkeypatch.setattr(cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(cache, "get_current_db_version_id", lambda: 7)
    monkeypatch.setattr(cache, "_memory_cache", {})

    def loading_during_save():
        cache.clear_energy_balance_cache()
        return {"value": "old"}

    cache.cached_load("consumption", (), loading_during_save)
    assert cache.cached_load("consumption", (), lambda: {"value": "new"}) == {"value": "new"}


def test_cache_clear_does_not_publish_data_change(monkeypatch):
    redis = RedisStub()
    monkeypatch.setattr(cache, "get_redis_client", lambda: redis)
    monkeypatch.setattr(cache, "_cache_generation", 0)
    monkeypatch.setattr(cache, "_data_revision", 0)
    monkeypatch.setattr(cache, "_memory_cache", {})
    cache.publish_energy_balance_data_change()
    assert cache.get_energy_balance_cache_generation() == 1
    assert cache.get_energy_balance_data_revision() == 1
    cache.clear_energy_balance_cache()
    assert cache.get_energy_balance_cache_generation() == 2
    assert cache.get_energy_balance_data_revision() == 1


def test_data_revision_is_shared_between_workers_independently_of_cache(monkeypatch):
    redis = RedisStub()
    monkeypatch.setattr(cache, "get_redis_client", lambda: redis)
    monkeypatch.setattr(cache, "_data_revision", 0)
    assert cache.get_energy_balance_data_revision() == 0
    redis.incr(cache._REDIS_GENERATION_KEY)
    assert cache.get_energy_balance_data_revision() == 0
    redis.incr(cache._REDIS_DATA_REVISION_KEY)
    assert cache.get_energy_balance_data_revision() == 1
    redis.incr(cache._REDIS_DATA_REVISION_KEY)
    assert cache.get_energy_balance_data_revision() == 2


def test_new_data_revision_never_exposes_old_cached_values(monkeypatch):
    redis = RedisStub()
    monkeypatch.setattr(cache, "get_redis_client", lambda: redis)
    monkeypatch.setattr(cache, "get_current_db_version_id", lambda: 7)
    monkeypatch.setattr(cache, "_cache_generation", 0)
    monkeypatch.setattr(cache, "_data_revision", 0)
    monkeypatch.setattr(cache, "_memory_cache", {})
    assert cache.cached_load("consumption", (), lambda: "old") == "old"
    increment = redis.incr

    def read_during_publication(key):
        result = increment(key)
        if key == cache._REDIS_DATA_REVISION_KEY:
            assert cache.get_energy_balance_data_revision() == 1
            assert cache.cached_load("consumption", (), lambda: "new") == "new"
        return result

    monkeypatch.setattr(redis, "incr", read_during_publication)
    cache.publish_energy_balance_data_change()
