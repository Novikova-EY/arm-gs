from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError

from app.common.services.database_version_filter import get_current_db_version_id
from app.rational_structure.routes import rational_structure_module_bp
from app.logs.services.logging_service import log_to_db
from app.rational_structure.services.calculation_workbook_services import load_calculation_context
from app.rational_structure.services.marginal_price_excel_services import export_marginal_price_workbook
from app.rational_structure.services.marginal_price_services import (
    build_marginal_price_context, import_marginal_price_workbook,
)


@rational_structure_module_bp.route("/marginal_price")
@login_required
def marginal_price():
    context = build_marginal_price_context(request.args, get_current_db_version_id())
    return render_template("rational_structure/marginal_price.html", **context,
                           import_form=FlaskForm(), can_import=current_user.has_admin)


@rational_structure_module_bp.route("/marginal_price/export")
@login_required
def export_marginal_price_excel():
    context = load_calculation_context(get_current_db_version_id(), "marginal_price")
    if context["version"] is None:
        abort(400, "Выберите версию базы данных перед выгрузкой.")
    if context["workbook"] is None:
        abort(400, "В выбранной версии БД расчетная книга пока не загружена.")
    return send_file(export_marginal_price_workbook(context["workbook"]), as_attachment=True,
                     download_name=f"marginal_price_v{context['version_id']}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@rational_structure_module_bp.route("/marginal_price/import", methods=["POST"])
@login_required
def import_marginal_price_excel():
    if not current_user.has_admin:
        abort(403)
    target = url_for("rational_structure_module_bp.marginal_price")
    if not FlaskForm().validate_on_submit():
        flash("Не удалось проверить форму. Обновите страницу и повторите загрузку.", "danger")
        return redirect(target)
    version_id = get_current_db_version_id()
    if version_id is None:
        flash("Выберите версию базы данных перед загрузкой.", "danger")
        return redirect(target)
    if request.form.get("database_version_id") != str(version_id):
        flash("Версия БД изменилась. Обновите страницу перед загрузкой.", "danger")
        return redirect(target)
    upload = request.files.get("file")
    if upload is None or not upload.filename or not upload.filename.lower().endswith(".xlsx"):
        flash("Выберите книгу Excel в формате .xlsx.", "danger")
        return redirect(target)
    raw = upload.read(30 * 1024 * 1024 + 1)
    if not raw or len(raw) > 30 * 1024 * 1024:
        flash("Файл пуст или превышает 30 МБ.", "danger")
        return redirect(target)
    try:
        counts = import_marginal_price_workbook(raw, version_id, current_user.username, upload.filename)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(target)
    except SQLAlchemyError:
        current_app.logger.exception("Ошибка импорта расчета замыкающей цены")
        flash("Данные не загружены из-за ошибки базы данных.", "danger")
        return redirect(target)
    log_to_db(current_user.username, "Импорт расчета замыкающей цены",
              f"Версия БД id={version_id}; {upload.filename}: {counts}", entity_type="rational_structure")
    flash(f"Данные сохранены. Территорий: {counts['territories']}, строк: {counts['rows']}.", "success")
    if counts["errors"]:
        flash(f"В книге ячеек с ошибками Excel или без сохраненного результата: {counts['errors']}. "
              "Они сохранены и выделены в таблицах.", "warning")
    return redirect(target)
