# -*- coding: utf-8 -*-
"""Страница электроёмкости по ФО: /electrical_intensity/electrical_intensity_fo/."""

from __future__ import annotations

from flask import current_app, flash, jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.common.services.database_version_services import get_current_version
from app.extensions import db
from app.energy_consumption.electrical_intensity.routes.electrical_intensity_root_bp import (
    electrical_intensity_root_bp,
)
from app.energy_consumption.electrical_intensity.routes.electrical_intensity_route_helpers import (
    csrf,
    csrf_ok,
    parse_ei_export_years_list,
    parse_rounding_digits,
    redirect_preserving_query,
)
from app.energy_consumption.electrical_intensity.services.electrical_intensity_export_services import (
    build_electrical_intensity_excel_stream,
)
from app.energy_consumption.electrical_intensity.services.electrical_intensity_import_services import (
    import_electrical_intensity_from_xlsx_bytes,
)
from app.energy_consumption.electrical_intensity.services.electrical_intensity_logging import (
    count_electrical_intensity_logs,
    load_formatted_electrical_intensity_logs,
    load_electrical_intensity_logs_raw,
)
from app.energy_consumption.electrical_intensity.services.electrical_intensity_page_services import (
    parse_electrical_intensity_page_kwargs,
)
from app.energy_consumption.electrical_intensity.services.electrical_intensity_services import (
    build_electrical_intensity_page_context,
    calculate_and_save_all_graph_points,
    compute_graph_points_for_row,
    save_electrical_intensity_from_post,
)
from app.logs.services.log_display_utils import format_logs_for_display


@electrical_intensity_root_bp.route("/electrical_intensity_fo/", methods=["GET", "POST"])
@login_required
def electrical_intensity():
    form = csrf()
    rd = parse_rounding_digits()

    if request.method == "POST":
        if not getattr(current_user, "has_admin", False):
            flash("Недостаточно прав для изменения данных.", "danger")
            return redirect_preserving_query(rounding_digits=rd)
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect_preserving_query(rounding_digits=rd)
        try:
            updated, skipped = save_electrical_intensity_from_post(request.form)
            db.session.commit()
            flash(f"Сохранено ячеек: {updated}. Пропущено: {skipped}.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Ошибка сохранения: {exc}", "danger")
        return redirect_preserving_query(rounding_digits=rd)

    page_kw = parse_electrical_intensity_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    lt_ei_initial_visible_years = page_kw.pop("lt_ei_initial_visible_years", None)
    lt_ei_year_seg_state = page_kw.pop("lt_ei_year_seg_state", None)
    context = build_electrical_intensity_page_context(**page_kw)
    if lt_ei_initial_visible_years is not None:
        context["lt_ei_initial_visible_years"] = lt_ei_initial_visible_years
    if lt_ei_year_seg_state is not None:
        context["lt_ei_year_seg_state"] = lt_ei_year_seg_state
    context["form"] = form
    context["can_edit"] = getattr(current_user, "has_admin", False)
    vid = get_current_version()
    context["electrical_intensity_logs_formatted"] = load_formatted_electrical_intensity_logs(
        vid, limit=50
    )
    return render_template("energy_consumption/electrical_intensity/electrical_intensity.html", **context)


