from app.energy_balance.services import energy_balance_cache as balance_cache
from app.generation.services.station_services import aggregation_cache


def test_balance_refresh_bypasses_stale_station_aggregation_without_clearing_other_consumers(monkeypatch):
    monkeypatch.setattr(aggregation_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(balance_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(aggregation_cache, "_cache", {})
    monkeypatch.setattr(balance_cache, "_cache_generation", 0)
    monkeypatch.setattr(balance_cache, "_memory_cache", {})
    monkeypatch.setattr("app.common.services.database_version_filter.get_current_db_version_id", lambda: 7)
    values = {"capacity": 100}

    @aggregation_cache.cache_aggregation
    def capacity(start_year, end_year, station_ids, filters=None):
        return values["capacity"]

    def balance_capacity():
        return capacity(2026, 2026, [1], {
            "_energy_balance_revision": f"eb:{balance_cache.get_energy_balance_cache_generation()}"
        })

    assert capacity(2026, 2026, [1]) == 100
    assert balance_capacity() == 100
    values["capacity"] = 200
    assert balance_capacity() == 100
    balance_cache.clear_energy_balance_cache()
    assert balance_capacity() == 200
    assert capacity(2026, 2026, [1]) == 100
