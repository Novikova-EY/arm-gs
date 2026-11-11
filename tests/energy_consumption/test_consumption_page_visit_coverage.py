"""Покрытие маршрутов общим middleware посещений (без расчетов страниц)."""
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_login import LoginManager

from app.energy_consumption.routes import energy_consumption_bp
from app.economics.routes import economics_bp
from app.electrical_intensity.routes import electrical_intensity_root_bp, long_term_consumption_bp
from app.logs.services import page_view_logging as visits


CONSUMPTION_PAGES = [
    "/", "/formulas/", "/russia/", "/russia_with_nt/", "/ees_russia/",
    "/ees_russia_with_nt/", "/ees/", "/summary_table/start/", "/summary_table/",
    "/summary/oes/", "/summary/federal_districts/", "/summary/energy_zones/",
    "/summary/oes/gaes_charge/", "/summary/federal_districts/gaes_charge/",
    "/summary/energy_zones/gaes_charge/", "/summary_table/oes/",
    "/summary_table/federal_districts/", "/summary_table/energy_zones/",
    "/summary_table/oes/gaes_charge/", "/summary_table/federal_districts/gaes_charge/",
    "/summary_table/energy_zones/gaes_charge/",
]
for resource in ("regional_energy_systems", "energy_areas", "federal_districts", "energy_units",
                 "energy_zones", "regional_districts", "synchronous_areas", "union_energy_systems",
                 "energy_system_types"):
    CONSUMPTION_PAGES.extend([f"/{resource}/", f"/{resource}/1/"])

PAGES = [("/energy_consumption" + path, "Спрос") for path in CONSUMPTION_PAGES] + [
    ("/energy_consumption/electrical_intensity_start/", "Долгосрочный прогноз потребления"),
    ("/energy_consumption/electrical_intensity_fo/", "Долгосрочный прогноз потребления"),
    ("/electrical_intensity/electrical_intensity_fo/", "Долгосрочный прогноз потребления"),
    ("/electrical_intensity/formulas/", "Долгосрочный прогноз потребления"),
    ("/economics/ved_consumption/", "Экономика"),
    ("/economics/ved_consumption_formulas/", "Экономика"),
]


@pytest.fixture
def visit_env(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True)
    manager = LoginManager(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(energy_consumption_bp, url_prefix="/energy_consumption")
    app.register_blueprint(long_term_consumption_bp, url_prefix="/energy_consumption")
    app.register_blueprint(electrical_intensity_root_bp, url_prefix="/electrical_intensity")
    app.register_blueprint(economics_bp, url_prefix="/economics")
    visits.init_page_view_logging(app)
    records = []
    monkeypatch.setattr(visits, "current_user", SimpleNamespace(username="reader", is_authenticated=True))
    monkeypatch.setattr(visits.logging_service_mod, "log_to_db", lambda user, action, **kw: records.append(
        {"user": user.username, "action": action, **kw}
    ))
    return app, records


@pytest.mark.parametrize("path,module", PAGES)
def test_every_page_route_logs_one_visit_with_filters(visit_env, path, module):
    app, records = visit_env
    endpoint, _ = app.url_map.bind("localhost").match(path)
    app.view_functions[endpoint] = lambda **kw: "<html><title>Раздел потребления</title></html>"
    response = app.test_client().get(path + "?start_year=2024&end_year=2026", headers={
        "Sec-Fetch-Dest": "document", "Accept": "text/html",
    })
    assert response.status_code == 200
    assert len(records) == 1
    record = records[0]
    assert record["user"] == "reader"
    assert record["action"] == "Открыта страница: Раздел потребления"
    assert record["entity_type"] == "page"
    assert f"module={module}" in record["details"]
    assert f"url={path}?start_year=2024&end_year=2026" in record["details"]
    assert f"endpoint={endpoint}" in record["details"]


@pytest.mark.parametrize("mode", ["json", "fragment", "redirect", "attachment", "ajax"])
def test_background_requests_are_not_page_visits(visit_env, mode):
    app, records = visit_env
    endpoint = "energy_consumption_bp.hub"

    def response():
        if mode == "json":
            return {"ok": True}
        if mode == "fragment":
            return "<div>Ячейка</div>"
        if mode == "redirect":
            return "", 302, {"Location": "/energy_consumption/"}
        if mode == "attachment":
            return "<html><title>Экспорт</title></html>", 200, {"Content-Disposition": "attachment; filename=export.html"}
        return "<html><title>Фоновый запрос</title></html>"

    app.view_functions[endpoint] = response
    headers = {"Sec-Fetch-Dest": "empty"} if mode == "ajax" else {}
    app.test_client().get("/energy_consumption/", headers=headers)
    assert records == []
