from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask, g, render_template_string
from flask_login import LoginManager, UserMixin, login_user
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, delete, event, insert, select, update
from sqlalchemy.orm import Session, declarative_base, relationship
from sqlalchemy.pool import StaticPool

from app.common.services import data_refresh_history as history
from app.extensions import cache, db
from app.logs.models.data_refresh_event_model import DataRefreshEvent, DataRefreshState
from config import SCHEMA_LOGS

@pytest.fixture(autouse=True)
def _patch_infrastructure():
    # These tests exercise real transactions rather than the suite's dummy db.session.
    yield


Base = declarative_base()


class Parent(Base):
    __module__ = "app.refdata.models.test_history"
    __tablename__ = "history_test_parent"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    database_version_id = Column(Integer)


class Source(Base):
    __module__ = "app.energy_consumption.models.test_history"
    __tablename__ = "history_test_source"
    id = Column(Integer, primary_key=True)
    value = Column(Integer)
    year_number = Column(Integer)
    database_version_id = Column(Integer)
    name = Column(String)
    note = Column(String)
    max_power_consumption_mw = Column(Numeric(25, 3))
    id_parent = Column(Integer, ForeignKey("history_test_parent.id"))
    parent = relationship(Parent)


class Other(Base):
    __module__ = "app.logs.models.test_history"
    __tablename__ = "history_test_other"
    id = Column(Integer, primary_key=True)


class Reader(UserMixin):
    id = "1"
    username = "reader"
    role_names = []
    roles = [SimpleNamespace(name="generation-reader")]


@pytest.fixture
def history_app(monkeypatch):
    from app.energy_consumption.routes import energy_consumption_bp
    from app.power_demand.routes import power_demand_bp
    from app.energy_balance.routes import energy_balance_bp
    from app.energy_consumption.routes import data_refresh_routes as ec_routes
    from app.power_demand.routes import data_refresh_routes as pd_routes
    from app.energy_balance.routes import data_refresh_routes as eb_routes
    from app.energy_consumption.services import data_refresh_services as ec
    from app.power_demand.services import data_refresh_services as pd
    from app.energy_balance.services import energy_balance_cache as eb

    for service in (ec, pd, eb):
        monkeypatch.setattr(service, "get_redis_client", lambda: None)
        monkeypatch.setattr(service, "_data_revision", 0)
    root = Path(__file__).resolve().parents[2] / "app"
    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))
    app.config.update(
        TESTING=True, SECRET_KEY="history-test", SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={"poolclass": StaticPool, "connect_args": {"check_same_thread": False},
                                   "execution_options": {"schema_translate_map": {SCHEMA_LOGS: None}}},
    )
    db.init_app(app)
    cache.init_app(app, config={"CACHE_TYPE": "SimpleCache"})
    manager = LoginManager(app)
    manager.user_loader(lambda _id: Reader())
    registered = [(name, handler) for name, handler in history._HANDLERS if event.contains(Session, name, handler)]
    history.init_data_refresh_history(app)
    history.init_data_refresh_history(app)

    @app.before_request
    def version():
        g.current_db_version = 7

    @app.get("/login")
    def login():
        login_user(Reader())
        return "ok"

    app.register_blueprint(energy_consumption_bp, url_prefix="/energy_consumption")
    app.register_blueprint(power_demand_bp, url_prefix="/power_demand")
    app.register_blueprint(energy_balance_bp, url_prefix="/energy_balance")

    def page(**_kwargs):
        return render_template_string('''<!doctype html><html><body>
        {% set data_refresh = energy_consumption_refresh or power_demand_refresh or energy_balance_refresh %}
        {% set csrf_token = 'test-token' %}{% include 'common/_data_refresh.html' %}
        <h1 class="text-center mb-4">Данные модуля</h1>
        <table><tbody><tr><td><input id="test-value" value="100"></td></tr></tbody></table>
        </body></html>''')

    for routes in (ec_routes, pd_routes, eb_routes):
        endpoints = routes._TABLE_ENDPOINTS if routes is eb_routes else routes._PAGE_ENDPOINTS
        for endpoint in endpoints:
            app.view_functions[endpoint] = page
    with app.app_context():
        Base.metadata.create_all(db.engine)
        DataRefreshState.__table__.create(db.engine)
        DataRefreshEvent.__table__.create(db.engine)
        with db.engine.begin() as connection:
            connection.execute(DataRefreshState.__table__.insert().values(id=1, epoch=str(uuid4()), revision=0))
    yield app
    for name, handler in history._HANDLERS:
        if (name, handler) not in registered:
            event.remove(Session, name, handler)
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def history_db(history_app):
    with history_app.app_context():
        g.current_db_version = 7
        with Session(db.engine) as session:
            yield session


