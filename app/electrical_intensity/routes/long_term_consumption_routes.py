# -*- coding: utf-8 -*-
"""Маршруты электроёмкости (долгосрочный спрос) — legacy-редиректы под /energy_consumption."""

from __future__ import annotations

from flask import redirect, render_template, request, url_for
from flask_login import login_required

from app.electrical_intensity.routes.long_term_consumption_bp import long_term_consumption_bp


@long_term_consumption_bp.route("/electrical_intensity_start/")
@login_required
def electrical_intensity_start():
    return render_template(
        "electrical_intensity/electrical_intensity_start.html",
        electrical_intensity_formulas_url=url_for(
            "electrical_intensity_root_bp.electrical_intensity_formulas",
        ),
    )


def _redirect_to_electrical_intensity_fo(subpath: str = ""):
    qs = request.query_string.decode()
    target = url_for("electrical_intensity_root_bp.electrical_intensity")
    if subpath:
        target = f"{target.rstrip('/')}/{subpath}"
    if qs:
        target = f"{target}?{qs}"
    return redirect(target, code=301)


@long_term_consumption_bp.route("/electrical_intensity/", methods=["GET", "POST"])
@long_term_consumption_bp.route("/electrical_intensity", defaults={"subpath": ""}, methods=["GET", "POST"])
@long_term_consumption_bp.route("/electrical_intensity/<path:subpath>")
def electrical_intensity_legacy_redirect(subpath=""):
    if subpath == "formulas" or subpath.startswith("formulas/"):
        qs = request.query_string.decode()
        target = url_for("electrical_intensity_root_bp.electrical_intensity_formulas")
        if subpath.startswith("formulas/"):
            suffix = subpath[len("formulas/") :]
            target = f"{target.rstrip('/')}/{suffix}"
        if qs:
            target = f"{target}?{qs}"
        return redirect(target, code=301)
    return _redirect_to_electrical_intensity_fo(subpath)


@long_term_consumption_bp.route("/electrical_intensity_fo/", methods=["GET", "POST"])
@login_required
def electrical_intensity_legacy():
    from app.electrical_intensity.routes.electrical_intensity_fo_routes import (
        electrical_intensity,
    )

    return electrical_intensity()


@long_term_consumption_bp.route(
    "/electrical_intensity_fo/calculate_graph_points", methods=["POST"]
)
@login_required
def electrical_intensity_calculate_graph_points_legacy():
    from app.electrical_intensity.routes.electrical_intensity_fo_routes import (
        electrical_intensity_calculate_graph_points,
    )

    return electrical_intensity_calculate_graph_points()


@long_term_consumption_bp.route(
    "/electrical_intensity_fo/calculate_graph_points_row", methods=["POST"]
)
@login_required
def electrical_intensity_calculate_graph_points_row_legacy():
    from app.electrical_intensity.routes.electrical_intensity_fo_routes import (
        electrical_intensity_calculate_graph_points_row,
    )

    return electrical_intensity_calculate_graph_points_row()


@long_term_consumption_bp.route("/electrical_intensity_fo/logs", methods=["GET"])
@login_required
def electrical_intensity_logs_legacy():
    from app.electrical_intensity.routes.electrical_intensity_fo_routes import (
        electrical_intensity_logs,
    )

    return electrical_intensity_logs()


@long_term_consumption_bp.route("/electrical_intensity_fo/export.xlsx")
@login_required
def electrical_intensity_export_xlsx_legacy():
    return _redirect_to_electrical_intensity_fo("export.xlsx")


@long_term_consumption_bp.route("/electrical_intensity_fo/import.xlsx", methods=["POST"])
@login_required
def electrical_intensity_import_xlsx_legacy():
    from app.electrical_intensity.routes.electrical_intensity_fo_routes import (
        electrical_intensity_import_xlsx,
    )

    return electrical_intensity_import_xlsx()


def _redirect_to_electrical_intensity_formulas():
    return redirect(
        url_for("electrical_intensity_root_bp.electrical_intensity_formulas", **request.args)
    )


@long_term_consumption_bp.route("/electrical_intensity_formulas/")
@login_required
def electrical_intensity_formulas_legacy():
    return _redirect_to_electrical_intensity_formulas()


@long_term_consumption_bp.route("/electrical_intensity_formulas/save", methods=["POST"])
@login_required
def electrical_intensity_formulas_legacy_save():
    from app.electrical_intensity.routes.electrical_intensity_formulas_routes import (
        electrical_intensity_formulas_save,
    )

    return electrical_intensity_formulas_save()


@long_term_consumption_bp.route("/electrical_intensity_formulas/reset", methods=["POST"])
@login_required
def electrical_intensity_formulas_legacy_reset():
    from app.electrical_intensity.routes.electrical_intensity_formulas_routes import (
        electrical_intensity_formulas_reset,
    )

    return electrical_intensity_formulas_reset()
