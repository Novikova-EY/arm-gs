from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.energy_consumption.routes import energy_consumption_parameter_routes as routes
from app.energy_consumption.services import energy_consumption_parameter_services as services
from app.energy_consumption.services import ec_display_cache


@pytest.mark.parametrize("path,variant", [
    ("/russia/", routes.CODE_WITHOUT_NT),
    ("/russia_with_nt/", routes.CODE_WITH_NT),
    ("/ees_russia/", routes.CODE_WITHOUT_NT),
    ("/ees_russia_with_nt/", routes.CODE_WITH_NT),
    ("/ees/", None),
])
def test_detail_live_save_returns_json_with_row_ids(app, monkeypatch, path, variant):
    app.register_blueprint(routes.energy_consumption_bp, url_prefix="/energy_consumption")
    monkeypatch.setattr(routes, "can_edit_energy_consumption", lambda user: True)
    save = Mock()
    monkeypatch.setattr(routes.dps, "save_demand_rows_from_post", save)
    monkeypatch.setattr(routes.dps, "get_demand_rows", lambda *a, **k: [SimpleNamespace(
        id=17, year_number=2025, energy_consumption_mln_kvt_ch=Decimal("123.456"),
        energy_consumption_sipr_mln_kvt_ch=None,
    )])
    response = app.test_client().post("/energy_consumption" + path, data={
        "slice_year[]": "2025", "ec_mln[]": "123.456", "row_id[]": "",
    }, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200
    assert response.json == {"ok": True, "rows": [{
        "id": 17, "year": 2025, "ec_mln": "123.456", "ec_sipr": "",
    }]}
    assert save.call_args.kwargs.get("perimeter_variant_code") == variant


@pytest.mark.parametrize("allowed,error,status", [
    (False, None, 403), (True, ValueError("Invalid number"), 400),
    (True, RuntimeError("Database failure"), 500),
])
def test_detail_live_save_failure_is_not_a_successful_redirect(app, monkeypatch, allowed, error, status):
    app.register_blueprint(routes.energy_consumption_bp, url_prefix="/energy_consumption")
    monkeypatch.setattr(routes, "can_edit_energy_consumption", lambda user: allowed)
    monkeypatch.setattr(routes.dps, "save_demand_rows_from_post", Mock(side_effect=error))
    response = app.test_client().post("/energy_consumption/russia/", headers={
        "X-Requested-With": "XMLHttpRequest",
    })
    assert response.status_code == status
    assert response.json["ok"] is False
    assert "Database failure" not in response.json["error"]


def test_detail_wrapper_passes_perimeter_to_real_save_service(monkeypatch):
    model = routes.RussiaFederationEnergyConsumptionParameter
    save = Mock(return_value=(1, 0))
    monkeypatch.setattr(services, "save_energy_consumption_rows_from_post", save)
    assert services.save_demand_rows_from_post(
        model, None, None, {}, perimeter_variant_code=routes.CODE_WITH_NT,
    ) == (1, 0)
    assert save.call_args.kwargs["perimeter_variant_code"] == routes.CODE_WITH_NT


def test_invalidation_clears_cached_energy_balance_data(app, monkeypatch):
    from app.energy_balance.services import energy_balance_cache as balance_cache
    from app.energy_consumption.services import ec_summary_page_cache as summary_cache

    monkeypatch.setattr(balance_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(summary_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(balance_cache, "get_current_db_version_id", lambda: 7)
    from app.extensions import cache
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache"})
    with app.app_context():
        balance_cache.clear_energy_balance_cache()
        loader = Mock(side_effect=[{"consumption": 10}, {"consumption": 20}])
        assert balance_cache.cached_load("consumption", (), loader) == {"consumption": 10}
        assert balance_cache.cached_load("consumption", (), loader) == {"consumption": 10}
        ec_display_cache.invalidate_energy_consumption_display_caches(version_id=7)
        assert balance_cache.cached_load("consumption", (), loader) == {"consumption": 20}


def test_detail_template_compiles(app):
    app.jinja_env.get_template("energy_consumption/energy_consumption_edit.html")
