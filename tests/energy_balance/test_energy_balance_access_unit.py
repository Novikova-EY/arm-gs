# -*- coding: utf-8 -*-
"""Права чтения и записи для всего blueprint энергобалансов."""

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.datastructures import MultiDict

from app.energy_balance.routes import energy_balance_bp
from app.energy_balance.services.access_services import can_edit_energy_balance

bp_routes = import_module("app.energy_balance.routes.energy_balance_bp")


def _user(*names):
    return SimpleNamespace(
        is_authenticated=True,
        roles=[SimpleNamespace(name=name, name_full=name) for name in names],
    )


@pytest.mark.parametrize(
    "name",
    ["admin", "generation-admin", "generation-editor", "generation_admin",
     "generation_editor", "Админ", "Генерация-админ", "Генерация-редактор"],
)
def test_edit_roles_are_allowed_by_code_or_full_name(name):
    assert can_edit_energy_balance(_user(name))
    user = _user()
    user.roles = [SimpleNamespace(name="role-code", name_full=name)]
    assert can_edit_energy_balance(user)


@pytest.mark.parametrize(
    "names",
    [(), ("guest",), ("generation-reader",), ("fuel-admin",),
     ("fuel-editor",), ("load-admin",), ("Генерация-чтение",),
     ("fuel-admin", "generation-reader")],
)
def test_other_roles_are_read_only(names):
    assert not can_edit_energy_balance(_user(*names))


def test_anonymous_cannot_edit_even_with_edit_role():
    user = _user("admin")
    user.is_authenticated = False
    assert not can_edit_energy_balance(user)


@pytest.fixture
def balance_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test")
    LoginManager(app)
    app.register_blueprint(energy_balance_bp, url_prefix="/energy_balance")
    return app


def _url(rule):
    return rule.rule.replace("<slug>", "ees-rossii").replace("<int:row_id>", "1")


@pytest.mark.parametrize("role", ["guest", "generation-reader", "fuel-admin", "load-editor"])
def test_all_mutating_routes_deny_readers_before_calling_handler(balance_app, monkeypatch, role):
    monkeypatch.setattr(bp_routes, "current_user", _user(role))
    client = balance_app.test_client()
    checked = set()
    for rule in balance_app.url_map.iter_rules():
        if rule.endpoint in {"energy_balance_bp.ee_generation", "energy_balance_bp.ee_transfers"}:
            continue  # POST только применяет фильтры.
        for method in rule.methods - {"GET", "HEAD", "OPTIONS"}:
            handler = Mock(return_value="handler called")
            monkeypatch.setitem(balance_app.view_functions, rule.endpoint, handler)
            response = client.open(_url(rule), method=method, json={})
            assert response.status_code == 403, (method, rule.rule)
            assert response.get_json() == {"ok": False, "error": "Недостаточно прав"}
            handler.assert_not_called()
            checked.add((rule.endpoint, method))
    assert len(checked) >= 20


@pytest.mark.parametrize("role", ["admin", "generation-admin", "generation-editor"])
def test_editors_pass_blueprint_guard_for_every_write_route(balance_app, monkeypatch, role):
    monkeypatch.setattr(bp_routes, "current_user", _user(role))
    for rule in balance_app.url_map.iter_rules():
        for method in rule.methods - {"GET", "HEAD", "OPTIONS"}:
            handler = Mock(return_value="allowed")
            monkeypatch.setitem(balance_app.view_functions, rule.endpoint, handler)
            response = balance_app.test_client().open(_url(rule), method=method, json={})
            assert response.status_code == 200, (method, rule.rule)
            handler.assert_called_once()


def test_readers_can_open_every_page_export_and_apply_filters(balance_app, monkeypatch):
    monkeypatch.setattr(bp_routes, "current_user", _user("generation-reader"))
    for rule in balance_app.url_map.iter_rules():
        if not rule.endpoint.startswith("energy_balance_bp."):
            continue
        methods = rule.methods & {"GET", "HEAD", "OPTIONS"}
        if rule.endpoint in {"energy_balance_bp.ee_generation", "energy_balance_bp.ee_transfers"}:
            methods.add("POST")
        for method in methods:
            monkeypatch.setitem(balance_app.view_functions, rule.endpoint, lambda **kwargs: "allowed")
            assert balance_app.test_client().open(_url(rule), method=method).status_code == 200


