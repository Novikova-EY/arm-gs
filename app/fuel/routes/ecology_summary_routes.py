"""Сводные данные для передачи в экологию."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import fuel_bp
from app.ecology.services.fuel_exchange_services import submit_fuel_year
from app.ecology.services.fuel_summary_constants import FUEL_SUMMARY_SCOPES, FUEL_SUMMARY_LABELS, FUEL_SUMMARY_CRITERIA
from app.ecology.services.fuel_summary_services import FuelSummaryError
from app.ecology.services.operating_tes_page_services import build_operating_tes_table_context


@fuel_bp.route("/ecology_summary/", methods=["GET", "POST"])
@login_required
def ecology_summary():
    scope = request.args.get("scope", "operating")
    if scope not in FUEL_SUMMARY_LABELS:
        abort(404)
    context = build_operating_tes_table_context(
        "vsego", "toplivo", start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"), rounding_digits=request.args.get("rounding_digits"),
        view_year=request.args.get("view_year"), fuel_source=True, fuel_scope=scope,
    )
    can_send = bool(current_user.has_admin)
    if request.method == "POST":
        if not can_send:
            return "Недостаточно прав", 403
        year = context["view_year"]
        if year not in context["range_years"]:
            return "Год не входит в выбранный диапазон", 400
        try:
            submit_fuel_year(year, scope=scope)
        except FuelSummaryError as exc:
            return str(exc), 409
        flash(f'{FUEL_SUMMARY_LABELS[scope]}: данные за {year} год переданы в модуль «Экология» и ожидают акцепта.', "success")
        return redirect(url_for("fuel_bp.ecology_summary", start_year=context["start_year"], end_year=context["end_year"], rounding_digits=context["rounding_digits"], view_year=year, scope=scope if scope != "operating" else None))
    context.update(
        table_endpoint="fuel_bp.ecology_summary", fuel_exchange_source=True,
        document_title='Сводные данные для модуля "Экология"',
        page_title='Количество сжигаемого топлива по тепловым электростанциям, тыс. т у.т./год', can_edit=False, can_send=can_send,
        page_title_html='Количество сжигаемого топлива по тепловым электростанциям, тыс. т у.т./год',
        fuel_scope=scope, fuel_summary_scopes=FUEL_SUMMARY_SCOPES,
        fuel_summary_criteria=FUEL_SUMMARY_CRITERIA,
    )
    return render_template("ecology/operating_tes/operating_tes_table.html", **context)