@electrical_intensity_root_bp.route(
    "/electrical_intensity_fo/calculate_graph_points", methods=["POST"]
)
@login_required
def electrical_intensity_calculate_graph_points():
    """Рассчитать все характерные точки графика (≤ текущего года) и сохранить в БД."""
    form = csrf()
    rd = parse_rounding_digits()
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для изменения данных.", "danger")
        return redirect_preserving_query(rounding_digits=rd)
    if not form.validate_on_submit():
        flash("Ошибка CSRF.", "danger")
        return redirect_preserving_query(rounding_digits=rd)
    page_kw = parse_electrical_intensity_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    page_kw.pop("lt_ei_initial_visible_years", None)
    page_kw.pop("lt_ei_year_seg_state", None)
    try:
        updated, skipped = calculate_and_save_all_graph_points(
            rounding_digits=page_kw["rounding_digits"],
            display_years=page_kw["display_years"],
            fd_filter_ids=page_kw["fd_filter_ids"],
            ved_filter_ids=page_kw["ved_filter_ids"],
            population_filter_selected=page_kw["population_filter_selected"],
        )
        db.session.commit()
        flash(
            f"Рассчитаны и сохранены точки графика: {updated}. Без изменений: {skipped}.",
            "success",
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка расчёта точек графика: {exc}", "danger")
    return redirect_preserving_query(rounding_digits=rd)


@electrical_intensity_root_bp.route(
    "/electrical_intensity_fo/calculate_graph_points_row", methods=["POST"]
)
@login_required
def electrical_intensity_calculate_graph_points_row():
    """Рассчитать graph_point для одной строки (без сохранения в БД)."""
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    if not csrf_ok():
        return jsonify(ok=False, error="Ошибка CSRF."), 400
    rd = parse_rounding_digits()
    page_kw = parse_electrical_intensity_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    page_kw.pop("lt_ei_initial_visible_years", None)
    page_kw.pop("lt_ei_year_seg_state", None)
    kind = str(request.form.get("territory_kind") or "").strip()
    terr_raw = str(request.form.get("territory_id") or "").strip()
    ved_raw = str(request.form.get("ved_id") or "").strip()
    fd_id: int | None = None
    if terr_raw:
        try:
            fd_id = int(terr_raw)
        except ValueError:
            fd_id = None
    try:
        result = compute_graph_points_for_row(
            rounding_digits=page_kw["rounding_digits"],
            display_years=page_kw["display_years"],
            territory_kind=kind,
            territory_id=fd_id,
            ved_id=ved_raw or None,
        )
    except Exception as exc:
        current_app.logger.exception("Расчёт точек графика для строки")
        return jsonify(ok=False, error=str(exc)), 500
    if not (result.get("cells_display") or {}):
        return (
            jsonify(
                ok=False,
                error=(
                    "Недостаточно исходных данных для расчёта "
                    "(выпуск продукции, потребление и инвестиции по выбранной территории и ВЭД)."
                ),
            ),
            422,
        )
    return jsonify(ok=True, **result)


@electrical_intensity_root_bp.route("/electrical_intensity_fo/logs", methods=["GET"])
@login_required
def electrical_intensity_logs():
    """AJAX: журнал изменений электроёмкости для текущей версии БД."""
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", 150, type=int)
    vid = get_current_version()
    if limit == 0:
        total = count_electrical_intensity_logs(vid)
        return jsonify(
            ok=True,
            logs=[],
            offset=0,
            limit=0,
            count=0,
            total=total,
            has_more=False,
        )
    limit = max(1, min(int(limit), 500))
    rows = load_electrical_intensity_logs_raw(vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_electrical_intensity_logs(vid)
    n = len(formatted)
    return jsonify(
        ok=True,
        logs=formatted,
        offset=offset,
        limit=limit,
        count=n,
        total=total,
        has_more=(offset + n) < total,
    )


@electrical_intensity_root_bp.route("/electrical_intensity_fo/export.xlsx")
@login_required
def electrical_intensity_export_xlsx():
    rd = parse_rounding_digits()
    page_kw = parse_electrical_intensity_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    lt_ei_initial_visible_years = page_kw.pop("lt_ei_initial_visible_years", None)
    page_kw.pop("lt_ei_year_seg_state", None)
    context = build_electrical_intensity_page_context(**page_kw)
    if lt_ei_initial_visible_years is not None:
        context["lt_ei_initial_visible_years"] = lt_ei_initial_visible_years
    export_years = parse_ei_export_years_list(
        list(context.get("years") or context.get("display_years") or [])
    )
    if export_years is not None:
        context["lt_ei_initial_visible_years"] = export_years
    stream = build_electrical_intensity_excel_stream(context)
    return send_file(
        stream,
        as_attachment=True,
        download_name="elektroemkost.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@electrical_intensity_root_bp.route("/electrical_intensity_fo/import.xlsx", methods=["POST"])
@login_required
def electrical_intensity_import_xlsx():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403

    upload = request.files.get("file")
    if upload is None or upload.filename is None or str(upload.filename).strip() == "":
        return jsonify(ok=False, error="Файл не выбран."), 400
    raw_name = str(upload.filename).strip().lower()
    if not (raw_name.endswith(".xlsx") or raw_name.endswith(".xlsm")):
        return jsonify(ok=False, error="Ожидается файл в формате .xlsx или .xlsm."), 400
    raw = upload.read()
    if not raw:
        return jsonify(ok=False, error="Пустой файл."), 400

    try:
        stats = import_electrical_intensity_from_xlsx_bytes(raw)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Импорт электроёмкости из Excel")
        return (
            jsonify(
                ok=False,
                error=(
                    "Не удалось выполнить импорт (ошибка при обработке файла или записи в БД). "
                    "Подробности — в журнале сервера приложения."
                ),
            ),
            400,
        )

    msg = (
        f"Импорт завершён: территорий {stats.get('territories', 0)}, "
        f"строк {stats.get('rows_processed', 0)}, "
        f"записано ячеек {stats.get('cells_written', 0)}."
    )
    warnings = stats.get("warnings") or []
    if warnings:
        msg += f" Предупреждений: {len(warnings)}."
    hints = warnings[:20]
    return jsonify(ok=True, message=msg, hints=hints, **stats)
