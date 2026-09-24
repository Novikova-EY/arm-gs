# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, g, make_response, request as flask_request

from app.logs.services.logging_service import PAGE_VIEW_ACTION_PREFIX, log_to_db
from app.logs.services.page_view_logging import (
    extract_html_title,
    init_page_view_logging,
    maybe_log_page_view,
    module_label_for_endpoint,
    should_log_page_view,
)


def _html(title="Топливо", status=200):
    resp = make_response(
        f"<!DOCTYPE html><html><head><title>{title}</title></head><body>ok</body></html>",
        status,
    )
    resp.content_type = "text/html; charset=utf-8"
    return resp


def test_extract_html_title_strips_tags_and_whitespace():
    markup = "<html><head><title>  Спрос  <span>x</span>  </title></head></html>"
    assert extract_html_title(markup) == "Спрос x"


def test_module_label_for_known_blueprints():
    assert module_label_for_endpoint("fuel_bp.fuel_start") == "Топливо"
    assert module_label_for_endpoint("power_demand_bp.hub") == "Нагрузки"
    assert module_label_for_endpoint("station_bp.station_list") == "Генерация"
    assert module_label_for_endpoint("unknown_bp.page") == ""


def test_should_log_skips_when_route_already_logged_page_view(app):
    with app.test_request_context(
        "/fuel/",
        method="GET",
        headers={"Sec-Fetch-Dest": "document", "Accept": "text/html"},
    ):
        g.page_view_logged = True
        with patch(
            "app.logs.services.page_view_logging.current_user",
            SimpleNamespace(is_authenticated=True, username="tester"),
        ):
            assert should_log_page_view(flask_request, _html()) is False


def test_should_log_skips_ajax_and_json(app):
    with app.test_request_context(
        "/energy_consumption/summary/logs/oes",
        method="GET",
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    ):
        json_resp = make_response('{"ok": true}', 200)
        json_resp.content_type = "application/json"
        with patch(
            "app.logs.services.page_view_logging.current_user",
            SimpleNamespace(is_authenticated=True, username="tester"),
        ):
            assert should_log_page_view(flask_request, json_resp) is False


def test_should_log_skips_fetch_subresource(app):
    with app.test_request_context(
        "/fuel/",
        method="GET",
        headers={"Sec-Fetch-Dest": "empty", "Accept": "*/*"},
    ):
        with patch(
            "app.logs.services.page_view_logging.current_user",
            SimpleNamespace(is_authenticated=True, username="tester"),
        ):
            assert should_log_page_view(flask_request, _html()) is False


def test_should_log_document_navigation_for_authenticated_html(app):
    with app.test_request_context(
        "/refdata/",
        method="GET",
        headers={"Sec-Fetch-Dest": "document", "Accept": "text/html"},
    ):
        with patch(
            "app.logs.services.page_view_logging.current_user",
            SimpleNamespace(is_authenticated=True, username="tester"),
        ):
            assert flask_request.endpoint == "refdata_bp.refdata"
            assert should_log_page_view(flask_request, _html()) is True


def test_should_log_skips_anonymous(app):
    with app.test_request_context(
        "/",
        method="GET",
        headers={"Sec-Fetch-Dest": "document", "Accept": "text/html"},
    ):
        with patch(
            "app.logs.services.page_view_logging.current_user",
            SimpleNamespace(is_authenticated=False),
        ):
            assert should_log_page_view(flask_request, _html("Главная")) is False


def test_should_log_skips_post(app):
    with app.test_request_context(
        "/fuel/",
        method="POST",
        headers={"Sec-Fetch-Dest": "document", "Accept": "text/html"},
    ):
        with patch(
            "app.logs.services.page_view_logging.current_user",
            SimpleNamespace(is_authenticated=True, username="tester"),
        ):
            assert should_log_page_view(flask_request, _html()) is False


def test_maybe_log_page_view_writes_user_and_title(app):
    calls = []

    def _capture(*args, **kwargs):
        calls.append((args, kwargs))

    with app.test_request_context(
        "/refdata/",
        method="GET",
        headers={"Sec-Fetch-Dest": "document", "Accept": "text/html"},
    ):
        user = SimpleNamespace(is_authenticated=True, username="ivanov")
        with patch(
            "app.logs.services.page_view_logging.current_user",
            user,
        ), patch(
            "app.logs.services.logging_service.log_to_db",
            side_effect=_capture,
        ):
            maybe_log_page_view(_html("Экология"))

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] is user
    assert args[1] == f"{PAGE_VIEW_ACTION_PREFIX}: Экология"
    assert "url=/refdata/" in kwargs["details"]
    assert "endpoint=refdata_bp.refdata" in kwargs["details"]
    assert "module=Справочники" in kwargs["details"]
    assert kwargs["entity_type"] == "page"


def test_maybe_log_uses_module_fallback_for_default_title():
    from flask import Blueprint

    mini = Flask("page-view-fallback")
    bp = Blueprint("generation_bp", __name__)

    @bp.route("/")
    def generation_start():
        return "<!DOCTYPE html><html><head><title>АРМ ГС</title></head><body>ok</body></html>"

    mini.register_blueprint(bp, url_prefix="/generation")
    init_page_view_logging(mini)
    logged = []

    with mini.test_client() as client, patch(
        "app.logs.services.page_view_logging.current_user",
        SimpleNamespace(is_authenticated=True, username="tester"),
    ), patch(
        "app.logs.services.logging_service.log_to_db",
        side_effect=lambda *a, **k: logged.append((a, k)),
    ):
        client.get(
            "/generation/",
            headers={"Sec-Fetch-Dest": "document", "Accept": "text/html"},
        )

    assert len(logged) == 1
    action = logged[0][0][1]
    assert action.startswith(PAGE_VIEW_ACTION_PREFIX)
    assert "Генерация" in action


def test_init_page_view_logging_hooks_after_request():
    mini = Flask("page-view-test")
    init_page_view_logging(mini)
    logged = []

    @mini.route("/hub")
    def hub():
        return (
            "<!DOCTYPE html><html><head><title>Нагрузки</title></head><body>ok</body></html>"
        )

    with mini.test_client() as client, patch(
        "app.logs.services.page_view_logging.current_user",
        SimpleNamespace(is_authenticated=True, username="petrov"),
    ), patch(
        "app.logs.services.logging_service.log_to_db",
        side_effect=lambda *a, **k: logged.append((a, k)),
    ):
        client.get("/hub", headers={"Sec-Fetch-Dest": "document", "Accept": "text/html"})

    assert len(logged) == 1
    assert logged[0][0][1] == f"{PAGE_VIEW_ACTION_PREFIX}: Нагрузки"
    assert logged[0][0][0].username == "petrov"


def test_log_to_db_marks_page_view_flag(app):
    class DummySession:
        def __init__(self):
            self.info = {}

        def add(self, obj):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class DummyLog:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    with app.app_context(), patch(
        "app.logs.services.logging_service._make_independent_session",
        return_value=DummySession(),
    ), patch(
        "app.logs.services.logging_service.Log",
        new=DummyLog,
    ):
        g.page_view_logged = False
        log_to_db(user="tester", action="Открыта страница типов топлива")
        assert g.page_view_logged is True