def cursor(app, module="consumption"):
    with app.test_request_context():
        g.current_db_version = 7
        return history.capture_history(module)["historyCursor"]


def read_events(app, token, module="energy_consumption", **kwargs):
    client = app.test_client()
    client.get("/login")
    return client.get(f"/{module}/data-changes/", query_string={"history_cursor": token, **kwargs})


@pytest.mark.parametrize("source,expected_modules", [
    ("app.energy_consumption.models.test_history", {"consumption", "demand", "balance"}),
    ("app.power_demand.models.test_history", {"demand", "balance"}),
    ("app.energy_balance.models.test_history", {"balance"}),
    ("app.generation.models.station.station_model", {"balance"}),
    ("app.energy_balance.models.regional_energy_system_transfer_model", {"balance"}),
    ("app.energy_balance.models.station_energy_generation_model", {"balance"}),
    ("app.energy_balance.models.ee_balance_export_value_model", {"balance"}),
    ("app.energy_balance.models.ee_import_export_oes_value_model", {"balance"}),
    ("app.generation.prospective_places.models.test_history", set()),
    ("app.electrical_intensity.models.test_history", set()),
    ("app.fuel.models.test_history", set()),
    ("app.refdata.models.test_history", set()),
    ("app.territories.models.test_history", set()),
])
def test_status_and_history_follow_module_dependencies(
    history_app, history_db, monkeypatch, source, expected_modules,
):
    packages = {"consumption": "energy_consumption", "demand": "power_demand", "balance": "energy_balance"}
    tokens = {module: cursor(history_app, module) for module in packages}
    monkeypatch.setattr(Source, "__module__", source)
    history_db.add(Source(value=10, database_version_id=7))
    history_db.commit()
    client = history_app.test_client()
    client.get("/login")
    for module, package in packages.items():
        expected = int(module in expected_modules)
        status = client.get(f"/{package}/data-revision/", query_string={"history_cursor": tokens[module]})
        assert status.json["history"] == {"available": True, "count": expected}
        events = read_events(history_app, tokens[module], package).json["events"]
        assert len(events) == expected


def test_commit_rollback_noop_and_unrelated_rows(history_app, history_db):
    token = cursor(history_app)
    session = history_db
    session.add(Source(id=1, value=10, year_number=2025, database_version_id=7))
    session.flush()
    assert session.execute(select(DataRefreshState.__table__.c.revision)).scalar_one() == 0
    assert session.execute(select(DataRefreshEvent.__table__.c.revision)).all() == []
    session.rollback()
    assert read_events(history_app, token).json["events"] == []
    session.add(Source(id=1, value=10, year_number=2025, database_version_id=7))
    session.commit()
    assert len(read_events(history_app, token).json["events"]) == 1
    token = cursor(history_app)
    row = session.get(Source, 1)
    row.value = 10
    session.add(Other())
    session.commit()
    assert read_events(history_app, token).json["events"] == []
    row.value = 20
    session.commit()
    response = read_events(history_app, token)
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    item = response.json["events"][0]
    assert item["title"] == "Изменение данных"
    assert item["years"] == [2025]
    assert item["records"] == 1


