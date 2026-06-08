# -*- coding: utf-8 -*-
"""Маршруты модуля «Экономика»."""

from __future__ import annotations

from flask import current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.energy_consumption.forms.energy_consumption_parameter_forms import EmptyCSRFForm
from app.extensions import db
from app.economics.routes.economics_bp import economics_bp
from app.economics.services.ved_consumption_import_services import (
    import_ved_consumption_from_xlsx_bytes,
)
from app.economics.services.ved_consumption_export_services import (
    build_ved_consumption_excel_stream,
)
from app.economics.services.ved_consumption_page_services import (
    parse_ved_consumption_page_kwargs,
)
from app.common.services.database_version_services import get_current_version
from app.logs.services.log_display_utils import format_logs_for_display
from app.economics.services.ved_consumption_logging import (
    count_ved_consumption_logs,
    load_formatted_ved_consumption_logs,
    load_ved_consumption_logs_raw,
)
from app.economics.services.ved_consumption_services import (
    build_ved_consumption_page_context,
    save_ved_consumption_from_post,
)
from app.economics.services.accum_fixed_capital_import_services import (
    import_accum_fixed_capital_from_xlsx_bytes,
)
from app.economics.services.accum_fixed_capital_export_services import (
    build_accum_fixed_capital_excel_stream,
)
from app.economics.services.accum_fixed_capital_page_services import (
    parse_accum_fixed_capital_page_kwargs,
)
from app.economics.services.accum_fixed_capital_logging import (
    count_accum_fixed_capital_logs,
    load_formatted_accum_fixed_capital_logs,
    load_accum_fixed_capital_logs_raw,
)
from app.economics.services.accum_fixed_capital_services import (
    build_accum_fixed_capital_page_context,
    save_accum_fixed_capital_from_post,
)
from app.economics.services.formula_text import economics_formula_text_services as efts
from app.economics.services.product_output_import_services import (
    import_product_output_from_xlsx_bytes,
)
from app.economics.services.product_output_export_services import (
    build_product_output_excel_stream,
)
from app.economics.services.product_output_page_services import (
    parse_product_output_page_kwargs,
)
from app.economics.services.product_output_logging import (
    count_product_output_logs,
    load_formatted_product_output_logs,
    load_product_output_logs_raw,
)
from app.economics.services.product_output_services import (
    build_product_output_page_context,
    save_product_output_from_post,
)
from app.economics.services.population_import_services import (
    import_population_from_xlsx_bytes,
)
from app.economics.services.population_export_services import (
    build_population_excel_stream,
)
from app.economics.services.population_page_services import (
    parse_population_page_kwargs,
)
from app.economics.services.population_logging import (
    count_population_logs,
    load_formatted_population_logs,
    load_population_logs_raw,
)
from app.economics.services.population_services import (
    build_population_page_context,
    save_population_from_post,
)
from app.economics.services.accum_monetary_income_import_services import (
    import_accum_monetary_income_from_xlsx_bytes,
)
from app.economics.services.accum_monetary_income_export_services import (
    build_accum_monetary_income_excel_stream,
)
from app.economics.services.accum_monetary_income_page_services import (
    parse_accum_monetary_income_page_kwargs,
)
from app.economics.services.accum_monetary_income_logging import (
    count_accum_monetary_income_logs,
    load_formatted_accum_monetary_income_logs,
    load_accum_monetary_income_logs_raw,
)
from app.economics.services.accum_monetary_income_services import (
    build_accum_monetary_income_page_context,
    save_accum_monetary_income_from_post,
)


def _csrf():
    return EmptyCSRFForm()


