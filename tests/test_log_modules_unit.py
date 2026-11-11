from datetime import datetime, timezone
from pathlib import Path
from importlib import import_module
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, g
from flask.templating import render_template
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.logs.models.log_model import Log
from app.logs.routes import log_routes
from app.logs.services.logging_service import log_to_db
from app.logs.services.module_labels import MODULE_LABELS, resolve_log_module
from config import SCHEMA_LOGS, SCHEMA_REFDATA

REAL_SESSION = db.session


@pytest.fixture
def journal(monkeypatch):
    for module in ("electrical_intensity", "economics", "energy_consumption", "energy_balance",
                   "power_demand", "ecology", "territories", "rational_structure"):
        import_module(f"app.{module}.models")

    app = Flask(__name__)
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite://",
                      SQLALCHEMY_ENGINE_OPTIONS={"execution_options": {
                          "schema_translate_map": {SCHEMA_LOGS: None, SCHEMA_REFDATA: None}}})
    monkeypatch.setattr(db, "session", REAL_SESSION)
    db.init_app(app)
    app.register_blueprint(log_routes.logs_bp, url_prefix="/log")
    app.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(str(Path(__file__).resolve().parents[1] / "app" / "templates")),
    ])
    monkeypatch.setattr(log_routes, "render_template", render_template)
    monkeypatch.setattr(log_routes, "current_user", SimpleNamespace(is_authenticated=False))
    with app.app_context():
        DatabaseVersion.__table__.create(db.engine)
        Log.__table__.create(db.engine)
        execute = db.session.execute

        def execute_with_clock(statement, *args, **kwargs):
            if str(statement).startswith("SELECT now() AT TIME ZONE"):
                return SimpleNamespace(scalar=lambda: datetime.now(timezone.utc))
            return execute(statement, *args, **kwargs)

        monkeypatch.setattr(db.session, "execute", execute_with_clock)
        g.current_db_version = None
        yield app
        db.session.remove()


@pytest.mark.parametrize("blueprint,module", MODULE_LABELS.items())
def test_log_writer_records_request_module(journal, blueprint, module):
    @journal.route("/event", endpoint=f"{blueprint}.event")
    def write_event():
        log_to_db("tester", "Изменение", entity_type="station")
        return "ok"

    assert journal.test_client().get("/event").status_code == 200
    record = db.session.query(Log).one()
    assert record.module == module
    assert record.action == "Изменение"


def test_background_and_explicit_modules_are_saved(journal):
    log_to_db("tester", "Импорт", entity_type="rational_structure")
    log_to_db("tester", "Изменение", module="Топливо")
    log_to_db("tester", "Служебное событие")
    db.session.add(Log(username="tester", action="Прямая запись", entity_type="ecology"))
    db.session.commit()
    assert [record.module for record in db.session.query(Log).order_by(Log.id)] == [
        "Рациональная структура", "Топливо", "Система", "Экология",
    ]
    assert resolve_log_module("  Топливо  ") == "Топливо"


def test_filter_sort_and_pagination_keep_selected_module(journal):
    db.session.add_all([
        Log(username="tester", action=f"Изменение {i}", module="Рациональная структура")
        for i in range(12)
    ] + [Log(username="tester", action="Чужое изменение", module="Топливо"),
         Log(username="tester", action="Открыта страница: Турбины", module="Рациональная структура")])
    db.session.commit()
    client = journal.test_client()
    response = client.get("/log/logs", query_string={
        "module": "Рациональная структура", "sort_by": "module", "sort_dir": "asc", "per_page": 10,
        "show_page_events": "false",
    })
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert ">Модуль</a>" in html
    assert "Изменение 11" in html
    assert "Чужое изменение" not in html
    assert "Открыта страница: Турбины" not in html
    from html.parser import HTMLParser

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.urls = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.urls.extend(value for key, value in attrs if key == "href")

    links = Links()
    links.feed(html)
    for url in links.urls:
        args = parse_qs(urlsplit(url).query)
        if args:
            assert args["module"] == ["Рациональная структура"]
            assert args["show_page_events"] == ["false"]
    next_url = next(url for url in links.urls if parse_qs(urlsplit(url).query).get("page") == ["2"])
    last_page = client.get(next_url).get_data(as_text=True)
    assert "Изменение 1" in last_page and "Изменение 0" in last_page
    assert "Изменение 11" not in last_page
    visits = client.get("/log/logs", query_string={
        "module": "Рациональная структура", "show_page_events": "true",
    }).get_data(as_text=True)
    assert "Открыта страница: Турбины" in visits


@pytest.mark.parametrize("path,endpoint,title,module", [
    ("/energy_consumption/", "energy_consumption_bp.hub", "Спрос", "Спрос"),
    ("/electrical_intensity/electrical_intensity_fo/",
     "electrical_intensity_root_bp.electrical_intensity", "Электроемкость по ФО",
     "Долгосрочный прогноз потребления"),
])
@pytest.mark.parametrize("accept_encoding", ["identity", "gzip"])
def test_page_visits_are_saved_and_visible_by_default(
    journal, monkeypatch, path, endpoint, title, module, accept_encoding,
):
    import runpy

    from flask_compress import Compress
    from app.logs.services import page_view_logging as visits

    Compress(journal)
    visits.init_page_view_logging(journal)
    monkeypatch.setattr("app.create_app", lambda: journal)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "run.py"), run_name="test_run")
    monkeypatch.setattr(visits.logging_service_mod, "log_to_db", log_to_db)
    monkeypatch.setattr(visits, "current_user", SimpleNamespace(username="reader", is_authenticated=True))
    markup = f"<html><title>{title}</title><body>{'Страница ' * 100}</body></html>"
    journal.add_url_rule(path, endpoint, lambda: markup)
    client = journal.test_client()
    response = client.get(path, headers={
        "Sec-Fetch-Dest": "document", "Accept": "text/html", "Accept-Encoding": accept_encoding,
    })
    assert response.status_code == 200
    if accept_encoding == "gzip":
        import gzip

        assert response.headers["Content-Encoding"] == "gzip"
        assert gzip.decompress(response.data).decode("utf-8") == markup
    else:
        assert response.get_data(as_text=True) == markup
    record = db.session.query(Log).one()
    assert record.username == "reader"
    assert record.module == module
    assert record.entity_type == "page"
    assert record.action == f"Открыта страница: {title}"
    assert f"url={path}" in record.details

    html = client.get("/log/logs", query_string={"module": module}).get_data(as_text=True)
    assert record.action in html
    assert f"url={path}" in html
    assert "show_page_events=true" in html

    hidden = client.get("/log/logs", query_string={
        "module": module, "show_page_events": "false",
    }).get_data(as_text=True)
    assert record.action not in hidden
    assert "show_page_events=false" in hidden

    checked = client.get("/log/logs", query_string=[
        ("show_page_events", "true"), ("show_page_events", "false"),
    ]).get_data(as_text=True)
    assert record.action in checked


def test_module_sort_orders_different_modules(journal):
    db.session.add_all([
        Log(username="tester", action="Событие топлива", module="Топливо"),
        Log(username="tester", action="Событие генерации", module="Генерация"),
    ])
    db.session.commit()
    client = journal.test_client()
    ascending = client.get("/log/logs?sort_by=module&sort_dir=asc").get_data(as_text=True)
    descending = client.get("/log/logs?sort_by=module&sort_dir=desc").get_data(as_text=True)
    assert ascending.index("Событие генерации") < ascending.index("Событие топлива")
    assert descending.index("Событие топлива") < descending.index("Событие генерации")
