from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from flask import Flask, g
from flask_login import LoginManager, UserMixin, login_required, login_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy import Column, Integer, create_engine, event, insert, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base

from app.energy_consumption.routes import energy_consumption_bp
from app.energy_consumption.routes import data_refresh_routes as routes
from app.energy_consumption.services import data_refresh_services as refresh
from app.energy_consumption.services import ec_summary_page_cache as summary_cache
from app.energy_balance.services import energy_balance_cache as balance_cache
from app.extensions import cache, csrf


Base = declarative_base()


class ConsumptionSource(Base):
    __module__ = "app.energy_consumption.models.test_refresh_source"
    __tablename__ = "consumption_refresh_source"
    id = Column(Integer, primary_key=True)
    value = Column(Integer)


class UnrelatedSource(Base):
    __module__ = "app.logs.models.test_refresh_source"
    __tablename__ = "consumption_refresh_log"
    id = Column(Integer, primary_key=True)


class Reader(UserMixin):
    id = 2
    username = "reader"
    roles = [SimpleNamespace(name="generation-reader")]


@pytest.fixture
def consumption_cache(monkeypatch):
    monkeypatch.setattr(refresh, "get_redis_client", lambda: None)
    monkeypatch.setattr(refresh, "_data_revision", 0)
    monkeypatch.setattr(summary_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(summary_cache, "_cache_generation", 0)
    monkeypatch.setattr(summary_cache, "_memory_cache", {})
    monkeypatch.setattr(balance_cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(balance_cache, "_cache_generation", 0)
    monkeypatch.setattr(balance_cache, "_data_revision", 0)
    monkeypatch.setattr(balance_cache, "_memory_cache", {})
    handlers = (
        ("after_flush", refresh._tracker._after_flush),
        ("do_orm_execute", refresh._tracker._orm_write),
        ("after_commit", refresh._tracker._after_commit),
        ("after_soft_rollback", refresh._tracker._after_soft_rollback),
    )
    previously_registered = {name for name, handler in handlers if event.contains(Session, name, handler)}
    refresh.init_energy_consumption_change_events()
    refresh.init_energy_consumption_change_events()
    yield
    for name, handler in handlers:
        if name not in previously_registered:
            event.remove(Session, name, handler)


@pytest.fixture
def consumption_db(consumption_cache):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def consumption_app(consumption_cache):
    root = Path(__file__).resolve().parents[2] / "app"
    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))
    app.config.update(TESTING=True, SECRET_KEY="consumption-refresh-test", TEST_VALUE="100")
    csrf.init_app(app)
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache"})
    manager = LoginManager(app)
    manager.user_loader(lambda user_id: Reader())

    @app.before_request
    def load_version():
        g.current_db_version = 7

    @app.get("/test-login")
    def login():
        login_user(Reader())
        return generate_csrf()

    for endpoint in (
        "station_bp.database_versions", "start.index", "refdata_bp.refdata",
        "logs.view_logs", "auth.logout", "auth.login", "auth.register", "start.export_table_excel",
    ):
        app.add_url_rule("/test-navigation/" + endpoint, endpoint, lambda: "")
    app.register_blueprint(energy_consumption_bp, url_prefix="/energy_consumption")

    def page(**kwargs):
        context = {"csrf_token": generate_csrf(), "value": app.config["TEST_VALUE"]}
        app.update_template_context(context)
        return app.jinja_env.from_string('''{% extends 'base.html' %}
          {% block content %}
          <table><tbody><tr><td><input id="test-value" value="{{ value }}"></td>
          <td><textarea id="test-note">note</textarea></td></tr></tbody></table>
          <input id="filter" value="filter">
          {% endblock %}''').render(context)

    for endpoint in routes._PAGE_ENDPOINTS:
        app.view_functions[endpoint] = login_required(page)
    return app


def test_api_requires_login_and_csrf_and_only_clears_cache(consumption_app):
    client = consumption_app.test_client()
    assert client.get("/energy_consumption/data-revision/").status_code == 401
    assert client.get("/energy_consumption/russia/").status_code == 401
    assert client.post("/energy_consumption/refresh-data/").status_code == 400
    token = client.get("/test-login").text
    status = client.get("/energy_consumption/data-revision/")
    assert status.json == {"ok": True, "revision": "7:data:0"}
    assert "no-store" in status.headers["Cache-Control"]
    assert client.get("/energy_consumption/refresh-data/").status_code == 405
    response = client.post("/energy_consumption/refresh-data/", headers={"X-CSRFToken": token})
    assert response.json == {"ok": True, "revision": "7:data:0"}
    assert "no-store" in response.headers["Cache-Control"]
    assert summary_cache._get_cache_generation() == 1
    assert consumption_app.config["TEST_VALUE"] == "100"
    assert refresh.get_energy_consumption_data_revision() == 0