def test_nested_rollback_and_outer_commit(history_app, history_db):
    token = cursor(history_app)
    with history_db.begin():
        history_db.add(Source(value=1, year_number=2025, database_version_id=7))
        history_db.flush()
        nested = history_db.begin_nested()
        history_db.add(Source(value=2, year_number=2030, database_version_id=7))
        history_db.flush()
        nested.rollback()
    events = read_events(history_app, token).json["events"]
    assert len(events) == 1
    assert events[0]["years"] == [2025]
    assert events[0]["records"] == 1


def test_nested_commit_defers_journal_until_outer_commit(history_app, history_db):
    token = cursor(history_app)
    with history_db.begin():
        with history_db.begin_nested():
            history_db.add(Source(value=1, database_version_id=7))
        assert history_db.execute(select(DataRefreshState.__table__.c.revision)).scalar_one() == 0
        history_db.add(Source(value=2, database_version_id=7))
    events = read_events(history_app, token).json["events"]
    assert len(events) == 1
    assert events[0]["records"] == 2


def test_versions_modules_bulk_and_private_actor(history_app, history_db, monkeypatch):
    tokens = {module: cursor(history_app, module) for module in ("consumption", "demand", "balance")}
    monkeypatch.setattr(Source, "__module__", "app.power_demand.models.test_history")
    history_db.add_all([Source(value=1, database_version_id=8), Source(value=2, database_version_id=7)])
    history_db.commit()
    assert read_events(history_app, tokens["consumption"]).json["events"] == []
    assert len(read_events(history_app, tokens["demand"], "power_demand").json["events"]) == 1
    assert len(read_events(history_app, tokens["balance"], "energy_balance").json["events"]) == 1
    token = cursor(history_app, "demand")
    history_db.execute(update(Source).values(value=3))
    history_db.commit()
    items = read_events(history_app, token, "power_demand").json["events"]
    assert len(items) == 1
    assert items[0]["years"] == []
    assert items[0]["records"] == 1
    assert len(items[0]["details"]) == 1
    assert items[0]["details"][0]["changes"] == ["Значение: было 2 → стало 3"]
    assert read_events(history_app, token).json["available"] is False


def test_import_grouping_across_commits_and_pagination(history_app, history_db):
    token = cursor(history_app)
    with history_app.test_request_context("/import"):
        g.current_db_version = 7
        history_db.add(Source(value=1, database_version_id=7))
        history_db.commit()
        history_db.add(Source(value=2, database_version_id=7))
        history_db.commit()
        operation_id = g.data_refresh_operation_id
    for i in range(22):
        history_db.add(Source(value=i, database_version_id=7))
        history_db.commit()
    with history_app.test_request_context("/import"):
        g.data_refresh_operation_id = operation_id
        history_db.add(Source(value=99, database_version_id=7))
        history_db.commit()
    first = read_events(history_app, token).json
    assert len(first["events"]) == 20
    second = read_events(history_app, token, before=first["nextBefore"]).json
    assert len(second["events"]) == 3
    assert second["nextBefore"] is None
    assert first["events"][0]["records"] == 3
    assert not ({item["id"] for item in first["events"]} & {item["id"] for item in second["events"]})


def test_cursor_epoch_auth_and_status(history_app, history_db):
    client = history_app.test_client()
    assert client.get("/energy_consumption/data-changes/").status_code == 401
    client.get("/login")
    token = cursor(history_app)
    status = client.get("/energy_consumption/data-revision/", query_string={"history_cursor": token})
    assert status.json["history"] == {"available": True, "count": 0}
    history_db.add(Source(value=1, database_version_id=7))
    history_db.commit()
    status = client.get("/energy_consumption/data-revision/", query_string={"history_cursor": token})
    assert status.json["history"]["count"] == 1
    assert read_events(history_app, token + "invalid").json["available"] is False
    with db.engine.begin() as connection:
        connection.execute(update(DataRefreshState.__table__).values(epoch=str(uuid4())))
    assert read_events(history_app, token).json["available"] is False


