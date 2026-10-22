"""Страницы сводных расчетов модуля «Экология»."""
from flask import abort, redirect, render_template, request, url_for
from flask_login import login_required

from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.calculation_summary_services import build_calculation_summary_context
from app.ecology.services.ecology_logging_services import context_lines, log_page_visit
from app.ecology.services.operating_tes_constants import get_territory


@ecology_bp.route("/calculation_summary/")
@login_required
def calculation_summary_index():
    return redirect(url_for(
        "ecology_bp.calculation_summary",
        **{**request.args.to_dict(), "territory_slug": "vsego", "sheet_slug": "toplivo"},
    ))


@ecology_bp.route("/calculation_summary/<territory_slug>/<sheet_slug>/")
@login_required
def calculation_summary(territory_slug, sheet_slug):
    if get_territory(territory_slug) is None:
        abort(404)
    context = build_calculation_summary_context(
        territory_slug, sheet_slug,
        **{key: request.args.get(key) for key in (
            "start_year", "end_year", "view_year", "rounding_digits", "coefficient_rounding_digits",
        )},
    )
    if context is None:
        abort(404)
    log_page_visit(
        "Сводные данные расчетов", tab=context["sheet"]["sheet_name"],
        details=context_lines(
            ("период", f"{context['start_year']}–{context['end_year']}"),
            ("год", context["view_year"]),
        ),
    )
    return render_template("ecology/operating_tes/operating_tes_table.html", **context)
