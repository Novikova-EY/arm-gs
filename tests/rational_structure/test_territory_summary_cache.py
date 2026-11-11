from decimal import Decimal
from types import SimpleNamespace

from test_territory_summary import summary_sources

from app.energy_consumption.services import ec_summary_page_cache
from app.energy_consumption.services import energy_consumption_summary_services as consumption
from app.rational_structure.services import territory_summary_services as territory


class Query:
    def __init__(self, rows):
        self.rows = rows

    def order_by(self, *args):
        return self

    def filter(self, *args):
        return self

    def group_by(self, *args):
        return self

    def all(self):
        return self.rows


def test_other_worker_consumption_change_refreshes_gaes_and_territory_formulas(
    app, monkeypatch, summary_sources,
):
    charge_rows = [(10, 2025, Decimal("100"))]
    monkeypatch.setattr(ec_summary_page_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(ec_summary_page_cache, "_cache_generation", 0)
    monkeypatch.setattr(consumption, "_gaes_stations_for_entity_query",
                        lambda *args: Query([(10, "ГАЭС")]))
    monkeypatch.setattr(consumption, "db", SimpleNamespace(
        session=SimpleNamespace(query=lambda *args: Query(charge_rows)),
    ))
    monkeypatch.setattr(consumption.dps, "filter_parents_by_version", lambda query, model: query)
    monkeypatch.setattr(territory, "_gaes_charge_raw_station_values_for_entity",
                        consumption._gaes_charge_raw_station_values_for_entity)
    consumption.clear_gaes_charge_summary_cache()

    def read_rows():
        context = {
            "sheet": "years", "years": [2025], "version_id": 1,
            "selected_zone": SimpleNamespace(id=1),
            "rows": [{"key": str(key)} for key in range(6)],
        }
        territory.populate_territory_summary_rows(context)
        return {row["key"]: row for row in context["rows"]}

    try:
        with app.test_request_context():
            before = read_rows()
        # Another worker commits new source data and bumps the shared generation.
        # This worker keeps its previously populated LRU cache.
        charge_rows[:] = [(10, 2025, Decimal("250"))]
        ec_summary_page_cache._bump_cache_generation()
        with app.test_request_context():
            after = read_rows()

        assert before["0"]["cells"] == ["8900.123456789"]
        assert after["0"]["cells"] == ["8750.123456789"]
        assert before["0_with_gaes"]["cells"] == after["0_with_gaes"]["cells"]
        assert before["4"]["cells"] != after["4"]["cells"]
        assert before["5"]["cells"] != after["5"]["cells"]
    finally:
        consumption.clear_gaes_charge_summary_cache()
