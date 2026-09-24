# -*- coding: utf-8 -*-
"""Маршруты модуля «Экология»."""

from __future__ import annotations

from flask import current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required

from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.gis_tek_constants import REPORT_PG, REPORT_ZV
from app.ecology.services.gis_tek_export_services import build_gis_tek_excel_stream
from app.ecology.services.gis_tek_import_services import import_gis_tek_from_xlsx_bytes
from app.ecology.services.gis_tek_page_services import (
    build_gis_tek_page_context,
    can_edit_ecology,
)
from app.ecology.services.gis_tes_fuel_comparison_constants import COMPARISON_GROUPS
from app.ecology.services.formula_text.operating_tes_formula_text_services import (
    list_formulas_for_admin,
    reset_formula_text_override,
    save_formula_text_override,
)
from app.extensions import db
from app.generation.forms.station_forms import StationFilterForm


def _report_list_endpoint(kind: str) -> str:
    return "ecology_bp.gis_tek_pg" if kind == REPORT_PG else "ecology_bp.gis_tek_pollutants"


def _redirect_kind(kind: str, **extra):
    endpoint = _report_list_endpoint(kind)
    args = request.args.to_dict(flat=True)
    args.update(extra)
    return redirect(url_for(endpoint, **args))


def _render_report(kind: str):
    endpoint = _report_list_endpoint(kind)
    if request.args.get("reset_filters") == "1":
        keep = {}
        for key in ("year", "per_page", "show_totals", "show_empty_rows"):
            value = request.args.get(key)
            if value not in (None, ""):
                keep[key] = value
        return redirect(url_for(endpoint, **keep))
    context = build_gis_tek_page_context(kind, request.args)
    context["can_edit"] = can_edit_ecology(current_user)
    context["form"] = StationFilterForm()
    context["show_ved_filter"] = True
    context["station_filters_hidden_skip_keys"] = ["page"]
    context["list_endpoint"] = endpoint
    context["station_filters_action"] = url_for(endpoint)
    reset_keep = {}
    if context.get("selected_year") is not None:
        reset_keep["year"] = context["selected_year"]
    if context.get("per_page_param"):
        reset_keep["per_page"] = context["per_page_param"]
    reset_keep["show_totals"] = "1" if context.get("show_totals") else "0"
    reset_keep["show_empty_rows"] = "1" if context.get("show_empty_rows") else "0"
    context["station_filters_reset_url"] = url_for(endpoint, **reset_keep)
    context["import_endpoint"] = (
        "ecology_bp.gis_tek_pg_import"
        if kind == REPORT_PG
        else "ecology_bp.gis_tek_pollutants_import"
    )
    context["export_endpoint"] = (
        "ecology_bp.gis_tek_pg_export"
        if kind == REPORT_PG
        else "ecology_bp.gis_tek_pollutants_export"
    )
    return render_template("ecology/gis_tek_report.html", **context)


def _import_report(kind: str):
    if not can_edit_ecology(current_user):
        flash("Недостаточно прав для загрузки данных.", "danger")
        return _redirect_kind(kind)
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Файл не выбран.", "danger")
        return _redirect_kind(kind)
    raw_name = str(upload.filename).strip().lower()
    if not (raw_name.endswith(".xlsx") or raw_name.endswith(".xlsm") or raw_name.endswith(".xls")):
        flash("Ожидается файл Excel (.xlsx).", "danger")
        return _redirect_kind(kind)
    raw = upload.read()
    if not raw:
        flash("Пустой файл.", "danger")
        return _redirect_kind(kind)
    user = session.get("username") or getattr(current_user, "username", None) or "Неизвестный пользователь"
    try:
        stats = import_gis_tek_from_xlsx_bytes(raw, kind, user)
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return _redirect_kind(kind)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Импорт ГИС ТЭК (%s)", kind)
        flash("Не удалось выполнить импорт. Подробности — в журнале сервера.", "danger")
        return _redirect_kind(kind)
    flash(stats.get("message") or "Импорт завершён.", "success")
    return _redirect_kind(kind)


def _export_report(kind: str):
    stream = build_gis_tek_excel_stream(kind, request.args)
    filename = (
        "gis_tek_parnikovye_gazy.xlsx" if kind == REPORT_PG else "gis_tek_zagryaznyayushchie_veshchestva.xlsx"
    )
    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@ecology_bp.route("/")
@login_required
def hub():
    return render_template(
        "ecology/ecology_start.html",
        can_edit_ecology=can_edit_ecology(current_user),
        comparison_groups=COMPARISON_GROUPS,
    )


@ecology_bp.route("/formulas/")
@login_required
def operating_tes_formulas():
    if not can_edit_ecology(current_user):
        flash("Недостаточно прав для редактирования текстов формул.", "danger")
        return redirect(url_for("ecology_bp.hub"))
    return render_template(
        "ecology/operating_tes/operating_tes_formulas.html",
        page_title="Тексты формул для модуля «Экология»",
        formula_rows=list_formulas_for_admin(),
    )


@ecology_bp.route("/formulas/save", methods=["POST"])
@login_required
def operating_tes_formulas_save():
    if not can_edit_ecology(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    try:
        save_formula_text_override(
            formula_key=str(data.get("formula_key") or ""),
            formula_text=str(data.get("formula_text") or ""),
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True)


@ecology_bp.route("/formulas/reset", methods=["POST"])
@login_required
def operating_tes_formulas_reset():
    if not can_edit_ecology(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    key = str(data.get("formula_key") or "").strip()
    if not key:
        return jsonify(ok=False, error="Не указан ключ формулы."), 400
    reset_formula_text_override(key)
    db.session.commit()
    return jsonify(ok=True)


@ecology_bp.route("/gis_tek/pg/", methods=["GET"])
@login_required
def gis_tek_pg():
    return _render_report(REPORT_PG)


@ecology_bp.route("/gis_tek/pg/import", methods=["POST"])
@login_required
def gis_tek_pg_import():
    return _import_report(REPORT_PG)


@ecology_bp.route("/gis_tek/pg/export.xlsx", methods=["GET"])
@login_required
def gis_tek_pg_export():
    return _export_report(REPORT_PG)


@ecology_bp.route("/gis_tek/pollutants/", methods=["GET"])
@login_required
def gis_tek_pollutants():
    return _render_report(REPORT_ZV)


@ecology_bp.route("/gis_tek/pollutants/import", methods=["POST"])
@login_required
def gis_tek_pollutants_import():
    return _import_report(REPORT_ZV)


@ecology_bp.route("/gis_tek/pollutants/export.xlsx", methods=["GET"])
@login_required
def gis_tek_pollutants_export():
    return _export_report(REPORT_ZV)
