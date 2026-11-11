"""Все вкладки раздела пишут посещение в общий журнал «Экология»."""
import pytest
from flask import Flask, session

from app.ecology.routes import calculation_summary_routes as summary
from app.ecology.routes import ecology_routes as ecology
from app.ecology.routes import ecology_totals_summary_routes as totals
from app.ecology.routes import gis_tes_fuel_comparison_routes as analysis
from app.ecology.routes import new_tes_routes as new
from app.ecology.routes import operating_tes_routes as operating
from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services import ecology_logging_services as audit
from app.ecology.services.calculation_summary_services import CALCULATION_SUMMARY_TABS
from app.ecology.services.gis_tek_constants import PAGE_TITLES
from app.ecology.services.gis_tes_fuel_comparison_constants import COMPARISON_SHEETS
from app.ecology.services.new_tes_constants import NEW_TES_CALC_SHEETS, NEW_TES_CAPACITY_TABS
from app.ecology.services.operating_tes_constants import CALC_SHEETS, TERRITORIES


@pytest.fixture
def visit_env(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(ecology_bp, url_prefix="/ecology")
    records = []
    monkeypatch.setattr(audit, "log_to_db", lambda user, action, details, **kw: records.append(
        {"user": user, "action": action, "details": details, **kw}
    ))
    for module in (summary, ecology, totals, analysis, new, operating):
        monkeypatch.setattr(module, "render_template", lambda *a, **kw: "page")
        if hasattr(module, "can_edit_ecology"):
            monkeypatch.setattr(module, "can_edit_ecology", lambda user: False)
    return app, records


def assert_visit(records, title, tab=None):
    assert len(records) == 1
    record = records[0]
    assert record["user"] == "viewer"
    assert record["entity_type"] == "ecology"
    assert record["action"].startswith("Открыта страница: Экология – ")
    assert title in record["action"]
    assert "url=/ecology/" in record["details"]
    if tab:
        assert f"вкладка={tab}" in record["details"]


@pytest.mark.parametrize("sheet", CALC_SHEETS, ids=lambda s: s["slug"])
@pytest.mark.parametrize("territory", TERRITORIES, ids=lambda t: t["slug"])
def test_operating_tabs(visit_env, monkeypatch, sheet, territory):
    app, records = visit_env
    context = dict(sheet=sheet, territory=territory, start_year=2024, end_year=2026,
                   view_year=2026, range_years=[2026], affiliation="all")
    monkeypatch.setattr(operating, "build_operating_tes_table_context", lambda *a, **kw: context)
    monkeypatch.setattr("app.ecology.services.fuel_exchange_services.pending_submissions", lambda *a, **kw: [])
    path = f"/ecology/operating_tes/{territory['slug']}/{sheet['slug']}/"
    with app.test_request_context(path):
        session["username"] = "viewer"
        operating.operating_tes_table.__wrapped__(territory["slug"], sheet["slug"])
    assert_visit(records, "Действующие ТЭС", sheet["sheet_name"])
    assert f"территория={territory['sheet_name']}" in records[0]["details"]


@pytest.mark.parametrize("sheet", NEW_TES_CALC_SHEETS, ids=lambda s: s["slug"])
@pytest.mark.parametrize("capacity,label", NEW_TES_CAPACITY_TABS)
def test_new_tabs_and_capacity(visit_env, monkeypatch, sheet, capacity, label):
    app, records = visit_env
    context = dict(sheet=sheet, territory={"sheet_name": "Всего"}, start_year=2024,
                   end_year=2026, view_year=2026, range_years=[2026], capacity_class=capacity)
    monkeypatch.setattr(new, "build_new_tes_table_context", lambda *a, **kw: context)
    monkeypatch.setattr("app.ecology.services.fuel_exchange_services.pending_submissions", lambda *a, **kw: [])
    with app.test_request_context(f"/ecology/new_tes/vsego/{sheet['slug']}/?capacity_class={capacity}"):
        session["username"] = "viewer"
        new.new_tes_table.__wrapped__("vsego", sheet["slug"])
    assert_visit(records, "Новые ТЭС", sheet["sheet_name"])
    assert f"мощность={label}" in records[0]["details"]


@pytest.mark.parametrize("sheet", CALCULATION_SUMMARY_TABS, ids=lambda s: s["slug"])
def test_calculation_summary_tabs(visit_env, monkeypatch, sheet):
    app, records = visit_env
    context = dict(sheet=sheet, start_year=2024, end_year=2026, view_year=2026)
    monkeypatch.setattr(summary, "build_calculation_summary_context", lambda *a, **kw: context)
    with app.test_request_context(f"/ecology/calculation_summary/vsego/{sheet['slug']}/"):
        session["username"] = "viewer"
        summary.calculation_summary.__wrapped__("vsego", sheet["slug"])
    assert_visit(records, "Сводные данные расчетов", sheet["sheet_name"])


@pytest.mark.parametrize("sheet", COMPARISON_SHEETS, ids=lambda s: s["slug"])
@pytest.mark.parametrize("is_totals", [False, True], ids=["analysis", "totals"])
def test_analysis_and_total_tabs(visit_env, monkeypatch, sheet, is_totals):
    app, records = visit_env
    context = dict(sheet=sheet, page_title=sheet["page_title"], start_year=2024, end_year=2026)
    module = totals if is_totals else analysis
    builder = "_ecology_totals_page_context" if is_totals else "build_comparison_table_context"
    monkeypatch.setattr(module, builder, lambda *a, **kw: context)
    if not is_totals:
        monkeypatch.setattr(analysis, "StationFilterForm", lambda: None)
    path = "totals_summary" if is_totals else "analysis"
    with app.test_request_context(f"/ecology/{path}/{sheet['slug']}/"):
        session["username"] = "viewer"
        view = totals.totals_summary if is_totals else analysis.gis_tes_fuel_comparison
        view.__wrapped__(sheet["slug"])
    assert_visit(records, "Итоговые суммы" if is_totals else "Сопоставление данных", sheet["page_title"])


@pytest.mark.parametrize("kind", list(PAGE_TITLES))
def test_report_pages(visit_env, monkeypatch, kind):
    app, records = visit_env
    monkeypatch.setattr(ecology, "build_gis_tek_page_context", lambda *a, **kw: dict(
        page_title=PAGE_TITLES[kind], rounding_digits=1
    ))
    monkeypatch.setattr(ecology, "StationFilterForm", lambda: None)
    with app.test_request_context(f"/ecology/gis_tek/{kind}/"):
        session["username"] = "viewer"
        ecology._render_report(kind)
    assert_visit(records, PAGE_TITLES[kind])


@pytest.mark.parametrize("is_formulas", [False, True], ids=["hub", "formulas"])
def test_hub_and_formula_pages(visit_env, monkeypatch, is_formulas):
    app, records = visit_env
    monkeypatch.setattr(ecology, "can_edit_ecology", lambda user: True)
    monkeypatch.setattr(ecology, "list_formulas_for_admin", lambda: [])
    with app.test_request_context("/ecology/formulas/" if is_formulas else "/ecology/"):
        session["username"] = "viewer"
        view = ecology.operating_tes_formulas if is_formulas else ecology.hub
        view.__wrapped__()
    assert_visit(records, "Тексты формул" if is_formulas else "Главная страница модуля")