def test_bulk_insert_and_failed_commit(history_app, history_db):
    from sqlalchemy.exc import IntegrityError

    token = cursor(history_app)
    history_db.execute(insert(Source), [{"id": 1, "value": 1, "database_version_id": 7},
                                       {"id": 2, "value": 2, "database_version_id": 7}])
    history_db.commit()
    assert len(read_events(history_app, token).json["events"]) == 1
    token = cursor(history_app)
    history_db.add_all([Source(id=3, value=1), Source(id=3, value=2)])
    with pytest.raises(IntegrityError):
        history_db.commit()
    history_db.rollback()
    assert read_events(history_app, token).json["events"] == []


def test_import_kind_actor_and_object_visibility(history_app, history_db, monkeypatch):
    token = cursor(history_app)
    balance_token = cursor(history_app, "balance")
    monkeypatch.setattr(history, "_get_current_username", lambda: "private-user")
    with history_app.test_request_context("/upload") as context:
        context.request.url_rule = SimpleNamespace(endpoint="energy_consumption_bp.import_excel")
        history_db.add(Source(value=1, year_number=2025, database_version_id=7, name="ОЭС Урала"))
        history_db.commit()
    item = read_events(history_app, token).json["events"][0]
    assert item["title"] == "Импорт: сохранены изменения"
    assert item["actor"] == "Другой пользователь"
    assert item["objects"] == ["ОЭС Урала"]
    item = read_events(history_app, balance_token, "energy_balance").json["events"][0]
    assert item["objects"] == []
    assert item["details"] == []


@pytest.mark.parametrize("model_name,title", [("SummaryRowNote", "Изменение примечаний"),
                                              ("ConsumptionFormulaText", "Изменение формул")])
def test_text_changes_are_not_presented_as_numeric(history_app, history_db, model_name, title):
    original_name = Source.__name__
    try:
        Source.__name__ = model_name
        token = cursor(history_app)
        history_db.add(Source(value=1, database_version_id=7))
        history_db.commit()
        assert read_events(history_app, token).json["events"][0]["title"] == title
    finally:
        Source.__name__ = original_name


