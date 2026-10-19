# -*- coding: utf-8 -*-
"""Ответ API помесячного баланса ТЭС содержит режим расчёта ячеек."""

from unittest.mock import patch

from flask import Flask

from app.energy_balance.routes import ee_balance_routes as routes


def test_generation_value_denies_users_without_edit_permission():
    app = Flask(__name__)
    with (
        app.test_request_context(
            "/ee_balance/sibir/generation_value/",
            method="PATCH",
            json={"year": 2026, "row_key": "generation_tes", "value": "12"},
        ),
        patch.object(routes, "_can_edit_ves_ses_energy", return_value=False),
        patch.object(routes, "update_ee_balance_manual_generation_value") as update,
    ):
        response, status = routes.ee_balance_generation_value.__wrapped__("sibir")

    assert status == 403
    assert response.get_json() == {"ok": False, "error": "Недостаточно прав"}
    update.assert_not_called()


def test_ural_without_tyumen_generation_value_is_saved_under_custom_slug():
    app = Flask(__name__)
    with (
        app.test_request_context(
            "/ee_balance/ural-without-tyumen/generation_value/",
            method="PATCH",
            json={"year": 2026, "row_key": "generation_tes", "value": "12"},
        ),
        patch.object(routes, "_can_edit_ves_ses_energy", return_value=True),
        patch.object(
            routes,
            "get_ee_balance_sheet",
            return_value={"slug": "ural", "sheet_name": "Урал"},
        ),
        patch.object(
            routes,
            "update_ee_balance_manual_generation_value",
            return_value={"year": 2026, "row_key": "generation_tes", "value": 12},
        ) as update,
    ):
        response = routes.ee_balance_generation_value.__wrapped__(
            "ural-without-tyumen"
        )

    assert response.get_json()["ok"] is True
    assert update.call_args.args == (
        "ural-without-tyumen",
        "generation_tes",
        2026,
        "12",
    )
    assert update.call_args.kwargs["sheet_name"] == "Урал"


def test_tes_forecast_update_returns_formula_cells():
    app = Flask(__name__)
    sheet = {"slug": "oes-318", "sheet_name": "ТИТЭС Сибири"}
    with (
        app.test_request_context(
            "/ee_balance/oes-318/tes_forecast/value/",
            method="PATCH",
            json={"year": 2026, "month": 1, "row_key": "consumption_share", "value": "0,2"},
        ),
        patch.object(routes, "_can_edit_ves_ses_energy", return_value=True),
        patch.object(routes, "get_ee_balance_sheet", return_value=sheet),
        patch.object(
            routes,
            "update_tes_forecast_value",
            return_value={
                "year": 2026,
                "row_key": "consumption_share",
                "month": 1,
                "cells": {"consumption": {"1": "600"}},
                "formula_cells": {"consumption": [1]},
                "tes_total": None,
            },
        ),
    ):
        response = routes.ee_balance_tes_forecast_value.__wrapped__("oes-318")

    assert response.get_json()["formula_cells"] == {"consumption": [1]}
    assert response.get_json()["cells"]["consumption"]["1"] == "600"