def test_every_html_page_gets_exactly_one_button_but_apis_do_not(consumption_app):
    client = consumption_app.test_client()
    client.get("/test-login")
    checked = set()
    for rule in consumption_app.url_map.iter_rules():
        if rule.endpoint not in routes._PAGE_ENDPOINTS:
            continue
        path = re.sub(r"<int:[^>]+>", "1", rule.rule)
        response = client.get(path + "?start_year=2024&end_year=2026")
        assert response.status_code == 200, path
        assert response.text.count('id="energyBalanceRefreshButton"') == 1, path
        assert '"revision": "7:data:0"' in response.text, path
        assert '"statusUrl": "/energy_consumption/data-revision/"' in response.text, path
        assert "no-store" in response.headers["Cache-Control"], path
        checked.add(rule.endpoint)
    assert checked == routes._PAGE_ENDPOINTS
    for rule in consumption_app.url_map.iter_rules():
        if rule.endpoint.startswith("energy_consumption_bp.") and rule.endpoint not in checked:
            consumption_app.view_functions[rule.endpoint] = lambda **kw: "<html>API or export</html>"
            path = re.sub(r"<[^>]+>", "test", rule.rule)
            with consumption_app.test_request_context(path):
                assert routes.inject_data_refresh() == {}


@pytest.mark.parametrize("scope,endpoint", [
    ("oes", "demand_summary_oes_data"),
    ("energy_zones", "demand_summary_energy_zones_data"),
    ("federal_districts", "demand_summary_federal_districts_data"),
])
def test_summary_json_cannot_be_served_from_browser_cache(consumption_app, monkeypatch, scope, endpoint):
    monkeypatch.setitem(consumption_app.view_functions, f"energy_consumption_bp.{endpoint}", lambda: {"rows": []})
    client = consumption_app.test_client()
    client.get("/test-login")
    response = client.get(f"/energy_consumption/summary/{scope}/data.json")
    assert response.json == {"rows": []}
    assert "no-store" in response.headers["Cache-Control"]
    assert "private" in response.headers["Cache-Control"]
    assert "energyBalanceRefreshButton" not in response.text


def test_real_hub_has_no_refresh_panel(consumption_app, monkeypatch):
    from app.energy_consumption.routes import energy_consumption_parameter_routes

    monkeypatch.setitem(consumption_app.view_functions, "energy_consumption_bp.hub", energy_consumption_parameter_routes.hub)
    monkeypatch.setattr(energy_consumption_parameter_routes, "can_edit_energy_consumption", lambda user: False)
    client = consumption_app.test_client()
    client.get("/test-login")
    response = client.get("/energy_consumption/")
    assert response.status_code == 200
    assert 'id="energyBalanceRefreshButton"' not in response.text


def test_revision_is_captured_before_page_build(consumption_app, monkeypatch):
    original = consumption_app.view_functions["energy_consumption_bp.russia_demand"]

    def page():
        refresh.publish_energy_consumption_data_change()
        return original()

    monkeypatch.setitem(consumption_app.view_functions, "energy_consumption_bp.russia_demand", page)
    client = consumption_app.test_client()
    client.get("/test-login")
    response = client.get("/energy_consumption/russia/")
    assert '"revision": "7:data:0"' in response.text
    assert client.get("/energy_consumption/data-revision/").json["revision"] == "7:data:1"


def test_commit_changes_revision_but_reads_noops_and_cache_clears_do_not(consumption_db):
    session = consumption_db
    session.add(ConsumptionSource(id=1, value=10))
    session.flush()
    assert refresh.get_energy_consumption_data_revision() == 0
    session.commit()
    assert refresh.get_energy_consumption_data_revision() == 1
    row = session.get(ConsumptionSource, 1)
    row.value = 10
    session.commit()
    session.add(UnrelatedSource(id=1))
    session.commit()
    summary_cache.clear_ec_summary_page_cache()
    assert refresh.get_energy_consumption_data_revision() == 1
    row.value = 20
    session.commit()
    assert refresh.get_energy_consumption_data_revision() == 2
    session.delete(row)
    session.commit()
    assert refresh.get_energy_consumption_data_revision() == 3


def test_consumption_commit_also_notifies_balances_without_cross_module_false_alerts(consumption_db, monkeypatch):
    from app.energy_balance.services import energy_balance_change_events as balance_events

    handlers = (
        ("after_flush", balance_events._tracker._after_flush),
        ("do_orm_execute", balance_events._tracker._orm_write),
        ("after_commit", balance_events._tracker._after_commit),
        ("after_soft_rollback", balance_events._tracker._after_soft_rollback),
    )
    previously_registered = {name for name, handler in handlers if event.contains(Session, name, handler)}
    balance_events.init_energy_balance_change_events()
    try:
        consumption_db.add(ConsumptionSource(value=10))
        consumption_db.commit()
        assert refresh.get_energy_consumption_data_revision() == 1
        assert balance_cache.get_energy_balance_data_revision() == 1
        monkeypatch.setattr(UnrelatedSource, "__module__", "app.energy_balance.models.test_refresh_source")
        consumption_db.add(UnrelatedSource(id=1))
        consumption_db.commit()
        assert balance_cache.get_energy_balance_data_revision() == 2
        assert refresh.get_energy_consumption_data_revision() == 1
    finally:
        for name, handler in handlers:
            if name not in previously_registered:
                event.remove(Session, name, handler)