def test_database_error_is_explicit_and_does_not_break_status(history_app, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    token = cursor(history_app)

    def unavailable(*_args):
        raise SQLAlchemyError("history offline")

    monkeypatch.setattr(history, "_history_query", unavailable)
    response = read_events(history_app, token)
    assert response.status_code == 503
    assert "no-store" in response.headers["Cache-Control"]
    assert response.json["ok"] is False
    client = history_app.test_client()
    client.get("/login")
    response = client.get("/energy_consumption/data-revision/", query_string={"history_cursor": token})
    assert response.status_code == 200
    assert response.json["ok"] is True
    assert response.json["history"]["available"] is False


@pytest.mark.parametrize("path", ["/energy_consumption/russia/", "/power_demand/russia/",
                                  "/energy_balance/ee_balance/ees-rossii/"])
def test_page_captures_history_baseline_for_each_module(history_app, path):
    import json
    import re

    client = history_app.test_client()
    client.get("/login")
    response = client.get(path)
    config = json.loads(re.search(r'id="energy-balance-refresh-config" type="application/json">(.*?)</script>', response.text).group(1))
    assert config["historyCursor"]
    assert config["loadedAt"]
    assert config["historyVersion"] == 7
    assert config["historyUrl"].endswith("/data-changes/")


def test_only_selected_version_in_status_and_shared_operation(history_app, history_db):
    token = cursor(history_app)
    with history_app.test_request_context("/save"):
        history_db.add_all([
            Source(value=71, name="Current", database_version_id=7),
            Source(value=81, name="Secret", database_version_id=8),
            Source(value=91, name="Unscoped", database_version_id=None),
            Parent(name="Global", database_version_id=None),
        ])
        history_db.commit()
    response = read_events(history_app, token).json
    assert len(response["events"]) == 1
    item = response["events"][0]
    assert item["records"] == 1
    assert item["objects"] == ["Current"]
    assert len(item["details"]) == 1
    assert "Secret" not in str(response)
    assert "Unscoped" not in str(response)
    assert "Global" not in str(response)
    client = history_app.test_client()
    client.get("/login")
    assert client.get("/energy_consumption/data-revision/", query_string={"history_cursor": token}).json["history"]["count"] == 1
    token = cursor(history_app)
    history_db.add_all([Source(value=82, database_version_id=8), Source(value=92)])
    history_db.commit()
    assert read_events(history_app, token).json["events"] == []
    assert client.get("/energy_consumption/data-revision/", query_string={"history_cursor": token}).json["history"]["count"] == 0


def test_no_selected_version_does_not_show_unscoped_events(history_app, history_db, monkeypatch):
    monkeypatch.setattr(history, "get_current_db_version_id", lambda: None)
    token = cursor(history_app)
    history_db.add_all([Source(value=7, database_version_id=7), Source(value=9)])
    history_db.commit()
    assert read_events(history_app, token).json["events"] == []


def test_details_use_stored_old_value_names_and_decimal_precision(history_app, history_db):
    from decimal import Decimal

    history_db.add(Parent(id=1, name="ОЭС Урала", database_version_id=7))
    history_db.add(Source(id=1, id_parent=1, year_number=2025, database_version_id=7,
                          value=10, max_power_consumption_mw=Decimal("1234.125")))
    history_db.commit()
    token = cursor(history_app)
    row = history_db.get(Source, 1)
    history_db.expire(row, ["value", "max_power_consumption_mw"])
    row.value = 20
    row.max_power_consumption_mw = Decimal("1234.126")
    history_db.commit()
    detail = read_events(history_app, token).json["events"][0]["details"][0]
    assert "ОЭС Урала" in detail["object"]
    assert "2025" in detail["object"]
    assert detail["object"] == "ОЭС Урала · 2025"
    assert "Значение: было 10 → стало 20" in detail["changes"]
    assert "Максимальное потребление мощности, МВт: было 1234,125 → стало 1234,126" in detail["changes"]
    assert not any("database_version_id" in change for change in detail["changes"])


def test_note_changes_and_noop_with_expired_values(history_app, history_db):
    history_db.add(Source(id=1, value=10, note="Старое", database_version_id=7))
    history_db.commit()
    token = cursor(history_app)
    row = history_db.get(Source, 1)
    history_db.expire(row, ["value"])
    row.value = 10
    history_db.commit()
    assert read_events(history_app, token).json["events"] == []
    row.note = "Новое"
    history_db.commit()
    item = read_events(history_app, token).json["events"][0]
    assert item["title"] == "Изменение примечаний"
    assert item["details"][0]["changes"] == ["Примечание: было Старое → стало Новое"]


def test_moving_between_versions_never_exposes_other_versions_values(history_app, history_db, monkeypatch):
    token7 = cursor(history_app)
    monkeypatch.setattr(history, "get_current_db_version_id", lambda: 8)
    token8 = cursor(history_app)
    monkeypatch.setattr(history, "get_current_db_version_id", lambda: 7)
    history_db.add(Source(id=1, value=70, name="Old", database_version_id=7))
    history_db.commit()
    token7 = cursor(history_app)
    row = history_db.get(Source, 1)
    row.database_version_id = 8
    row.value = 80
    row.name = "New"
    history_db.commit()
    item7 = read_events(history_app, token7).json["events"][0]
    assert item7["title"] == "Удаление данных"
    assert "New" not in str(item7)
    assert "Значение: было 70 → стало не указано" in item7["details"][0]["changes"]
    monkeypatch.setattr(history, "get_current_db_version_id", lambda: 8)
    item8 = read_events(history_app, token8).json["events"][0]
    assert item8["title"] == "Добавление данных"
    assert "Old" not in str(item8)
    assert "Значение: было не указано → стало 80" in item8["details"][0]["changes"]


def test_bulk_insert_update_delete_preserve_versions_and_details(history_app, history_db):
    token = cursor(history_app)
    history_db.execute(insert(Source), [{"id": 1, "value": 7, "database_version_id": 7},
                                       {"id": 2, "value": 8, "database_version_id": 8},
                                       {"id": 3, "value": 9}])
    history_db.commit()
    items = read_events(history_app, token).json["events"]
    assert len(items) == 1
    assert items[0]["records"] == 1
    assert items[0]["details"][0]["changes"] == ["Значение: было не указано → стало 7"]
    token = cursor(history_app)
    history_db.execute(update(Source).where(Source.value >= 7).values(value=10))
    history_db.commit()
    items = read_events(history_app, token).json["events"]
    assert len(items) == 1
    assert items[0]["details"][0]["changes"] == ["Значение: было 7 → стало 10"]
    token = cursor(history_app)
    history_db.execute(update(Source).values(value=10))
    history_db.commit()
    assert read_events(history_app, token).json["events"] == []
    history_db.execute(delete(Source))
    history_db.commit()
    item = read_events(history_app, token).json["events"][0]
    assert item["title"] == "Удаление данных"
    assert item["records"] == 1
    assert item["details"][0]["changes"] == ["Значение: было 10 → стало не указано"]


def test_old_summary_is_not_given_invented_details(history_app, history_db):
    token = cursor(history_app)
    history_db.add(Source(value=1, database_version_id=7))
    history_db.commit()
    with db.engine.begin() as connection:
        table = DataRefreshEvent.__table__
        summary = dict(connection.execute(select(table.c.summary)).scalar_one())
        summary.pop("details")
        connection.execute(update(table).values(summary=summary))
    item = read_events(history_app, token).json["events"][0]
    assert item["details"] == []
    assert "impact" not in item


def test_legacy_unscoped_events_are_excluded_even_for_admin(history_app, history_db, monkeypatch):
    token = cursor(history_app)
    history_db.add(Source(value=7, database_version_id=7))
    history_db.commit()
    with db.engine.begin() as connection:
        table = DataRefreshEvent.__table__
        record = dict(connection.execute(select(table)).mappings().one())
        record.update(revision=2, operation_id=str(uuid4()), database_version_id=None,
                      summary={"records": 1, "years": [2030], "category": "Private", "objects": ["Secret"],
                               "details": [{"object": "Secret", "changes": ["Private values"]}]})
        connection.execute(table.insert().values(**record))
        connection.execute(update(DataRefreshState.__table__).values(revision=2))
    monkeypatch.setattr(Reader, "role_names", ["admin"])
    response = read_events(history_app, token).json
    assert len(response["events"]) == 1
    assert "Secret" not in str(response)
    assert "2030" not in str(response)


def test_bulk_delete_loader_criteria_and_update_by_primary_key(history_app, history_db):
    from sqlalchemy.orm import with_loader_criteria

    history_db.add_all([Source(id=1, value=7, database_version_id=7), Source(id=2, value=8, database_version_id=8)])
    history_db.commit()
    token = cursor(history_app)
    history_db.execute(delete(Source).options(with_loader_criteria(Source, Source.database_version_id == 8)))
    history_db.commit()
    assert read_events(history_app, token).json["events"] == []
    history_db.execute(update(Source), [{"id": 1, "value": 70}])
    history_db.commit()
    item = read_events(history_app, token).json["events"][0]
    assert item["details"][0]["changes"] == ["Значение: было 7 → стало 70"]
