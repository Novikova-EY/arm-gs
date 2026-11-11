from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from flask import redirect

from app.common.services import economics_fd_data_cache as source_cache
from app.electrical_intensity.routes import electrical_intensity_fo_routes as routes
from app.electrical_intensity.services import electrical_intensity_services as forecast
from app.extensions import cache


class GaesQuery:
    def __init__(self, rows):
        self.rows = rows

    def select_from(self, *args):
        return self

    def join(self, *args):
        return self

    def filter(self, *args):
        return self

    def group_by(self, *args):
        return self

    def all(self):
        return self.rows


def test_forecast_reads_updated_gaes_charge_without_a_page_cache(monkeypatch):
    rows = [(2025, Decimal("100"))]
    monkeypatch.setattr(forecast, "db", SimpleNamespace(
        session=SimpleNamespace(query=lambda *args: GaesQuery(rows)),
    ))
    monkeypatch.setattr(forecast.dps, "filter_parents_by_version", lambda query, model: query)

    before = forecast._load_rf_gaes_charge_cells(display_years=[2025, 2026])
    rows[:] = [(2025, Decimal("250")), (2026, Decimal("300"))]
    after = forecast._load_rf_gaes_charge_cells(display_years=[2025, 2026])

    assert before == {2025: Decimal("100"), 2026: None}
    assert after == {2025: Decimal("250"), 2026: Decimal("300")}
    assert forecast._subtract_cell_maps({2025: Decimal("1000")}, after, [2025]) == {
        2025: Decimal("750"),
    }


@pytest.mark.parametrize("mode", ["manual", "excel"])
def test_forecast_source_cache_is_invalidated_after_commit(app, monkeypatch, mode):
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache"})
    source = {"value": Decimal("1"), "committed": False}
    monkeypatch.setattr(source_cache, "_bulk_load_ei_year_values", lambda **kwargs: {
        1: {(2, "graph_point", 2025): source["value"]},
    })
    monkeypatch.setattr(routes, "get_current_version", lambda: 7)
    monkeypatch.setattr(routes, "current_user", SimpleNamespace(has_admin=True))
    monkeypatch.setattr(routes, "parse_rounding_digits", lambda: 1)
    monkeypatch.setattr(routes, "csrf", lambda: SimpleNamespace(validate_on_submit=lambda: True))
    monkeypatch.setattr(routes, "redirect_preserving_query", lambda **kwargs: redirect("/forecast"))
    monkeypatch.setattr(routes, "save_electrical_intensity_from_post", lambda form: (1, 0))
    monkeypatch.setattr(routes, "import_electrical_intensity_from_xlsx_bytes", lambda raw: {"cells_written": 1})

    def commit():
        source.update(value=Decimal("2"), committed=True)

    monkeypatch.setattr(routes, "db", SimpleNamespace(
        session=SimpleNamespace(commit=commit, rollback=lambda: None),
    ))
    invalidate = routes.invalidate_economics_fd_data_cache

    def invalidate_after_commit(*args):
        assert source["committed"]
        invalidate(*args)

    monkeypatch.setattr(routes, "invalidate_economics_fd_data_cache", invalidate_after_commit)
    with app.test_request_context():
        before = forecast._load_fd_ei_year_values_map(version_id=7, fd_id=1)
    data = {"file": (BytesIO(b"workbook"), "forecast.xlsx")} if mode == "excel" else {}
    with app.test_request_context(method="POST", data=data):
        handler = routes.electrical_intensity_import_xlsx if mode == "excel" else routes.electrical_intensity
        response = handler.__wrapped__()
        assert response.status_code in (200, 302)
    with app.test_request_context():
        after = forecast._load_fd_ei_year_values_map(version_id=7, fd_id=1)

    assert before[(2, "graph_point", 2025)] == Decimal("1")
    assert after[(2, "graph_point", 2025)] == Decimal("2")
