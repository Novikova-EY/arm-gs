# -*- coding: utf-8 -*-
"""Правка ячеек страниц анализа ЗВ/ПГ: маршрут PATCH."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from flask import Flask

from app.ecology.routes import gis_tes_fuel_comparison_routes as routes


def test_zv_sheet_value_patch_saves_pollutant():
    app = Flask(__name__)
    with (
        app.test_request_context(
            "/ecology/analysis/zv-vse/value/",
            method="PATCH",
            json={
                "year": 2017,
                "numb": 708,
                "field": "SO2_gaz",
                "value": "12,5",
                "rounding_digits": 1,
            },
        ),
        patch.object(routes, "can_edit_ecology", return_value=True),
        patch.object(
            routes,
            "save_analysis_ecology_cell",
            return_value={"SO2_gaz": {"text": "12,5", "nonzero": False}},
        ) as save,
    ):
        response = routes.gis_tes_fuel_comparison_update_value.__wrapped__("zv-vse")

    body = response.get_json()
    assert body == {
        "ok": True,
        "values": {"SO2_gaz": {"text": "12,5", "nonzero": False}},
    }
    assert save.call_args.args == ("zv-vse", 708, 2017, "SO2_gaz", Decimal("12.5"))
    assert save.call_args.kwargs["rounding_digits"] == 1


def test_unknown_analysis_sheet_value_patch_is_rejected():
    app = Flask(__name__)
    with (
        app.test_request_context(
            "/ecology/analysis/zv-other/value/",
            method="PATCH",
            json={"year": 2017, "numb": 1, "field": "SO2_gaz", "value": 1},
        ),
        patch.object(routes, "can_edit_ecology", return_value=True),
        patch.object(routes, "save_analysis_ecology_cell") as save,
    ):
        response, status = routes.gis_tes_fuel_comparison_update_value.__wrapped__(
            "zv-other"
        )

    assert status == 400
    assert response.get_json() == {"ok": False, "error": "Лист только для просмотра"}
    save.assert_not_called()
