from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime, import_equipment_runtime

from app.common.services.database_version_filter import get_current_db_version_id
from app.rational_structure.routes import rational_structure_module_bp
from app.rational_structure.services.equipment_runtime_services import build_equipment_runtime_context


@rational_structure_module_bp.route("/equipment_runtime")
@login_required
def equipment_runtime():
    context = build_equipment_runtime_context(request.args, get_current_db_version_id())
    return render_template("rational_structure/equipment_runtime.html", **context)


@rational_structure_module_bp.route("/equipment_runtime/export")
@login_required
def export_equipment_runtime_excel():
    context = build_equipment_runtime_context(request.args, get_current_db_version_id())
    return send_file(export_equipment_runtime(context), as_attachment=True,
                     download_name="equipment_runtime.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@rational_structure_module_bp.route("/equipment_runtime/import", methods=["POST"])
@login_required
def import_equipment_runtime_excel():
    if not current_user.has_admin:
        abort(403)
    target = url_for("rational_structure_module_bp.equipment_runtime")
    if not FlaskForm().validate_on_submit():
        flash("Не удалось проверить форму. Обновите страницу и повторите загрузку.", "danger")
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
        count = import_equipment_runtime(raw, get_current_db_version_id(), upload.filename, current_user.username)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(target)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Ошибка импорта расчета наработки оборудования")
        flash("Данные не загружены. Ошибка базы данных, подробности в журнале сервера.", "danger")
        return redirect(target)
    log_to_db(current_user.username, "Импорт расчета наработки оборудования",
              f"{upload.filename}: {count} записей", entity_type="rational_structure")
    flash(f"Книга сохранена в архиве. Записей оборудования: {count}. Расчет использует только данные приложения.", "success")
    return redirect(target)
