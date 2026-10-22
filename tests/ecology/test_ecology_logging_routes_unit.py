# -*- coding: utf-8 -*-
"""Маршруты «Экологии»: посещение страниц и вкладок, загрузка и выгрузка файлов."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from app.ecology.routes import ecology_routes as eco_routes
from app.ecology.routes import new_tes_routes
from app.ecology.routes import operating_tes_routes
from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.gis_tek_constants import PAGE_TITLES, REPORT_PG


def test_operating_tes_table_logs_page_and_tab():
    app = Flask(__name__)
    context = {
        "page_title": "Характеристика топлив",
        "sheet": {"sheet_name": "Характеристики", "layout": "chars"},
        "territory": {"sheet_name": "Всего"},
        "start_year": 2024,
        "end_year": 2030,
        "view_year": 2026,
        "range_years": [2024, 2025],
    }
    with (
        app.test_request_context("/ecology/operating_tes/vsego/khar-topl/"),
        patch.object(
            operating_tes_routes,
            "build_operating_tes_table_context",
            return_value=context,
        ),
        patch.object(operating_tes_routes, "can_edit_ecology", return_value=False),
        patch.object(operating_tes_routes, "current_user", SimpleNamespace()),
        patch.object(operating_tes_routes, "render_template", return_value=""),
        patch.object(operating_tes_routes, "log_page_visit") as visit,
    ):
        operating_tes_routes.operating_tes_table.__wrapped__("vsego", "khar-topl")

    assert visit.call_args.args == ("Действующие ТЭС",)
    assert visit.call_args.kwargs["tab"] == "Характеристики"
    details = visit.call_args.kwargs["details"]
    assert "территория=Всего" in details
    assert "период=2024–2030" in details
    assert "год=2026" in details


def test_new_tes_table_logs_page_and_tab():
    app = Flask(__name__)
    context = {
        "page_title": "Нормативы удельных выбросов",
        "sheet": {"sheet_name": "Нормативы", "layout": "chars"},
        "territory": {"sheet_name": "Всего"},
        "start_year": 2025,
        "end_year": 2031,
        "view_year": 2028,
    }
    with (
        app.test_request_context("/ecology/new_tes/vsego/spravochnik/"),
        patch.object(new_tes_routes, "build_new_tes_table_context", return_value=context),
        patch.object(new_tes_routes, "can_edit_ecology", return_value=False),
        patch.object(new_tes_routes, "current_user", SimpleNamespace()),
        patch.object(new_tes_routes, "render_template", return_value=""),
        patch.object(new_tes_routes, "log_page_visit") as visit,
    ):
        new_tes_routes.new_tes_table.__wrapped__("vsego", "spravochnik")

    assert visit.call_args.args == ("Новые ТЭС",)
    assert visit.call_args.kwargs["tab"] == "Нормативы"


def test_gis_tek_report_logs_page_visit():
    app = Flask(__name__)
    app.register_blueprint(ecology_bp, url_prefix="/ecology")
    context = {
        "page_title": PAGE_TITLES[REPORT_PG],
        "rounding_digits": 1,
        "show_totals": False,
        "show_empty_rows": False,
        "selected_year": None,
        "per_page_param": None,
    }
    with (
        app.test_request_context("/ecology/gis_tek/pg/"),
        patch.object(eco_routes, "build_gis_tek_page_context", return_value=context),
        patch.object(eco_routes, "can_edit_ecology", return_value=False),
        patch.object(eco_routes, "current_user", SimpleNamespace()),
        patch.object(eco_routes, "StationFilterForm", lambda *args, **kwargs: None),
        patch.object(eco_routes, "render_template", return_value=""),
        patch.object(eco_routes, "log_page_visit") as visit,
    ):
        eco_routes._render_report(REPORT_PG)

    assert visit.call_args.args == (PAGE_TITLES[REPORT_PG],)


def test_gis_tek_import_logs_uploaded_file():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    data = {"file": (BytesIO(b"excel-bytes"), "gis_tek_pg.xlsx")}
    with (
        app.test_request_context(
            "/ecology/gis_tek/pg/import", method="POST", data=data
        ),
        patch.object(eco_routes, "can_edit_ecology", return_value=True),
        patch.object(
            eco_routes, "import_gis_tek_from_xlsx_bytes", return_value={"message": "ok"}
        ),
        patch.object(eco_routes, "_redirect_kind", return_value="redirected"),
        patch.object(eco_routes, "log_file_upload") as upload,
    ):
        eco_routes._import_report(REPORT_PG)

    assert upload.call_args.args == (PAGE_TITLES[REPORT_PG], "gis_tek_pg.xlsx")
    assert upload.call_args.kwargs["size_bytes"] == len(b"excel-bytes")


def test_gis_tek_export_logs_downloaded_file():
    app = Flask(__name__)
    with (
        app.test_request_context("/ecology/gis_tek/pg/export.xlsx"),
        patch.object(
            eco_routes, "build_gis_tek_excel_stream", return_value=BytesIO(b"excel")
        ),
        patch.object(eco_routes, "log_file_download") as download,
    ):
        eco_routes._export_report(REPORT_PG)

    assert download.call_args.args == (
        PAGE_TITLES[REPORT_PG],
        "gis_tek_parnikovye_gazy.xlsx",
    )


def test_formula_save_logs_before_and_after():
    app = Flask(__name__)
    session = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    with (
        app.test_request_context(
            "/ecology/formulas/save",
            method="POST",
            json={"formula_key": "ash_to_natural", "formula_text": "новый текст"},
        ),
        patch.object(eco_routes, "can_edit_ecology", return_value=True),
        patch.object(eco_routes, "db", SimpleNamespace(session=session)),
        patch.object(eco_routes, "save_formula_text_override") as save,
        patch.object(
            eco_routes,
            "ot_formula_text",
            side_effect=["старый текст", "новый текст"],
        ),
        patch.object(eco_routes, "log_cell_change") as change,
    ):
        response = eco_routes.operating_tes_formulas_save.__wrapped__()

    assert response.get_json() == {"ok": True}
    assert save.call_args.kwargs == {
        "formula_key": "ash_to_natural",
        "formula_text": "новый текст",
    }
    assert change.call_args.args == (
        "Тексты формул",
        "Текст формулы ash_to_natural",
        "старый текст",
        "новый текст",
    )
    assert change.call_args.kwargs["number"] is False


def _fuel_review_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(ecology_bp, url_prefix="/ecology")
    return app


def _fuel_submission():
    return SimpleNamespace(id=7, year_number=2026, scope="operating")


def _review_request_context(app, method="POST", decision="accept"):
    kwargs = {"data": {"decision": decision}} if method == "POST" else {}
    return app.test_request_context(
        "/ecology/operating_tes/fuel_submissions/7/", method=method, **kwargs
    )


def test_fuel_submission_accept_logs_before_and_after():
    app = _fuel_review_app()
    submission = _fuel_submission()
    differences = [
        {
            "label": "Газ",
            "territory": "ОЭС Центра",
            "unit": "тыс. т у.т.",
            "before": Decimal("10"),
            "after": Decimal("12"),
            "delta": Decimal("2"),
        }
    ]
    with (
        _review_request_context(app),
        patch.object(operating_tes_routes, "can_edit_ecology", return_value=True),
        patch.object(operating_tes_routes, "current_user", SimpleNamespace()),
        patch(
            "app.ecology.services.fuel_exchange_services.get_submission",
            return_value=submission,
        ),
        patch(
            "app.ecology.services.fuel_exchange_services.submission_differences",
            return_value=differences,
        ) as diff,
        patch(
            "app.ecology.services.fuel_exchange_services.review_fuel_submission"
        ) as review,
        patch.object(operating_tes_routes, "log_changes") as changes,
        patch.object(operating_tes_routes, "log_event") as event,
    ):
        operating_tes_routes.operating_tes_fuel_review.__wrapped__(7)

    # Разница считается до акцепта: после него эталон уже совпадает с пакетом.
    diff.assert_called_once_with(submission)
    review.assert_called_once_with(7, accept=True)
    event.assert_not_called()
    assert changes.call_args.args == (
        "Акцепт: Данные из модуля «Топливо» за 2026 год – Действующие ТЭС",
        ["Газ (ОЭС Центра): было 10 → стало 12"],
    )


def test_fuel_submission_review_page_logs_page_and_year():
    app = _fuel_review_app()
    submission = _fuel_submission()
    with (
        _review_request_context(app, method="GET"),
        patch.object(operating_tes_routes, "can_edit_ecology", return_value=True),
        patch.object(operating_tes_routes, "current_user", SimpleNamespace()),
        patch(
            "app.ecology.services.fuel_exchange_services.get_submission",
            return_value=submission,
        ),
        patch(
            "app.ecology.services.fuel_exchange_services.submission_differences",
            return_value=[],
        ),
        patch.object(operating_tes_routes, "render_template", return_value=""),
        patch.object(operating_tes_routes, "log_page_visit") as visit,
    ):
        operating_tes_routes.operating_tes_fuel_review.__wrapped__(7)

    assert visit.call_args.args == ("Акцепт данных из модуля «Топливо»",)
    assert visit.call_args.kwargs["tab"] == "2026 год"
    assert visit.call_args.kwargs["details"] == ["пакет=7"]


def test_fuel_submission_reject_logs_decision_without_changes():
    app = _fuel_review_app()
    submission = _fuel_submission()
    with (
        _review_request_context(app, decision="reject"),
        patch.object(operating_tes_routes, "can_edit_ecology", return_value=True),
        patch.object(operating_tes_routes, "current_user", SimpleNamespace()),
        patch(
            "app.ecology.services.fuel_exchange_services.get_submission",
            return_value=submission,
        ),
        patch(
            "app.ecology.services.fuel_exchange_services.submission_differences"
        ) as diff,
        patch(
            "app.ecology.services.fuel_exchange_services.review_fuel_submission"
        ) as review,
        patch.object(operating_tes_routes, "log_changes") as changes,
        patch.object(operating_tes_routes, "log_event") as event,
    ):
        operating_tes_routes.operating_tes_fuel_review.__wrapped__(7)

    diff.assert_not_called()
    review.assert_called_once_with(7, accept=False)
    changes.assert_not_called()
    assert event.call_args.args[0] == (
        "Отклонены Данные из модуля «Топливо» за 2026 год – Действующие ТЭС"
    )