@pytest.fixture
def templates():
    from jinja2 import Environment

    env = Environment(
        loader=ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader("app/templates"),
        ]),
        autoescape=True,
    )
    env.globals.update(
        csrf_token="test-token",
        url_for=lambda endpoint, **kwargs: "/" + endpoint,
        current_user=_user("generation-reader"),
        request=SimpleNamespace(args=MultiDict()),
    )
    return env


@pytest.mark.parametrize("editable", [False, True])
def test_control_values_and_notes_render_as_text_for_readers(templates, editable):
    control = templates.get_template("energy_balance/ee_generation/ee_generation_control_row.html").render(
        can_edit_energy_balance=editable, res_id=1, period_columns=[(2026, "2026")],
        period_totals={2026: "123,4"}, rounding_digits=1,
        format_generation_input_value=lambda value, digits: value,
    )
    note = templates.get_template("energy_balance/_row_note_cell.html").render(
        can_edit_energy_balance=editable, row={"note": "Примечание <строки>"},
    )
    assert "123,4" in control
    assert ("<input" in control) == editable
    assert ("<textarea" in note) == editable
    assert "Примечание &lt;строки&gt;" in note


@pytest.mark.parametrize("editable", [False, True])
@pytest.mark.parametrize("kind", ["power_balance", "ee_balance"])
def test_balance_tables_hide_all_write_controls_but_keep_data_and_export(templates, editable, kind):
    row = {
        "key": "custom_1", "label": "Строка перетока", "is_custom": True,
        "custom_id": 1, "custom_direction": "flow_in", "can_add_custom_flow": True,
        "editable_values": True, "value_save_kind": "custom", "kind": "value", "unit": "МВт",
        "year_values": {2026: "123,4"}, "year_values_raw": {2026: "123.4"},
        "note": "Примечание строки", "formula_client": None,
    }
    html = templates.get_template(f"energy_balance/{kind}/{kind}_table.html").render(
        can_edit_energy_balance=editable, can_edit=editable,
        sheet={"slug": "ees-rossii"}, rows=[row], years=[2026],
        filter_year_list=[2026], start_year=2026, end_year=2026, rounding_digits=1,
    )
    # Проверяем разметку, а не строки JavaScript с динамическими элементами.
    markup = html.split("<script>", 1)[0]
    for control in ("pb-custom-label", "pb-custom-value", "pb-custom-add", "pb-custom-delete", "pb-row-note"):
        assert (f'class="form-control form-control-sm {control}"' in markup
                or f'class="btn btn-outline-success btn-sm {control}"' in markup
                or f'class="btn btn-outline-danger btn-sm {control}"' in markup) == editable
    assert "Строка перетока" in markup
    assert "123,4" in markup
    assert "Примечание строки" in markup
    assert "Выгрузить в Excel" in markup


@pytest.mark.parametrize("editable", [False, True])
@pytest.mark.parametrize("kind", ["generation", "transfers"])
def test_import_hidden_for_readers_while_export_remains(templates, editable, kind):
    html = templates.get_template("fuel/_shared/station_filters_second_row.html").render(
        can_edit_energy_balance=editable,
        form=SimpleNamespace(csrf_token=""),
        **{f"show_ee_{kind}_import": True},
    )
    suffix = "Generation" if kind == "generation" else "Transfers"
    assert (f'id="importEe{suffix}Form"' in html) == editable
    assert f'id="exportEe{suffix}Form"' in html


def test_changed_templates_compile(templates):
    for path in Path("app/templates/energy_balance").rglob("*.html"):
        templates.get_template(path.relative_to("app/templates").as_posix())
    templates.get_template("fuel/_shared/station_filters_second_row.html")
