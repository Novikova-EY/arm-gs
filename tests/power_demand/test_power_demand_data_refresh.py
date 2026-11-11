from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from flask import Flask, g
from flask_login import LoginManager, UserMixin, login_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy import Column, Integer, create_engine, event
from sqlalchemy.orm import Session, declarative_base

from app.extensions import cache, csrf
from app.power_demand.routes import power_demand_bp
from app.power_demand.routes import data_refresh_routes as routes
from app.power_demand.services import data_refresh_services as refresh
from app.power_demand.services import pd_summary_page_cache as page_cache

Base = declarative_base()


class LoadSource(Base):
    __module__ = "app.power_demand.models.test_refresh"
    __tablename__ = "power_demand_refresh_test"
    id = Column(Integer, primary_key=True)
    value = Column(Integer)


class Reader(UserMixin):
    id = 1
    username = "reader"
    roles = [SimpleNamespace(name="power-demand-reader")]


@pytest.fixture
def load_db(monkeypatch):
    monkeypatch.setattr(refresh, "get_redis_client", lambda: None)
    monkeypatch.setattr(refresh, "_data_revision", 0)
    monkeypatch.setattr(page_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(page_cache, "_memory_cache", {})
    monkeypatch.setattr(page_cache, "_cache_generation", 0)
    handlers = (
        ("after_flush", refresh._tracker._after_flush),
        ("do_orm_execute", refresh._tracker._orm_write),
        ("after_commit", refresh._tracker._after_commit),
        ("after_soft_rollback", refresh._tracker._after_soft_rollback),
    )
    registered = {name for name, handler in handlers if event.contains(Session, name, handler)}
    refresh.init_power_demand_change_events()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
    for name, handler in handlers:
        if name not in registered:
            event.remove(Session, name, handler)


@pytest.fixture
def load_app(load_db):
    root = Path(__file__).resolve().parents[2] / "app"
    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))
    app.config.update(TESTING=True, SECRET_KEY="loads-refresh-test")
    csrf.init_app(app)
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache"})
    manager = LoginManager(app)
    manager.user_loader(lambda user_id: Reader())

    @app.before_request
    def version():
        g.current_db_version = 7

    @app.get("/test-login")
    def login():
        login_user(Reader())
        return generate_csrf()

    for endpoint in (
        "station_bp.database_versions", "start.index", "refdata_bp.refdata",
        "logs.view_logs", "auth.logout", "auth.login", "auth.register", "start.export_table_excel",
    ):
        app.add_url_rule("/navigation/" + endpoint, endpoint, lambda: "")
    app.register_blueprint(power_demand_bp, url_prefix="/power_demand")

    def page(**kwargs):
        context = {"csrf_token": generate_csrf()}
        app.update_template_context(context)
        return app.jinja_env.from_string('''{% extends 'base.html' %}
        {% block content %}
        <table id="powerDemandSummaryTable" class="power-demand-summary-table"><tbody><tr>
        <td class="summary-year-cell"><input id="test-value" class="form-control fuel-param-input" value="100" data-initial="100"></td>
        <td id="calculated" class="summary-year-cell">200</td></tr></tbody></table>
        {% endblock %}''').render(context)

    for endpoint in routes._PAGE_ENDPOINTS:
        app.view_functions[endpoint] = page
    return app


def test_html_coverage_and_home_exclusion(load_app):
    client = load_app.test_client()
    client.get("/test-login")
    checked = set()
    for rule in load_app.url_map.iter_rules():
        if rule.endpoint not in routes._PAGE_ENDPOINTS:
            continue
        path = re.sub(r"<int:[^>]+>", "1", rule.rule)
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text.count('id="energyBalanceRefreshButton"') == 1, path
        assert '"revision": "7:data:0"' in response.text, path
        assert "no-store" in response.headers["Cache-Control"]
        checked.add(rule.endpoint)
    assert checked == routes._PAGE_ENDPOINTS
    with load_app.test_request_context("/power_demand/"):
        assert routes.inject_data_refresh() == {}
    for rule in load_app.url_map.iter_rules():
        if rule.endpoint.endswith("_data") and "GET" in rule.methods:
            load_app.view_functions[rule.endpoint] = lambda: {"rows": []}
            response = client.get(rule.rule)
            assert "no-store" in response.headers["Cache-Control"]
            assert "energyBalanceRefreshButton" not in response.text


def test_refresh_security_and_no_false_change(load_app):
    client = load_app.test_client()
    assert client.get("/power_demand/data-revision/").status_code == 401
    assert client.post("/power_demand/refresh-data/").status_code == 400
    token = client.get("/test-login").text
    response = client.post("/power_demand/refresh-data/", headers={"X-CSRFToken": token})
    assert response.json == {"ok": True, "revision": "7:data:0"}
    assert client.get("/power_demand/data-revision/").json["revision"] == "7:data:0"
    assert page_cache._get_cache_generation() == 1


