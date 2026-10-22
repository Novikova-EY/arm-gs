# -*- coding: utf-8 -*-
"""Маршруты сопоставления данных ГИС ТЭС и Топливо."""

from __future__ import annotations

from datetime import datetime

from flask import (
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.datastructures import MultiDict

from app.common.services.help_services import parse_decimal_from_display
from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.export_gis_tes_fuel_comparison_services import (
    export_comparison_table_to_excel,
)
from app.ecology.services.ecology_logging_services import (
    context_lines,
    log_file_download,
    log_page_visit,
)
from app.ecology.services.gis_tek_page_services import can_edit_ecology, parse_norm_zv_parts
from app.ecology.services.gis_tes_fuel_comparison_constants import (
    ANALYSIS_SHEET_SLUGS,
    ZV_NORM_DEFAULT_PARTS,
)
from app.ecology.services.gis_tes_fuel_comparison_services import (
    build_comparison_table_context,
    save_analysis_ecology_cell,
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
                "emission_rounding_digits",
                "specific_rounding_digits",
                "per_page",
                "show_totals",
                "show_empty_rows",
                "show_reported",
            )
            if (value := request.args.get(key)) not in (None, "")
        }
        if "norm_zv" in request.args:
            keep["norm_zv"] = request.args.getlist("norm_zv")
        return redirect(
            url_for("ecology_bp.gis_tes_fuel_comparison", sheet_slug=sheet_slug, **keep)
        )
    context = build_comparison_table_context(
        sheet_slug,
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
        emission_rounding_digits=request.args.get("emission_rounding_digits"),
        specific_rounding_digits=request.args.get("specific_rounding_digits"),
        request_args=request.args,
    )
    if context is None:
        abort(404)
    year_keep = {
        key: context[key]
        for key in (
            "start_year",
            "end_year",
            "rounding_digits",
            "emission_rounding_digits",
            "specific_rounding_digits",
            "per_page",
        )
        if context.get(key) is not None
    }
    if "norm_zv" in request.args:
        year_keep["norm_zv"] = context.get("norm_zv_selected") or [""]
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
        can_edit_ecology(current_user) and sheet_slug in ANALYSIS_SHEET_SLUGS
    )
    log_page_visit(
        "Сопоставление данных ГИС ТЭС и Топливо",
        tab=context["page_title"],
        details=context_lines(
            ("период", f"{context.get('start_year')}–{context.get('end_year')}"),
        ),
    )
    return render_template("ecology/analysis/gis_tes_fuel_comparison.html", **context)


@ecology_bp.route("/analysis/<sheet_slug>/export.xlsx")
@login_required
def gis_tes_fuel_comparison_export(sheet_slug: str):
    """Выгрузка таблицы анализа в Excel (все страницы, с ОЭС/РЭС)."""
    export_args = MultiDict(request.args)
    export_args["per_page"] = "all"
    context = build_comparison_table_context(
        sheet_slug,
        start_year=export_args.get("start_year"),
        end_year=export_args.get("end_year"),
        rounding_digits=export_args.get("rounding_digits"),
        emission_rounding_digits=export_args.get("emission_rounding_digits"),
        specific_rounding_digits=export_args.get("specific_rounding_digits"),
        request_args=export_args,
    )
    if context is None:
        abort(404)
    stream = export_comparison_table_to_excel(context)
    filename = f"ecology_analysis_{sheet_slug}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    log_file_download(
        context["page_title"],
        filename,
        details=[f"лист={sheet_slug}"],
    )
    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        max_age=0,
    )


@ecology_bp.route("/analysis/<sheet_slug>/value/", methods=["PATCH"])
@login_required
def gis_tes_fuel_comparison_update_value(sheet_slug: str):
    if not can_edit_ecology(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    if sheet_slug not in ANALYSIS_SHEET_SLUGS:
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
        values = save_analysis_ecology_cell(
            sheet_slug,
            station_numb,
            year_number,
            column_key,
            amount,
            rounding_digits=data.get("rounding_digits") or request.args.get("rounding_digits"),
            emission_rounding_digits=(
                data.get("emission_rounding_digits")
                or request.args.get("emission_rounding_digits")
            ),
            specific_rounding_digits=(
                data.get("specific_rounding_digits")
                or request.args.get("specific_rounding_digits")
            ),
            norm_zv_parts=parse_norm_zv_parts(
                data if "norm_zv" in data else request.args,
                ZV_NORM_DEFAULT_PARTS,
            ),
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить параметр анализа ЗВ/ПГ")
        return jsonify(ok=False, error="Не удалось сохранить"), 500
    return jsonify(ok=True, values=values)