def _redirect_preserving_query(endpoint: str, **extra):
    qs = (request.form.get("preserve_qs") or "").strip()
    if qs:
        base = url_for(endpoint, **extra)
        return redirect(f"{base}?{qs}" if "?" not in base else f"{base}&{qs}")
    args = {k: v for k, v in request.args.items(multi=True)}
    flat: dict = {}
    for k, v in args.items():
        flat[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
    flat.update(extra)
    return redirect(url_for(endpoint, **flat))


def _parse_rounding_digits() -> int:
    raw = request.args.get("rounding_digits")
    if request.method == "POST" and (raw is None or str(raw).strip() == ""):
        raw = request.form.get("rounding_digits")
    if raw is None or str(raw).strip() == "":
        return 1
    try:
        v = int(raw)
    except (ValueError, TypeError):
        return 1
    if v in (0, 1, 2, 3, -1):
        return v
    return 1


@economics_bp.route("/")
@login_required
def hub():
    return render_template("economics/economics_start.html")


@economics_bp.route("/ved_consumption/", methods=["GET", "POST"])
@login_required
def ved_consumption():
    form = _csrf()
    rd = _parse_rounding_digits()

    if request.method == "POST":
        if not getattr(current_user, "has_admin", False):
            flash("Недостаточно прав для изменения данных.", "danger")
            return _redirect_preserving_query("economics_bp.ved_consumption", rounding_digits=rd)
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return _redirect_preserving_query("economics_bp.ved_consumption", rounding_digits=rd)
        try:
            updated, skipped = save_ved_consumption_from_post(request.form)
            db.session.commit()
            flash(f"Сохранено ячеек: {updated}. Пропущено: {skipped}.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Ошибка сохранения: {exc}", "danger")
        return _redirect_preserving_query("economics_bp.ved_consumption", rounding_digits=rd)

    page_kw = parse_ved_consumption_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_ved_consumption_page_context(**page_kw)
    context["form"] = form
    context["can_edit"] = getattr(current_user, "has_admin", False)
    vid = get_current_version()
    context["ved_consumption_logs_formatted"] = load_formatted_ved_consumption_logs(
        vid, limit=50
    )
    return render_template("economics/ved_consumption.html", **context)


@economics_bp.route("/ved_consumption/logs", methods=["GET"])
@login_required
def ved_consumption_logs():
    """AJAX: журнал изменений потребления по ВЭД для текущей версии БД."""
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", 150, type=int)
    vid = get_current_version()
    if limit == 0:
        total = count_ved_consumption_logs(vid)
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
    rows = load_ved_consumption_logs_raw(vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_ved_consumption_logs(vid)
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


@economics_bp.route("/ved_consumption/export.xlsx")
@login_required
def ved_consumption_export_xlsx():
    rd = _parse_rounding_digits()
    page_kw = parse_ved_consumption_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_ved_consumption_page_context(**page_kw)
    stream = build_ved_consumption_excel_stream(context)
    return send_file(
        stream,
        as_attachment=True,
        download_name="potreblenie_po_ved.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@economics_bp.route("/ved_consumption/import.xlsx", methods=["POST"])
@login_required
def ved_consumption_import_xlsx():
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
        stats = import_ved_consumption_from_xlsx_bytes(raw)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Импорт потребления по ВЭД из Excel")
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
        f"строк ВЭД {stats.get('rows_processed', 0)}, "
        f"записано ячеек {stats.get('cells_written', 0)}."
    )
    db_versions = stats.get("database_versions") or 0
    if db_versions:
        msg += f" Данные записаны во все версии БД ({db_versions})."
    warnings = stats.get("warnings") or []
    if warnings:
        msg += f" Предупреждений: {len(warnings)}."
    hints = warnings[:20]
    return jsonify(ok=True, message=msg, hints=hints, **stats)


@economics_bp.route("/formulas/")
@login_required
def economics_formulas():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для редактирования текстов формул.", "danger")
        return redirect(url_for("economics_bp.hub"))
    return render_template(
        "economics/economics_formulas.html",
        page_title="Тексты формул — Экономика",
        formula_rows=efts.list_formulas_for_admin(),
    )


@economics_bp.route("/formulas/save", methods=["POST"])
@login_required
def economics_formulas_save():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    try:
        efts.save_formula_text_override(
            formula_key=str(data.get("formula_key") or ""),
            formula_text=str(data.get("formula_text") or ""),
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True)


@economics_bp.route("/formulas/reset", methods=["POST"])
@login_required
def economics_formulas_reset():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    key = str(data.get("formula_key") or "").strip()
    if not key:
        return jsonify(ok=False, error="Не указан ключ формулы."), 400
    try:
        efts.reset_formula_text_override(key)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True)


@economics_bp.route("/ved_consumption_formulas/")
@login_required
def ved_consumption_formulas():
    return redirect(url_for("economics_bp.economics_formulas"))


@economics_bp.route("/ved_consumption_formulas/save", methods=["POST"])
@login_required
def ved_consumption_formulas_save():
    return economics_formulas_save()


@economics_bp.route("/ved_consumption_formulas/reset", methods=["POST"])
@login_required
def ved_consumption_formulas_reset():
    return economics_formulas_reset()


@economics_bp.route("/accum_fixed_capital/", methods=["GET", "POST"])
@login_required
def accum_fixed_capital():
    form = _csrf()
    rd = _parse_rounding_digits()

    if request.method == "POST":
        if not getattr(current_user, "has_admin", False):
            flash("Недостаточно прав для изменения данных.", "danger")
            return _redirect_preserving_query(
                "economics_bp.accum_fixed_capital", rounding_digits=rd
            )
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return _redirect_preserving_query(
                "economics_bp.accum_fixed_capital", rounding_digits=rd
            )
        try:
            updated, skipped = save_accum_fixed_capital_from_post(request.form)
            db.session.commit()
            flash(f"Сохранено ячеек: {updated}. Пропущено: {skipped}.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Ошибка сохранения: {exc}", "danger")
        return _redirect_preserving_query(
            "economics_bp.accum_fixed_capital", rounding_digits=rd
        )

    page_kw = parse_accum_fixed_capital_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_accum_fixed_capital_page_context(**page_kw)
    context["form"] = form
    context["can_edit"] = getattr(current_user, "has_admin", False)
    vid = get_current_version()
    context["accum_fixed_capital_logs_formatted"] = load_formatted_accum_fixed_capital_logs(
        vid, limit=50
    )
    return render_template("economics/accum_fixed_capital.html", **context)


@economics_bp.route("/accum_fixed_capital/logs", methods=["GET"])
@login_required
def accum_fixed_capital_logs():
    """AJAX: журнал изменений накопленных инвестиций для текущей версии БД."""
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", 150, type=int)
    vid = get_current_version()
    if limit == 0:
        total = count_accum_fixed_capital_logs(vid)
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
    rows = load_accum_fixed_capital_logs_raw(vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_accum_fixed_capital_logs(vid)
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


@economics_bp.route("/accum_fixed_capital/export.xlsx")
@login_required
def accum_fixed_capital_export_xlsx():
    rd = _parse_rounding_digits()
    page_kw = parse_accum_fixed_capital_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_accum_fixed_capital_page_context(**page_kw)
    stream = build_accum_fixed_capital_excel_stream(context)
    return send_file(
        stream,
        as_attachment=True,
        download_name="nakoplennye_investicii_osn_kapital.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@economics_bp.route("/accum_fixed_capital/import.xlsx", methods=["POST"])
@login_required
def accum_fixed_capital_import_xlsx():
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
        stats = import_accum_fixed_capital_from_xlsx_bytes(raw)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Импорт накопленных инвестиций из Excel")
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
        f"строк ВЭД {stats.get('rows_processed', 0)}, "
        f"записано ячеек {stats.get('cells_written', 0)}."
    )
    db_versions = stats.get("database_versions") or 0
    if db_versions:
        msg += f" Данные записаны во все версии БД ({db_versions})."
    warnings = stats.get("warnings") or []
    if warnings:
        msg += f" Предупреждений: {len(warnings)}."
    hints = warnings[:20]
    return jsonify(ok=True, message=msg, hints=hints, **stats)


@economics_bp.route("/accum_fixed_capital_formulas/")
@login_required
def accum_fixed_capital_formulas():
    return redirect(url_for("economics_bp.economics_formulas"))


@economics_bp.route("/accum_fixed_capital_formulas/save", methods=["POST"])
@login_required
def accum_fixed_capital_formulas_save():
    return economics_formulas_save()


@economics_bp.route("/accum_fixed_capital_formulas/reset", methods=["POST"])
@login_required
def accum_fixed_capital_formulas_reset():
    return economics_formulas_reset()


@economics_bp.route("/product_output/", methods=["GET", "POST"])
@login_required
def product_output():
    form = _csrf()
    rd = _parse_rounding_digits()

    if request.method == "POST":
        if not getattr(current_user, "has_admin", False):
            flash("Недостаточно прав для изменения данных.", "danger")
            return _redirect_preserving_query(
                "economics_bp.product_output", rounding_digits=rd
            )
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return _redirect_preserving_query(
                "economics_bp.product_output", rounding_digits=rd
            )
        try:
            updated, skipped = save_product_output_from_post(request.form)
            db.session.commit()
            flash(f"Сохранено ячеек: {updated}. Пропущено: {skipped}.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Ошибка сохранения: {exc}", "danger")
        return _redirect_preserving_query(
            "economics_bp.product_output", rounding_digits=rd
        )

    page_kw = parse_product_output_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_product_output_page_context(**page_kw)
    context["form"] = form
    context["can_edit"] = getattr(current_user, "has_admin", False)
    vid = get_current_version()
    context["product_output_logs_formatted"] = load_formatted_product_output_logs(
        vid, limit=50
    )
    return render_template("economics/product_output.html", **context)


@economics_bp.route("/product_output/logs", methods=["GET"])
@login_required
def product_output_logs():
    """AJAX: журнал изменений выпуска продукции для текущей версии БД."""
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", 150, type=int)
    vid = get_current_version()
    if limit == 0:
        total = count_product_output_logs(vid)
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
    rows = load_product_output_logs_raw(vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_product_output_logs(vid)
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


@economics_bp.route("/product_output/export.xlsx")
@login_required
def product_output_export_xlsx():
    rd = _parse_rounding_digits()
    page_kw = parse_product_output_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_product_output_page_context(**page_kw)
    stream = build_product_output_excel_stream(context)
    return send_file(
        stream,
        as_attachment=True,
        download_name="vypusk_produktsii.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@economics_bp.route("/product_output/import.xlsx", methods=["POST"])
@login_required
def product_output_import_xlsx():
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
        stats = import_product_output_from_xlsx_bytes(raw)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Импорт выпуска продукции из Excel")
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
        f"строк ВЭД {stats.get('rows_processed', 0)}, "
        f"записано ячеек {stats.get('cells_written', 0)}."
    )
    db_versions = stats.get("database_versions") or 0
    if db_versions:
        msg += f" Данные записаны во все версии БД ({db_versions})."
    warnings = stats.get("warnings") or []
    if warnings:
        msg += f" Предупреждений: {len(warnings)}."
    hints = warnings[:20]
    return jsonify(ok=True, message=msg, hints=hints, **stats)


@economics_bp.route("/product_output_formulas/")
@login_required
def product_output_formulas():
    return redirect(url_for("economics_bp.economics_formulas"))


@economics_bp.route("/product_output_formulas/save", methods=["POST"])
@login_required
def product_output_formulas_save():
    return economics_formulas_save()


@economics_bp.route("/product_output_formulas/reset", methods=["POST"])
@login_required
def product_output_formulas_reset():
    return economics_formulas_reset()


@economics_bp.route("/population/", methods=["GET", "POST"])
@login_required
def population():
    form = _csrf()
    rd = _parse_rounding_digits()

    if request.method == "POST":
        if not getattr(current_user, "has_admin", False):
            flash("Недостаточно прав для изменения данных.", "danger")
            return _redirect_preserving_query(
                "economics_bp.population", rounding_digits=rd
            )
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return _redirect_preserving_query(
                "economics_bp.population", rounding_digits=rd
            )
        try:
            updated, skipped = save_population_from_post(request.form)
            db.session.commit()
            flash(f"Сохранено ячеек: {updated}. Пропущено: {skipped}.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Ошибка сохранения: {exc}", "danger")
        return _redirect_preserving_query(
            "economics_bp.population", rounding_digits=rd
        )

    page_kw = parse_population_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_population_page_context(**page_kw)
    context["form"] = form
    context["can_edit"] = getattr(current_user, "has_admin", False)
    vid = get_current_version()
    context["population_logs_formatted"] = load_formatted_population_logs(
        vid, limit=50
    )
    return render_template("economics/population.html", **context)


@economics_bp.route("/population/logs", methods=["GET"])
@login_required
def population_logs():
    """AJAX: журнал изменений численности населения для текущей версии БД."""
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", 150, type=int)
    vid = get_current_version()
    if limit == 0:
        total = count_population_logs(vid)
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
    rows = load_population_logs_raw(vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_population_logs(vid)
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


@economics_bp.route("/population/export.xlsx")
@login_required
def population_export_xlsx():
    rd = _parse_rounding_digits()
    page_kw = parse_population_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_population_page_context(**page_kw)
    stream = build_population_excel_stream(context)
    return send_file(
        stream,
        as_attachment=True,
        download_name="chislennost_naseleniya.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@economics_bp.route("/population/import.xlsx", methods=["POST"])
@login_required
def population_import_xlsx():
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
        stats = import_population_from_xlsx_bytes(raw)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Импорт численности населения из Excel")
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
    sheet_name = stats.get("sheet_name")
    if sheet_name:
        msg += f" Лист: «{sheet_name}»."
    years_ensured = stats.get("years_ensured") or 0
    if years_ensured:
        msg += f" Добавлено записей годов в справочник: {years_ensured}."
    db_versions = stats.get("database_versions") or 0
    if db_versions:
        msg += f" Данные записаны во все версии БД ({db_versions})."
    warnings = stats.get("warnings") or []
    if warnings:
        msg += f" Предупреждений: {len(warnings)}."
    hints = warnings[:20]
    return jsonify(ok=True, message=msg, hints=hints, **stats)


@economics_bp.route("/accum_monetary_income/", methods=["GET", "POST"])
@login_required
def accum_monetary_income():
    form = _csrf()
    rd = _parse_rounding_digits()

    if request.method == "POST":
        if not getattr(current_user, "has_admin", False):
            flash("Недостаточно прав для изменения данных.", "danger")
            return _redirect_preserving_query(
                "economics_bp.accum_monetary_income", rounding_digits=rd
            )
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return _redirect_preserving_query(
                "economics_bp.accum_monetary_income", rounding_digits=rd
            )
        try:
            updated, skipped = save_accum_monetary_income_from_post(request.form)
            db.session.commit()
            flash(f"Сохранено ячеек: {updated}. Пропущено: {skipped}.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"Ошибка сохранения: {exc}", "danger")
        return _redirect_preserving_query(
            "economics_bp.accum_monetary_income", rounding_digits=rd
        )

    page_kw = parse_accum_monetary_income_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_accum_monetary_income_page_context(**page_kw)
    context["form"] = form
    context["can_edit"] = getattr(current_user, "has_admin", False)
    vid = get_current_version()
    context["accum_monetary_income_logs_formatted"] = (
        load_formatted_accum_monetary_income_logs(vid, limit=50)
    )
    return render_template("economics/accum_monetary_income.html", **context)


@economics_bp.route("/accum_monetary_income/logs", methods=["GET"])
@login_required
def accum_monetary_income_logs():
    """AJAX: журнал изменений накопленных денежных доходов населения."""
    offset = request.args.get("offset", 0, type=int) or 0
    limit = request.args.get("limit", 150, type=int)
    vid = get_current_version()
    if limit == 0:
        total = count_accum_monetary_income_logs(vid)
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
    rows = load_accum_monetary_income_logs_raw(vid, limit=limit, offset=offset)
    formatted = format_logs_for_display(rows)
    total = count_accum_monetary_income_logs(vid)
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


@economics_bp.route("/accum_monetary_income/export.xlsx")
@login_required
def accum_monetary_income_export_xlsx():
    rd = _parse_rounding_digits()
    page_kw = parse_accum_monetary_income_page_kwargs(rounding_digits=rd)
    page_kw.pop("data_start_year", None)
    page_kw.pop("data_end_year", None)
    context = build_accum_monetary_income_page_context(**page_kw)
    stream = build_accum_monetary_income_excel_stream(context)
    return send_file(
        stream,
        as_attachment=True,
        download_name="nakoplennye_denezhnye_dohody_naseleniya.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@economics_bp.route("/accum_monetary_income/import.xlsx", methods=["POST"])
@login_required
def accum_monetary_income_import_xlsx():
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
        stats = import_accum_monetary_income_from_xlsx_bytes(raw)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Импорт накопленных денежных доходов населения из Excel"
        )
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
    sheet_name = stats.get("sheet_name")
    if sheet_name:
        msg += f" Лист: «{sheet_name}»."
    years_ensured = stats.get("years_ensured") or 0
    if years_ensured:
        msg += f" Добавлено записей годов в справочник: {years_ensured}."
    db_versions = stats.get("database_versions") or 0
    if db_versions:
        msg += f" Данные записаны во все версии БД ({db_versions})."
    warnings = stats.get("warnings") or []
    if warnings:
        msg += f" Предупреждений: {len(warnings)}."
    hints = warnings[:20]
    return jsonify(ok=True, message=msg, hints=hints, **stats)