@pytest.mark.parametrize("endpoint,path", [
    ("demand_summary_save_cell", "/summary/cell"),
    ("ozp_maxima_save", "/ozp_maxima/save"),
    ("russia_demand", "/russia/"),
])
@pytest.mark.parametrize("foreign", [False, True])
def test_only_own_commits_are_acknowledged(load_app, load_db, endpoint, path, foreign):
    def save():
        if foreign:
            with load_app.app_context(), load_app.test_request_context("/other-tab"):
                refresh.publish_power_demand_data_change()
        load_db.add(LoadSource(value=100))
        load_db.commit()
        return {"ok": True}

    load_app.view_functions["power_demand_bp." + endpoint] = save
    client = load_app.test_client()
    token = client.get("/test-login").text
    response = client.post("/power_demand" + path, headers={
        "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest",
    })
    assert response.status_code == 200
    if foreign:
        assert "X-Power-Demand-Revision" not in response.headers
    else:
        assert response.headers["X-Power-Demand-Revision-Before"] == "7:data:0"
        assert response.headers["X-Power-Demand-Revision"] == "7:data:1"


@pytest.mark.parametrize("module,expected", [
    ("app.power_demand.models.test_refresh", 1),
    ("app.energy_consumption.models.test_refresh", 1),
    ("app.energy_balance.models.test_refresh", 0),
    ("app.generation.models.station.station_model", 0),
    ("app.electrical_intensity.models.test_refresh", 0),
    ("app.generation.prospective_places.models.test_refresh", 0),
    ("app.fuel.models.test_refresh", 0),
    ("app.refdata.models.test_refresh", 0),
    ("app.territories.models.test_refresh", 0),
])
def test_only_loads_and_consumption_notify_loads(load_db, monkeypatch, module, expected):
    monkeypatch.setattr(LoadSource, "__module__", module)
    load_db.add(LoadSource(value=100))
    load_db.commit()
    assert refresh.get_power_demand_data_revision() == expected


def test_revision_follows_commit_not_flush_or_cache_clear(load_db):
    load_db.add(LoadSource(value=100))
    load_db.flush()
    assert refresh.get_power_demand_data_revision() == 0
    load_db.rollback()
    assert refresh.get_power_demand_data_revision() == 0
    load_db.add(LoadSource(value=200))
    load_db.commit()
    assert refresh.get_power_demand_data_revision() == 1
    page_cache.invalidate_power_demand_display_caches()
    assert refresh.get_power_demand_data_revision() == 1


@pytest.mark.parametrize("path,endpoint", [
    ("/russia/", "russia_demand"),
    ("/russia_with_nt/", "russia_with_nt_demand"),
    ("/ees/", "ees_demand"),
    ("/ees_with_nt/", "ees_with_nt_demand"),
])
@pytest.mark.parametrize("outcome", ["saved", "invalid", "denied"])
def test_real_detail_handlers_return_live_save_json(load_app, monkeypatch, path, endpoint, outcome):
    from app.power_demand.routes import demand_parameter_routes as parameters

    load_app.view_functions["power_demand_bp." + endpoint] = getattr(parameters, endpoint)
    monkeypatch.setattr(parameters, "can_edit_power_demand", lambda user: outcome != "denied")
    monkeypatch.setattr(parameters, "_csrf", lambda: SimpleNamespace(validate_on_submit=lambda: True))

    def save(*args, **kwargs):
        if outcome == "invalid":
            raise ValueError("Неверная дата")

    monkeypatch.setattr(parameters.dps, "save_demand_rows_from_post", save)
    monkeypatch.setattr(parameters.dps, "get_demand_rows", lambda *args, **kwargs: [
        SimpleNamespace(id=1, year_number=2024, is_historical_maximum=False, max_power_consumption_mw=100),
        SimpleNamespace(id=2, year_number=None, is_historical_maximum=True, max_power_consumption_mw=200),
    ])
    client = load_app.test_client()
    token = client.get("/test-login").text
    response = client.post("/power_demand" + path, headers={
        "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest",
    })
    assert response.status_code == {"saved": 200, "invalid": 400, "denied": 403}[outcome]
    assert response.json["ok"] is (outcome == "saved")
    if outcome == "saved":
        assert response.json["rows"] == [
            {"id": 1, "year": "2024", "p_max": "100"},
            {"id": 2, "year": "hist", "p_max": "200"},
        ]


def test_real_power_demand_hub_has_no_refresh(load_app):
    from app.power_demand.routes.demand_parameter_routes import hub

    load_app.view_functions["power_demand_bp.hub"] = hub
    client = load_app.test_client()
    client.get("/test-login")
    response = client.get("/power_demand/")
    assert response.status_code == 200
    assert 'id="energyBalanceRefreshButton"' not in response.text
