# -*- coding: utf-8 -*-
"""Маршруты сопоставления данных ГИС ТЭС и Топливо."""

from __future__ import annotations

from flask import abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.common.services.help_services import parse_decimal_from_display
from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.gis_tek_page_services import can_edit_ecology
from app.ecology.services.gis_tes_fuel_comparison_constants import PG_ANALYSIS_SHEET_SLUGS
from app.ecology.services.gis_tes_fuel_comparison_services import (
    build_comparison_table_context,
    save_analysis_pg_ecology_cell,
)
from app.generation.forms.station_forms import StationFilterForm


@ecology_bp.route("/analysis/<sheet_slug>/")
@login_required
def gis_tes_fuel_comparison(sheet_slug: str):
    if request.args.get("reset_filters") == "1":
        keep = {
            key: value
            for key in (
                "start_year",
                "end_year",
                "rounding_digits",
                "per_page",
                "show_totals",
                "show_empty_rows",
                "show_reported",
            )
            if (value := request.args.get(key)) not in (None, "")
        }
        return redirect(
            url_for("ecology_bp.gis_tes_fuel_comparison", sheet_slug=sheet_slug, **keep)
        )
    context = build_comparison_table_context(
        sheet_slug,
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
        request_args=request.args,
    )
    if context is None:
        abort(404)
    year_keep = {
        key: context[key]
        for key in ("start_year", "end_year", "rounding_digits", "per_page")
        if context.get(key) is not None
    }
    year_keep["show_totals"] = "1" if context.get("show_totals") else "0"
    year_keep["show_empty_rows"] = "1" if context.get("show_empty_rows") else "0"
    year_keep["show_reported"] = "1" if context.get("show_reported") else "0"
    context["form"] = StationFilterForm()
    context["station_filters_action"] = url_for(
        "ecology_bp.gis_tes_fuel_comparison",
        sheet_slug=sheet_slug,
    )
    context["station_filters_reset_url"] = url_for(
        "ecology_bp.gis_tes_fuel_comparison",
        sheet_slug=sheet_slug,
        **year_keep,
    )
    context["can_edit"] = bool(
        can_edit_ecology(current_user) and sheet_slug in PG_ANALYSIS_SHEET_SLUGS
    )
    return render_template("ecology/analysis/gis_tes_fuel_comparison.html", **context)


@ecology_bp.route("/analysis/<sheet_slug>/value/", methods=["PATCH"])
@login_required
def gis_tes_fuel_comparison_update_value(sheet_slug: str):
    if not can_edit_ecology(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    if sheet_slug not in PG_ANALYSIS_SHEET_SLUGS:
        return jsonify(ok=False, error="Лист только для просмотра"), 400
    data = request.get_json(silent=True) or {}
    column_key = str(data.get("field") or "").strip()
    try:
        station_numb = int(data.get("numb"))
        year_number = int(data.get("year"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Некорректные станция или год"), 400
    raw = data.get("value")
    try:
        amount = parse_decimal_from_display(raw) if raw not in (None, "") else None
    except Exception:
        return jsonify(ok=False, error="Некорректное число"), 400
    try:
        values = save_analysis_pg_ecology_cell(
            sheet_slug,
            station_numb,
            year_number,
            column_key,
            amount,
            rounding_digits=data.get("rounding_digits") or request.args.get("rounding_digits"),
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить параметр анализа ПГ")
        return jsonify(ok=False, error="Не удалось сохранить"), 500
    return jsonify(ok=True, values=values)
