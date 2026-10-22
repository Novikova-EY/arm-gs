# -*- coding: utf-8 -*-
"""Маршруты расчёта по новым ТЭС."""

from __future__ import annotations

from flask import abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.common.services.help_services import parse_decimal_from_display
from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.ecology_logging_services import (
    context_lines,
    log_page_visit,
)
from app.ecology.services.gis_tek_page_services import can_edit_ecology
from app.ecology.services.new_tes_constants import (
    CAPACITY_CLASSES,
    CAPACITY_LE100_KEY,
    DEFAULT_SHEET_SLUG,
    DEFAULT_TERRITORY_SLUG,
    get_calc_sheet,
)
from app.ecology.services.new_tes_page_services import (
    build_new_tes_table_context,
    upsert_norm,
)
from app.ecology.services.operating_tes_constants import get_territory


@ecology_bp.route("/new_tes/")
@login_required
def new_tes_hub():
    return redirect(
        url_for(
            "ecology_bp.new_tes_table",
            territory_slug=DEFAULT_TERRITORY_SLUG,
            sheet_slug=DEFAULT_SHEET_SLUG,
        )
    )


@ecology_bp.route("/new_tes/<territory_slug>/")
@login_required
def new_tes_territory(territory_slug: str):
    if get_territory(territory_slug) is None:
        abort(404)
    return redirect(
        url_for(
            "ecology_bp.new_tes_table",
            territory_slug=territory_slug,
            sheet_slug=DEFAULT_SHEET_SLUG,
            **request.args,
        )
    )


@ecology_bp.route("/new_tes/<territory_slug>/<sheet_slug>/")
@login_required
def new_tes_table(territory_slug: str, sheet_slug: str):
    context = build_new_tes_table_context(
        territory_slug,
        sheet_slug,
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
        view_year=request.args.get("view_year"),
        capacity_class=request.args.get("capacity_class", CAPACITY_LE100_KEY),
    )
    if context is None:
        abort(404)
    sheet = context.get("sheet") or {}
    log_page_visit(
        "Новые ТЭС",
        tab=str(sheet.get("sheet_name") or sheet_slug),
        details=context_lines(
            ("территория", (context.get("territory") or {}).get("sheet_name")),
            ("период", f"{context.get('start_year')}–{context.get('end_year')}"),
            ("год", context.get("view_year")),
        ),
    )
    context["can_edit"] = bool(
        can_edit_ecology(current_user) and sheet.get("layout") == "chars"
    )
    if sheet.get("layout") == "fuel":
        from app.ecology.services.fuel_exchange_services import pending_submissions
        from app.ecology.services.fuel_summary_constants import FUEL_SUMMARY_LABELS, NEW_TES_SCOPE_CAPACITY

        scope = next(key for key, capacity in NEW_TES_SCOPE_CAPACITY.items() if capacity == context["capacity_class"])
        pending = pending_submissions(context["range_years"], scope=scope)
        context["new_fuel_pending"] = [item for item in pending if item.year_number == context["view_year"]]
        context["fuel_summary_labels"] = FUEL_SUMMARY_LABELS
    return render_template(
        "ecology/operating_tes/operating_tes_table.html",
        document_title="Расчет по новым ТЭС",
        **context,
    )


@ecology_bp.route(
    "/new_tes/<territory_slug>/<sheet_slug>/value/",
    methods=["PATCH"],
)
@login_required
def new_tes_update_value(territory_slug: str, sheet_slug: str):
    if not can_edit_ecology(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    if get_territory(territory_slug) is None or get_calc_sheet(sheet_slug) is None:
        abort(404)
    capacity = request.args.get("capacity_class", CAPACITY_LE100_KEY)
    if capacity not in CAPACITY_CLASSES:
        abort(404)
    data = request.get_json(silent=True) or {}
    year = data.get("year")
    field = str(data.get("field") or "").strip()
    row_key = str(data.get("row_key") or "").strip()
    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Некорректный год"), 400
    raw = data.get("value")
    try:
        amount = parse_decimal_from_display(raw) if raw not in (None, "") else None
    except Exception:
        return jsonify(ok=False, error="Некорректное число"), 400
    try:
        if sheet_slug == "spravochnik":
            if field in {"ash", "so2", "nox", "k_co2"}:
                field = f"{'pg' if field == 'k_co2' else field}_{capacity}"
            upsert_norm(row_key, year_int, field, amount)
        else:
            return jsonify(ok=False, error="Лист только для просмотра"), 400
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить норматив новых ТЭС")
        return jsonify(ok=False, error="Не удалось сохранить"), 500
    return jsonify(ok=True)
