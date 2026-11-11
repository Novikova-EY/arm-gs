from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask
from werkzeug.exceptions import Forbidden

from app.ecology.routes import ecology_routes, gis_tes_fuel_comparison_routes
from app.ecology.routes import new_tes_routes, operating_tes_routes
from app.ecology.services.gis_tek_page_services import can_edit_ecology


@pytest.mark.parametrize(
    "user, expected",
    [
        (SimpleNamespace(is_authenticated=False, role_names=["ecology-admin"]), False),
        (SimpleNamespace(is_authenticated=True, role_names=["admin"], has_admin=True), True),
        (SimpleNamespace(is_authenticated=True, role_names=["ecology-auditor"]), False),
        (SimpleNamespace(is_authenticated=True, role_names=["ecology-admin"]), True),
        (SimpleNamespace(is_authenticated=True, role_names=["ecology-editor"]), True),
        (SimpleNamespace(is_authenticated=True, role_names=["Экология-админ"]), True),
        (SimpleNamespace(is_authenticated=True, role_names=["Экология-редактор"]), True),
        (
            SimpleNamespace(
                is_authenticated=True,
                role_names=[],
                roles=[
                    SimpleNamespace(name="ecology_viewer", name_full="Экология-редактор")
                ],
            ),
            True,
        ),
    ],
)
def test_ecology_edit_permission_only_matches_configured_roles(user, expected):
    assert can_edit_ecology(user) is expected


def test_formula_page_is_readable_without_edit_role(monkeypatch):
    app = Flask(__name__)
    captured = {}
    monkeypatch.setattr(ecology_routes, "current_user", SimpleNamespace(is_authenticated=True))
    monkeypatch.setattr(ecology_routes, "can_edit_ecology", lambda user: False)
    monkeypatch.setattr(ecology_routes, "list_formulas_for_admin", lambda: ["formula"])
    monkeypatch.setattr(ecology_routes, "log_page_visit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ecology_routes,
        "render_template",
        lambda template, **context: captured.update(template=template, **context) or "page",
    )

    with app.test_request_context("/ecology/formulas/"):
        assert ecology_routes.operating_tes_formulas.__wrapped__() == "page"

    assert captured["formula_rows"] == ["formula"]
    assert captured["can_edit"] is False


@pytest.mark.parametrize(
    "route_module, route_name, args",
    [
        (ecology_routes, "operating_tes_formulas_save", ()),
        (ecology_routes, "operating_tes_formulas_reset", ()),
        (gis_tes_fuel_comparison_routes, "gis_tes_fuel_comparison_update_value", ("pg-vse",)),
        (new_tes_routes, "new_tes_update_value", ("vsego", "spravochnik")),
        (operating_tes_routes, "operating_tes_update_value", ("vsego", "khar-topl")),
    ],
)
def test_ecology_write_endpoints_reject_users_without_edit_role(
    monkeypatch, route_module, route_name, args
):
    app = Flask(__name__)
    monkeypatch.setattr(route_module, "current_user", SimpleNamespace(is_authenticated=True))
    monkeypatch.setattr(route_module, "can_edit_ecology", lambda user: False)

    with app.test_request_context("/ecology/write", method="PATCH" if "update_value" in route_name else "POST", json={}):
        response = getattr(route_module, route_name).__wrapped__(*args)

    assert response[1] == 403


def test_gis_tek_import_rejects_users_without_edit_role(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(ecology_routes, "current_user", SimpleNamespace(is_authenticated=True))
    monkeypatch.setattr(ecology_routes, "can_edit_ecology", lambda user: False)

    with app.test_request_context("/ecology/gis_tek/pg/import", method="POST"):
        with pytest.raises(Forbidden):
            ecology_routes._import_report("pg")


def test_fuel_submission_review_rejects_users_without_edit_role(monkeypatch):
    app = Flask(__name__)
    submission = SimpleNamespace(id=4, year_number=2026, scope="operating")
    monkeypatch.setattr(operating_tes_routes, "current_user", SimpleNamespace(is_authenticated=True))
    monkeypatch.setattr(operating_tes_routes, "can_edit_ecology", lambda user: False)
    monkeypatch.setattr(
        "app.ecology.services.fuel_exchange_services.get_submission",
        lambda submission_id: submission,
    )

    with app.test_request_context(
        "/ecology/operating_tes/fuel_submissions/4/", method="POST", data={"decision": "accept"}
    ):
        with pytest.raises(Forbidden):
            operating_tes_routes.operating_tes_fuel_review.__wrapped__(4)
