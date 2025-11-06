import io
import types
import os
import sys
import pytest
from flask import Flask

# Добавляем корень проекта в sys.path для импортов вида `from app...`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch


@pytest.fixture(autouse=True)
def _patch_infrastructure():
    """Глобальные моки: транзакции, логирование, choices_cache, чтобы не дергать БД."""
    class _DummyNoAutoflush:
        def __enter__(self):
            return None
        def __exit__(self, exc_type, exc, tb):
            return False

    class _DummySession:
        def __init__(self):
            self.no_autoflush = _DummyNoAutoflush()
        def get(self, *a, **k):
            return None
        def flush(self):
            return None
        def rollback(self):
            return None
        def commit(self):
            return None
        def __call__(self, *a, **k):
            # имитируем scoped_session(), который вызывается как функция
            return self

    dummy_session = _DummySession()

    with (
        patch("app.common.services.tranzaction_services.db.session", new=dummy_session),
        patch("app.common.services.tranzaction_services._commit_with_retry", new=lambda: None),
        patch("app.logs.services.logging_service.log_to_db", new=lambda *a, **k: None),
        patch("app.common.services.choices_cache_service.choices_cache.get_choices", new=lambda *a, **k: []),
        patch("app.common.services.database_version_services.get_current_version", new=lambda: None),
        patch("app.common.services.get_services.energy_systems.energy_system_type_get_services.get_energy_system_type_list_full", new=lambda: []),
        patch("app.common.services.get_services.energy_systems.union_energy_system_get_services.get_union_energy_system_list_full", new=lambda: []),
        patch("app.common.services.get_services.energy_systems.regional_energy_system_get_services.get_regional_energy_system_list_full", new=lambda: []),
        patch("app.common.services.get_services.territories.regional_district_get_services.get_regional_district_list_full", new=lambda: []),
        patch("app.common.services.get_services.energy_systems.synchronous_area_get_services.get_synchronous_area_list_full", new=lambda: []),
        patch("app.common.services.get_services.energy_systems.energy_zone_get_services.get_energy_zone_list_full", new=lambda: []),
        patch("app.refdata.models.fuels.fuel_type_model.FuelType", new=types.SimpleNamespace(id=1)),
        patch("app.refdata.routes.fuels.fuel_routes.FuelType", new=types.SimpleNamespace(id=1), create=True),
        patch("flask.render_template", new=lambda *a, **k: ""),
    ):
        yield


@pytest.fixture
def app():
    templates_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "templates"))
    static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "static"))
    app = Flask(__name__, template_folder=templates_path, static_folder=static_path)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        WTF_CSRF_ENABLED=False,
        LOGIN_DISABLED=True,  # отключаем login_required для тестов роутов
    )

    # Регистрируем только refdata blueprint, чтобы не тянуть весь app factory
    from app.refdata.routes import refdata_bp
    app.register_blueprint(refdata_bp, url_prefix="/refdata")

    # Заглушка блюпринта станций для ссылок в base.html
    from flask import Blueprint
    station_bp = Blueprint("station_bp", __name__)
    @station_bp.route("/generation/stations/database_versions")
    def database_versions():
        return ""
    app.register_blueprint(station_bp)

    # current_user для шаблонов
    @app.context_processor
    def inject_current_user():
        return {"current_user": types.SimpleNamespace(is_authenticated=False)}

    # Заглушка auth.login/register для ссылок в base.html
    auth_bp = Blueprint("auth", __name__)
    @auth_bp.route("/auth/login")
    def login():
        return ""
    @auth_bp.route("/auth/register")
    def register():
        return ""
    app.register_blueprint(auth_bp, url_prefix="/")
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class DummyPagination:
    def __init__(self, items=None, page=1, per_page=20, total=0):
        self.items = items or []
        self.page = page
        self.per_page = per_page
        self.total = total

    def __iter__(self):
        return iter(self.items)

    @property
    def pages(self):
        if self.per_page == 0:
            return 0
        return (self.total + self.per_page - 1) // self.per_page


@pytest.fixture
def dummy_pagination():
    return DummyPagination


@pytest.fixture
def dummy_excel_bytes():
    def _factory():
        buf = io.BytesIO()
        buf.write(b"PK\x03\x04dummy-xlsx")
        buf.seek(0)
        return buf
    return _factory


