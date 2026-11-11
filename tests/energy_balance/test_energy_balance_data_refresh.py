from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from flask import Flask, current_app, g
from flask_login import LoginManager, UserMixin, login_user
from flask_wtf.csrf import generate_csrf

from app.energy_balance.routes import energy_balance_bp
from app.energy_balance.services import energy_balance_cache as cache
from app.extensions import csrf
from test_energy_balance_change_events import BalanceValue, source_db


class Reader(UserMixin):
    id = 2
    roles = [SimpleNamespace(name="generation-reader")]


@pytest.fixture
def refresh_app(monkeypatch):
    monkeypatch.setattr(cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(cache, "_cache_generation", 0)
    monkeypatch.setattr(cache, "_data_revision", 0)
    monkeypatch.setattr(cache, "_memory_cache", {})
    root = Path(__file__).resolve().parents[2] / "app"
    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))
    app.config.update(TESTING=True, SECRET_KEY="refresh-test")
    csrf.init_app(app)
    manager = LoginManager(app)
    manager.user_loader(lambda user_id: Reader())

    @app.before_request
    def load_version():
        g.current_db_version = 7

    @app.get("/test-login")
    def login():
        login_user(Reader())
        return generate_csrf()

    app.register_blueprint(energy_balance_bp, url_prefix="/energy_balance")
    app.config["TEST_VALUE"] = "100"

    def table_page(slug):
        context = {"value": app.config["TEST_VALUE"]}
        if app.config.get("TEST_CSRF_AS_STRING", True):
            context["csrf_token"] = generate_csrf()
        current_app.update_template_context(context)
        return app.jinja_env.from_string('''<!doctype html><html><head><meta charset="utf-8"></head><body>
          {% include 'energy_balance/_data_refresh.html' %}
          <table><tbody><tr><td><input id="test-value" value="{{ value }}"></td>
          <td><textarea id="test-note">note</textarea></td></tr></tbody></table>
          <input id="filter" value="filter">
        </body></html>''').render(context)

    app.view_functions["energy_balance_bp.ee_balance_table"] = table_page
    return app


def test_status_and_refresh_require_login_csrf_and_do_not_modify_data(refresh_app):
    client = refresh_app.test_client()
    assert client.get("/energy_balance/data-revision/").status_code == 401
    assert client.post("/energy_balance/refresh-data/").status_code == 400
    token = client.get("/test-login").text
    status = client.get("/energy_balance/data-revision/")
    assert status.json == {"ok": True, "revision": "7:data:0"}
    assert "no-store" in status.headers["Cache-Control"]
    assert client.get("/energy_balance/refresh-data/").status_code == 405
    response = client.post("/energy_balance/refresh-data/", headers={"X-CSRFToken": token})
    assert response.status_code == 200
    assert response.json == {"ok": True, "revision": "7:data:0"}
    assert cache.get_energy_balance_cache_generation() == 1
    assert refresh_app.config["TEST_VALUE"] == "100"
    assert client.get("/energy_balance/data-revision/").json["revision"] == "7:data:0"
    assert client.patch("/energy_balance/ee_balance/ees-rossii/generation_value/", headers={"X-CSRFToken": token}, json={}).status_code == 403


def test_table_includes_revision_before_build_and_keeps_query(refresh_app):
    client = refresh_app.test_client()
    client.get("/test-login")
    response = client.get("/energy_balance/ee_balance/ees-rossii/?start_year=2024&end_year=2026")
    assert response.status_code == 200
    assert '"revision": "7:data:0"' in response.text
    assert "Обновить данные" in response.text
    assert 'id="energyBalanceRefreshLabel" aria-live="polite"' in response.text
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("as_string", [True, False])
def test_refresh_panel_accepts_string_and_callable_csrf(refresh_app, as_string):
    refresh_app.config["TEST_CSRF_AS_STRING"] = as_string
    client = refresh_app.test_client()
    client.get("/test-login")
    response = client.get("/energy_balance/ee_balance/ees-rossii/")
    assert response.status_code == 200
    token = re.search(r'data-csrf-token="([^"]+)"', response.text).group(1)
    refreshed = client.post(
        "/energy_balance/refresh-data/", headers={"X-CSRFToken": token}
    )
    assert refreshed.status_code == 200
    assert refreshed.json == {"ok": True, "revision": "7:data:0"}


def test_source_commit_changes_revision_but_reads_and_cache_clears_do_not(refresh_app, source_db):
    client = refresh_app.test_client()
    client.get("/test-login")
    url = "/energy_balance/data-revision/"
    assert client.get(url).json["revision"] == "7:data:0"
    source_db.add(BalanceValue(id=1, value=10))
    source_db.flush()
    assert client.get(url).json["revision"] == "7:data:0"
    source_db.commit()
    assert client.get(url).json["revision"] == "7:data:1"
    row = source_db.get(BalanceValue, 1)
    assert row.value == 10
    source_db.commit()
    cache.clear_energy_balance_cache()
    assert client.get(url).json["revision"] == "7:data:1"
    row.value = 20
    source_db.commit()
    assert client.get(url).json["revision"] == "7:data:2"


def test_change_during_build_remains_visible_to_status_poll(refresh_app, monkeypatch):
    original = refresh_app.view_functions["energy_balance_bp.ee_balance_table"]

    def build(slug):
        cache.publish_energy_balance_data_change()
        return original(slug)

    monkeypatch.setitem(refresh_app.view_functions, "energy_balance_bp.ee_balance_table", build)
    client = refresh_app.test_client()
    client.get("/test-login")
    response = client.get("/energy_balance/ee_balance/ees-rossii/")
    assert '"revision": "7:data:0"' in response.text
    assert client.get("/energy_balance/data-revision/").json["revision"] == "7:data:1"
