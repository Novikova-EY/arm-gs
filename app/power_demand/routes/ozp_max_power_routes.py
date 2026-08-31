# -*- coding: utf-8 -*-
"""Маршруты таблицы «Максимумы потребления мощности ОЗП»."""
from __future__ import annotations

from flask import jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.power_demand.routes.power_demand_bp import power_demand_bp
from app.power_demand.services.access_services import can_edit_power_demand
from app.power_demand.services import ozp_max_power_services as ozp


def _parse_request_year_range() -> tuple[int, int]:
    years = ozp.filter_year_list()
    return ozp.parse_year_range(
        request.args.get("start_year"),
        request.args.get("end_year"),
        years=years,
    )


def _parse_request_rounding() -> int:
    return ozp.parse_rounding_digits(request.args.get("rounding_digits"))


@power_demand_bp.route("/ozp_maxima/")
@login_required
def ozp_maxima():
    start_year, end_year = _parse_request_year_range()
    rounding_digits = _parse_request_rounding()
    context = ozp.build_page_context(
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        can_edit=can_edit_power_demand(current_user),
    )
    return render_template("power_demand/ozp_max_power.html", **context)


@power_demand_bp.route("/ozp_maxima/save", methods=["POST"])
@login_required
def ozp_maxima_save():
    if not can_edit_power_demand(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    cells = data.get("cells")
    if not isinstance(cells, list):
        return jsonify(ok=False, error="Неверный запрос"), 400
    result = ozp.save_ozp_cells(cells)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@power_demand_bp.route("/ozp_maxima/export.xlsx", methods=["GET", "POST"])
@login_required
def ozp_maxima_export():
    start_year, end_year = _parse_request_year_range()
    rounding_digits = _parse_request_rounding()
    columns = ozp.build_ozp_columns(start_year, end_year)
    stream = ozp.build_ozp_excel_stream(
        columns=columns,
        year_groups=ozp.build_year_header_groups(columns),
        stored=ozp.load_ozp_rows_by_end_year(),
        rounding_digits=rounding_digits,
    )
    filename = f"power_demand_ozp_maxima_{start_year}_{end_year}.xlsx"
    return send_file(
        stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
