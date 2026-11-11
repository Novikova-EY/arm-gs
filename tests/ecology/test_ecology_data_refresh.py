from types import SimpleNamespace

from flask import Flask

from app.ecology.routes import data_refresh_routes
from app.ecology.routes.ecology_bp import ecology_bp


def test_refresh_route_clears_comparison_data_cache(monkeypatch):
    cleared = []
    monkeypatch.setattr(data_refresh_routes, "clear_comparison_cache", lambda: cleared.append(True))

    with Flask(__name__).test_request_context("/ecology/refresh-data/", method="POST"):
        response = data_refresh_routes.refresh_data.__wrapped__()

    assert response.get_json() == {"ok": True}
    assert response.headers["Cache-Control"] == "no-store, private"
    assert cleared == [True]


def test_all_ecology_data_tabs_have_refresh_control():
    app = Flask(__name__)
    app.register_blueprint(ecology_bp, url_prefix="/ecology")

    page_endpoints = {
        rule.endpoint
        for rule in app.url_map.iter_rules()
        if rule.endpoint in data_refresh_routes._PAGE_ENDPOINTS
    }

    assert page_endpoints == data_refresh_routes._PAGE_ENDPOINTS
    assert {
        "ecology_bp.gis_tek_pg",
        "ecology_bp.gis_tek_pollutants",
        "ecology_bp.gis_tes_fuel_comparison",
        "ecology_bp.operating_tes_table",
        "ecology_bp.new_tes_table",
        "ecology_bp.calculation_summary",
        "ecology_bp.totals_summary",
    } <= page_endpoints


def test_refresh_control_is_not_injected_on_ecology_hub(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(ecology_bp, url_prefix="/ecology")

    with app.test_request_context("/ecology/"):
        monkeypatch.setattr(data_refresh_routes, "request", SimpleNamespace(endpoint="ecology_bp.hub"))
        assert data_refresh_routes.inject_data_refresh() == {}

        monkeypatch.setattr(data_refresh_routes, "request", SimpleNamespace(endpoint="ecology_bp.gis_tek_pg"))
        assert data_refresh_routes.inject_data_refresh()["ecology_refresh"]["refreshUrl"]


def test_ecology_pages_are_not_cached_between_refreshes(monkeypatch):
    monkeypatch.setattr(
        data_refresh_routes,
        "request",
        SimpleNamespace(endpoint="ecology_bp.calculation_summary"),
    )
    response = Flask(__name__).response_class("page")

    response = data_refresh_routes.prevent_stale_page_response(response)

    assert response.headers["Cache-Control"] == "no-store, private"
