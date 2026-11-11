from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g
from flask_login import LoginManager
from jinja2 import Environment

from app.fuel.routes import fuel_routes as routes


FIELDS = (
    "numb", "d", "r", "name_ext", "vedomstvo", "be", "gk", "gkf", "er",
    "n1", "n2", "p1", "p2", "addr", "codegor", "note",
)
SELECT_FIELDS = ("d", "r", "vedomstvo", "be", "gk", "gkf", "er", "codegor")


@pytest.fixture
def inline_client(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test")
    LoginManager(app)
    user = SimpleNamespace(is_authenticated=True, has_admin=True)
    group = SimpleNamespace(id=22, **{field: None for field in FIELDS})
    group.note = "Keep this note"
    app.before_request(lambda: setattr(g, "_login_user", user))
    app.add_url_rule("/inline/<int:equipment_group_id>", view_func=routes.equipment_group_inline_edit,
                     methods=["GET", "POST"])
    monkeypatch.setattr("app.common.services.database_version_filter.get_current_db_version_id", lambda: 7)
    resolver = Mock(return_value=group)
    monkeypatch.setattr("app.common.services.version_entity_resolve_services.load_by_id_with_version_or_anchor", resolver)
    monkeypatch.setattr(routes.db.session, "get", lambda model, pk: group)
    monkeypatch.setattr(routes, "log_to_db", Mock())
    update = Mock()
    monkeypatch.setattr(routes, "update_equipment_group_from_form", update)
    with app.test_client() as client:
        yield client, user, group, update, resolver


@pytest.mark.parametrize("field", FIELDS)
def test_save_one_field_uses_card_service_and_returns_persisted_value(inline_client, field):
    client, _, group, update, resolver = inline_client

    def persist(group_id, form):
        assert group_id == 22
        assert form == {field: "12"}
        setattr(group, field, 12 if field in SELECT_FIELDS or field == "numb" else "12")
        return True, "Saved", [(field, "old", "12")], group_id

    update.side_effect = persist
    response = client.post("/inline/10", data={"field": field, "value": " 12 ", "note": "Unwanted overwrite"})
    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["value"] == "12"
    assert response.json["group_id"] == 22
    if field != "note":
        assert group.note == "Keep this note"
    assert resolver.call_args.args[1:] == (10, 7)
    assert field in routes.log_to_db.call_args.kwargs["details"]


@pytest.mark.parametrize("method", ["get", "post"])
def test_read_only_user_cannot_load_or_save_editor(inline_client, method):
    client, user, _, update, resolver = inline_client
    user.has_admin = False
    response = getattr(client, method)("/inline/10")
    assert response.status_code == 403
    assert response.json["success"] is False
    update.assert_not_called()
    resolver.assert_not_called()


def test_save_checks_csrf(inline_client):
    client, _, _, update, _ = inline_client
    with client.session_transaction() as session:
        session["csrf_token"] = "expected-token"
    response = client.post("/inline/10", data={"field": "note", "value": "new"})
    assert response.status_code == 400
    update.assert_not_called()
    update.return_value = (False, "Validation failed", [], None)
    response = client.post("/inline/10", data={"field": "note", "value": "new", "csrf_token": "expected-token"})
    assert response.json["message"] == "Validation failed"
    update.assert_called_once()


@pytest.mark.parametrize("data", [
    {"field": "database_version_id", "value": "2"},
    {"field": "note"},
    {"field": "numb", "value": "not a number"},
    {"field": "gk", "value": "1.5"},
])
def test_invalid_payload_is_not_saved(inline_client, data):
    client, _, _, update, _ = inline_client
    response = client.post("/inline/10", data=data)
    assert response.status_code == 400
    assert response.json["success"] is False
    update.assert_not_called()


@pytest.mark.parametrize("field", ["numb", "d", "codegor", "note"])
def test_clearing_a_field_is_saved_and_returned_as_empty_string(inline_client, field):
    client, _, group, update, _ = inline_client

    def persist(group_id, form):
        assert form == {field: ""}
        setattr(group, field, None)
        return True, "Saved", [(field, "old", "–")], group_id

    update.side_effect = persist
    response = client.post("/inline/10", data={"field": field, "value": ""})
    assert response.status_code == 200
    assert response.json["value"] == ""


def test_missing_group(inline_client):
    client, _, _, update, resolver = inline_client
    resolver.return_value = None
    response = client.post("/inline/10", data={"field": "note", "value": "new"})
    assert response.status_code == 404
    update.assert_not_called()


def test_card_validation_failure_is_returned_without_success(inline_client):
    client, _, _, update, _ = inline_client
    update.return_value = (False, "Duplicate code", [], None)
    response = client.post("/inline/10", data={"field": "numb", "value": "42"})
    assert response.status_code == 400
    assert response.json == {"success": False, "message": "Duplicate code"}
    routes.log_to_db.assert_not_called()


def test_unexpected_save_failure_returns_json(inline_client):
    client, _, _, update, _ = inline_client
    update.side_effect = RuntimeError("Database unavailable")
    response = client.post("/inline/10", data={"field": "note", "value": "new"})
    assert response.status_code == 500
    assert response.json["success"] is False
    routes.log_to_db.assert_not_called()


def test_choices_are_taken_from_card_context(inline_client, monkeypatch):
    client, _, _, _, _ = inline_client
    choices = {field: [["", "–"], [1, "First"], [9, "Other"]] for field in SELECT_FIELDS}
    monkeypatch.setattr(routes, "get_equipment_group_edit_context", lambda group_id: {
        f"{field}_choices": values for field, values in choices.items()
    })
    response = client.get("/inline/10")
    assert response.status_code == 200
    assert response.json["choices"] == choices


@pytest.mark.parametrize("admin", [False, True])
def test_all_fuel_cells_render_editors_only_for_admin(admin):
    source = Path("app/templates/fuel/equipment_groups/stations_equipment_groups.html").read_text(encoding="utf-8")
    macro = source[source.index("{% macro fuel_inline_field"):source.index("{% macro render_equipment_group_rows")]
    template = Environment(autoescape=True).from_string(macro + """
        {% for field in fields %}
        {% call fuel_inline_field(eg, field) %}Current label{% endcall %}
        {% endfor %}
    """)
    html = template.render(current_user=SimpleNamespace(has_admin=admin), fields=FIELDS,
                           eg=SimpleNamespace(id=4, **{field: '"<unsafe>' for field in FIELDS}))
    if admin:
        assert html.count("seg-fuel-input") == 16
        assert html.count("<select ") == 8
        assert html.count("<textarea ") == 7
        assert html.count("<input ") == 1
        assert html.count('class="seg-fuel-display"') == 16
        assert html.count("Current label") == 24  # visible text plus the initial select options
        assert html.count(' hidden') == 16
        assert "<unsafe>" not in html
    else:
        assert "seg-fuel-input" not in html
        assert html.count("Current label") == 16
