from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, jsonify, session
from flask_login import LoginManager, UserMixin, login_user
from flask_wtf.csrf import generate_csrf
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.exceptions import NotFound

from app.auth.services import user_settings_services as settings
from app.auth.routes import users_bp
from app.extensions import csrf


class TestUser(UserMixin):
    __test__ = False

    def __init__(self, user_id, admin=False):
        self.id = user_id
        self.username = f"user-{user_id}"
        self.roles = [SimpleNamespace(name="admin" if admin else "guest")]


@pytest.fixture
def settings_app(tmp_path, monkeypatch):
    app = Flask(__name__, template_folder="../../app/templates", instance_path=str(tmp_path))
    app.config.update(TESTING=True, SECRET_KEY="settings-test")
    csrf.init_app(app)
    manager = LoginManager(app)
    users = {1: TestUser(1, True), 2: TestUser(2), 3: TestUser(3)}
    manager.user_loader(lambda user_id: users.get(int(user_id)))
    settings.init_user_settings_reset(app)
    app.register_blueprint(users_bp, url_prefix="/users")

    @app.get("/login/<int:user_id>")
    def login(user_id):
        login_user(users[user_id])
        session["current_db_version"] = 42
        session["station_list_last_query_args"] = {"q": "saved"}
        session["generation_years_version_id"] = 42
        session["external_code_check_filters"] = {"name": "station"}
        session["fuel_db_import_job"] = "keep-job"
        return generate_csrf()

    @app.get("/page")
    def page():
        return jsonify(dict(session))

    def find_user(model, user_id):
        if user_id not in users:
            raise NotFound()
        return users[user_id]

    monkeypatch.setattr(settings.db, "get_or_404", find_user)
    monkeypatch.setattr(settings, "log_to_db", lambda *args: None)
    return app


def post_reset(client, token, user_id=2, **params):
    return client.post(f"/users/{user_id}/reset-settings", data={"csrf_token": token, **params})


def test_reset_is_targeted_and_preserves_auth_version_and_jobs(settings_app):
    admin, target, other = [settings_app.test_client() for _ in range(3)]
    token = admin.get("/login/1").text
    target.get("/login/2")
    other.get("/login/3")
    response = post_reset(admin, token, q="find", page="3", per_page="10", sort_by="email", sort_dir="desc")
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.location).query)
    assert query == {"q": ["find"], "page": ["3"], "per_page": ["10"], "sort_by": ["email"], "sort_dir": ["desc"]}
    data = target.get("/page").json
    for key in settings._SESSION_SETTINGS:
        assert key not in data
    assert data["_user_id"] == "2"
    assert data["current_db_version"] == 42
    assert data["fuel_db_import_job"] == "keep-job"
    assert data["csrf_token"]
    assert "station_list_last_query_args" in other.get("/page").json
    assert "station_list_last_query_args" in admin.get("/page").json
    with target.session_transaction() as saved:
        saved["station_list_last_query_args"] = {"q": "new"}
    assert target.get("/page").json["station_list_last_query_args"] == {"q": "new"}
    post_reset(admin, token)
    assert "station_list_last_query_args" not in target.get("/page").json


def test_reset_reaches_every_session_and_survives_new_app(settings_app):
    admin = settings_app.test_client()
    token = admin.get("/login/1").text
    clients = [settings_app.test_client(), settings_app.test_client()]
    for client in clients:
        client.get("/login/2")
    post_reset(admin, token)
    for client in clients:
        assert "station_list_last_query_args" not in client.get("/page").json
    with settings_app.app_context():
        token = settings.get_settings_reset_token(2)
    new_app = Flask("restarted", instance_path=settings_app.instance_path)
    with new_app.app_context():
        assert settings.get_settings_reset_token(2) == token
        assert settings.get_settings_reset_token(3) == ""


def test_reset_requires_admin_csrf_post_and_existing_user(settings_app):
    client = settings_app.test_client()
    assert client.get("/users/2/reset-settings").status_code == 405
    assert client.post("/users/2/reset-settings").status_code == 400
    guest_token = client.get("/login/3").text
    assert post_reset(client, guest_token).status_code == 403
    admin_token = client.get("/login/1").text
    assert post_reset(client, admin_token, 999).status_code == 404
    with client.session_transaction() as saved:
        saved.pop("_user_id")
    assert post_reset(client, admin_token).status_code == 401
    with settings_app.app_context():
        assert settings.get_settings_reset_token(2) == ""


def test_storage_failure_is_not_reported_as_success(settings_app, monkeypatch):
    client = settings_app.test_client()
    token = client.get("/login/1").text

    def fail(*args):
        raise PermissionError("read-only")

    monkeypatch.setattr(settings.os, "replace", fail)
    assert post_reset(client, token).status_code == 302
    with client.session_transaction() as saved:
        assert saved["_flashes"][-1][0] == "danger"
    assert not list((Path(settings_app.instance_path) / "user_settings_resets").iterdir())


def test_admin_can_reset_self(settings_app):
    client = settings_app.test_client()
    token = client.get("/login/1").text
    assert post_reset(client, token, 1).status_code == 302
    data = client.get("/page").json
    assert data["_user_id"] == "1"
    assert "station_list_last_query_args" not in data


def test_user_table_uses_separate_reset_forms(settings_app):
    from app.auth.forms.users_forms import UsersBulkForm
    from app.common.models.pagination import Pagination

    settings_app.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(str(Path(__file__).resolve().parents[2] / "app/templates")),
    ])
    with settings_app.test_request_context("/users"):
        user = TestUser(2)
        user.email = "test@example.com"
        html = settings_app.jinja_env.get_template("auth/users/users.html").render(
            current_user=TestUser(1, True), users=[user], roles=[], form=UsersBulkForm(),
            pagination=Pagination(page=1, per_page=50, total=1), q="", sort_by="id", sort_dir="asc", per_page=50,
        )
    assert 'form="reset-settings-2"' in html
    assert 'action="/users/2/reset-settings"' in html
    assert "return confirm(" in html
    reset_start = html.index('id="reset-settings-2"')
    reset_end = html.index('</form>', reset_start)
    bulk_start = html.index('<form method="POST" action="/users">')
    assert reset_end < bulk_start