def test_bulk_import_and_update_publish_after_commit(consumption_db):
    session = consumption_db
    session.execute(insert(ConsumptionSource), [{"value": 10}, {"value": 20}])
    assert refresh.get_energy_consumption_data_revision() == 0
    session.commit()
    assert refresh.get_energy_consumption_data_revision() == 1
    session.execute(update(ConsumptionSource).values(value=30))
    session.commit()
    assert refresh.get_energy_consumption_data_revision() == 2


def test_failed_and_nested_transactions_do_not_publish_early(consumption_db):
    session = consumption_db
    with session.begin():
        nested = session.begin_nested()
        session.add(ConsumptionSource(id=1, value=10))
        session.flush()
        nested.rollback()
    assert refresh.get_energy_consumption_data_revision() == 0
    session.add_all([ConsumptionSource(id=1, value=10), ConsumptionSource(id=1, value=20)])
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert refresh.get_energy_consumption_data_revision() == 0
    with session.begin():
        with session.begin_nested():
            session.add(ConsumptionSource(id=2, value=10))
        assert refresh.get_energy_consumption_data_revision() == 0
    assert refresh.get_energy_consumption_data_revision() == 1


@pytest.mark.parametrize("module", [
    "app.generation.models.station.station_gaes_charge_consumption_model",
    "app.power_demand.models.test_refresh",
    "app.energy_balance.models.test_refresh",
    "app.electrical_intensity.models.test_refresh",
    "app.generation.prospective_places.models.test_refresh",
    "app.fuel.models.test_refresh",
    "app.refdata.models.energy_systems.regional_energy_system_model",
    "app.territories.models.territory",
])
def test_other_module_changes_do_not_notify_consumption(consumption_db, monkeypatch, module):
    monkeypatch.setattr(ConsumptionSource, "__module__", module)
    consumption_db.add(ConsumptionSource(value=10))
    consumption_db.commit()
    assert refresh.get_energy_consumption_data_revision() == 0


def test_shared_revision_is_independent_of_cache_generation(consumption_cache, monkeypatch):
    class RedisStub:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def incr(self, key):
            self.values[key] = self.values.get(key, 0) + 1
            return self.values[key]

    redis = RedisStub()
    monkeypatch.setattr(refresh, "get_redis_client", lambda: redis)
    monkeypatch.setattr(summary_cache, "get_redis_client", lambda: redis)
    refresh.publish_energy_consumption_data_change()
    assert summary_cache._get_cache_generation() == 1
    monkeypatch.setattr(refresh, "_data_revision", 0)
    assert refresh.get_energy_consumption_data_revision() == 1
    summary_cache.clear_ec_summary_page_cache()
    assert refresh.get_energy_consumption_data_revision() == 1
    redis.incr(refresh._REDIS_DATA_REVISION_KEY)
    assert refresh.get_energy_consumption_data_revision() == 2

@pytest.mark.parametrize("foreign_change", [None, "before", "between"])
def test_save_response_only_acknowledges_own_commits(consumption_app, consumption_db, monkeypatch, foreign_change):
    def other_tab():
        # A separate request must not be acknowledged as this tab's save.
        with consumption_app.app_context(), consumption_app.test_request_context("/other-tab"):
            refresh.publish_energy_consumption_data_change()

    def save():
        if foreign_change == "before":
            other_tab()
        consumption_db.add(ConsumptionSource(value=10))
        consumption_db.commit()
        if foreign_change == "between":
            other_tab()
        consumption_db.add(ConsumptionSource(value=20))
        consumption_db.commit()
        return {"ok": True}

    monkeypatch.setitem(consumption_app.view_functions, "energy_consumption_bp.demand_summary_save_cell", save)
    client = consumption_app.test_client()
    token = client.get("/test-login").text
    response = client.post("/energy_consumption/summary/cell", headers={
        "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest",
    })
    assert response.status_code == 200
    if foreign_change:
        assert "X-Consumption-Revision" not in response.headers
    else:
        assert response.headers["X-Consumption-Revision-Before"] == "7:data:0"
        assert response.headers["X-Consumption-Revision"] == "7:data:2"
    assert client.get("/energy_consumption/data-revision/").json["revision"] == (
        "7:data:3" if foreign_change else "7:data:2"
    )
