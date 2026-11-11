import pytest
from flask import Blueprint, Flask, g, jsonify, session
from flask_login import LoginManager, UserMixin, current_user
from flask_sqlalchemy import SQLAlchemy

from app.auth.routes import auth_routes
from app.common.middleware import database_version_middleware as versions


@pytest.fixture
def version_app(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="version-restore-test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
    )
    database = SQLAlchemy(app)

    class Version(database.Model):
        id = database.Column(database.Integer, primary_key=True)
        is_active = database.Column(database.Boolean, default=False)

    class User(database.Model, UserMixin):
        id = database.Column(database.Integer, primary_key=True)
        username = database.Column(database.String)
        email = database.Column(database.String)
        last_database_version_id = database.Column(database.Integer)

        def check_password(self, password):
            return password == "password"

    manager = LoginManager(app)
    manager.user_loader(lambda user_id: database.session.get(User, int(user_id)))
    monkeypatch.setattr(versions, "db", database)
    monkeypatch.setattr(versions, "DatabaseVersion", Version)
    monkeypatch.setattr(versions, "get_default_version", lambda: database.session.get(Version, 30))
    monkeypatch.setattr(auth_routes, "db", database)
    monkeypatch.setattr(auth_routes, "User", User)
    monkeypatch.setattr(auth_routes, "log_to_db", lambda *args, **kwargs: None)

    from app.common.services import clear_all_caches
    from app.common.services.get_services.years import years_get_services

    monkeypatch.setattr(clear_all_caches, "clear_all_application_caches", lambda: None)
    monkeypatch.setattr(years_get_services, "clear_planning_period_year_caches", lambda: None)
    versions.init_database_version_middleware(app)
    app.register_blueprint(auth_routes.auth_bp)
    start = Blueprint("start", __name__)

    @start.get("/")
    def index():
        return "start"

    app.register_blueprint(start)

    @app.get("/page")
    def page():
        return jsonify(
            version=g.current_db_version,
            saved=current_user.last_database_version_id if current_user.is_authenticated else None,
            session_version=session.get("current_db_version"),
        )

    @app.post("/switch/<int:version_id>")
    def switch(version_id):
        versions.set_session_version(version_id)
        return page()

    with app.app_context():
        database.create_all()
        database.session.add_all([
            Version(id=10), Version(id=20, is_active=True), Version(id=30),
            User(id=1, username="first", email="first@test", last_database_version_id=10),
            User(id=2, username="new", email="new@test"),
            User(id=3, username="deleted", email="deleted@test", last_database_version_id=999),
            User(id=4, username="other", email="other@test", last_database_version_id=20),
        ])
        database.session.commit()
    return app, database, User, Version


def authenticated_client(app, user_id=1, session_version="missing"):
    client = app.test_client()
    with client.session_transaction() as saved:
        saved["_user_id"] = str(user_id)
        saved["_fresh"] = True
        if session_version != "missing":
            saved["current_db_version"] = session_version
    return client


@pytest.mark.parametrize("session_version", ["missing", None, 999])
def test_page_restores_profile_after_session_version_is_lost(version_app, session_version):
    app, database, User, _ = version_app
    client = authenticated_client(app, session_version=session_version)
    assert client.get("/page").json == {"version": 10, "saved": 10, "session_version": 10}
    assert client.get("/page").json["version"] == 10
    with app.app_context():
        assert database.session.get(User, 1).last_database_version_id == 10


@pytest.mark.parametrize("user_id", [2, 3])
def test_missing_or_deleted_profile_version_uses_active(version_app, user_id):
    app, database, User, _ = version_app
    client = authenticated_client(app, user_id, session_version=999)
    assert client.get("/page").json == {"version": 20, "saved": 20, "session_version": 20}
    with app.app_context():
        assert database.session.get(User, user_id).last_database_version_id == 20


def test_valid_session_selection_is_saved_and_not_replaced_by_active_version(version_app):
    app, database, User, _ = version_app
    client = authenticated_client(app, session_version=30)
    assert client.get("/page").json == {"version": 30, "saved": 30, "session_version": 30}
    with app.app_context():
        assert database.session.get(User, 1).last_database_version_id == 30


def test_switch_persists_immediately_and_survives_new_login(version_app):
    app, database, User, _ = version_app
    client = authenticated_client(app, session_version=10)
    assert client.post("/switch/30").json == {"version": 30, "saved": 30, "session_version": 30}
    with app.app_context():
        assert database.session.get(User, 1).last_database_version_id == 30
        assert database.session.get(User, 4).last_database_version_id == 20
    new_client = app.test_client()
    assert new_client.post("/login", data={"email": "first@test", "password": "password"}).status_code == 302
    assert new_client.get("/page").json["version"] == 30


@pytest.mark.parametrize("email,expected", [("first@test", 10), ("new@test", 20), ("deleted@test", 20)])
def test_login_replaces_previous_users_session_version(version_app, email, expected):
    app, _, _, _ = version_app
    client = authenticated_client(app, user_id=4, session_version=30)
    response = client.post("/login", data={"email": email, "password": "password"})
    assert response.status_code == 302
    assert response.location == "/"
    assert client.get("/page").json == {"version": expected, "saved": expected, "session_version": expected}


def test_logout_then_login_restores_last_selected_version(version_app):
    app, _, _, _ = version_app
    client = authenticated_client(app, session_version=10)
    client.post("/switch/30")
    assert client.get("/logout").status_code == 302
    client.post("/login", data={"email": "first@test", "password": "password"})
    assert client.get("/page").json["version"] == 30


def test_remembered_login_restores_profile_without_session_version(version_app):
    app, _, _, _ = version_app
    client = app.test_client()
    from flask_login.utils import encode_cookie

    with app.app_context():
        cookie = encode_cookie("1")
    client.set_cookie("remember_token", cookie)
    assert client.get("/page").json == {"version": 10, "saved": 10, "session_version": 10}


def test_no_active_version_keeps_existing_default_fallback(version_app):
    app, database, _, Version = version_app
    with app.app_context():
        database.session.get(Version, 20).is_active = False
        database.session.commit()
    assert authenticated_client(app, user_id=2).get("/page").json["version"] == 30
    assert authenticated_client(app, user_id=1).get("/page").json["version"] == 10


def test_selected_version_deleted_between_requests_falls_back_to_active(version_app):
    app, database, _, Version = version_app
    client = authenticated_client(app, session_version=10)
    assert client.get("/page").json["version"] == 10
    with app.app_context():
        database.session.delete(database.session.get(Version, 10))
        database.session.commit()
    assert client.get("/page").json == {"version": 20, "saved": 20, "session_version": 20}


def test_invalid_switch_does_not_change_saved_selection(version_app):
    app, database, User, _ = version_app
    client = authenticated_client(app, session_version=10)
    with pytest.raises(ValueError, match="999"):
        client.post("/switch/999")
    assert client.get("/page").json["version"] == 10
    with app.app_context():
        assert database.session.get(User, 1).last_database_version_id == 10


def test_empty_version_catalog_does_not_break_login(version_app):
    app, database, _, Version = version_app
    with app.app_context():
        Version.query.delete()
        database.session.commit()
    client = app.test_client()
    assert client.post("/login", data={"email": "first@test", "password": "password"}).status_code == 302
    assert client.get("/page").json == {"version": None, "saved": None, "session_version": None}
