from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError

from app.common.services.database_version_filter import get_current_db_version_id
from app.logs.services.logging_service import log_to_db
from app.extensions import db
from app.rational_structure.models import TerritoryTechnology
from app.rational_structure.services.territory_technology_matching import set_technology_references
from app.rational_structure.services.territory_technology_export_services import export_territory_technologies
from app.rational_structure.routes import rational_structure_module_bp
from app.rational_structure.services.territory_technology_services import build_territory_technology_context, import_territory_inputs


@rational_structure_module_bp.route("/territory_technologies")
@login_required
def territory_technologies():
    context = build_territory_technology_context(request.args, get_current_db_version_id())
    return render_template("rational_structure/territory_technologies.html", **context,
                           import_form=FlaskForm(), can_import=current_user.has_admin)


@rational_structure_module_bp.route("/territory_technologies/export")
@login_required
def export_territory_technologies_excel():
    version_id = get_current_db_version_id()
    if version_id is None:
        abort(400, "Выберите версию базы данных перед выгрузкой.")
    context = build_territory_technology_context(request.args, version_id)
    if context["version"] is None:
        abort(400, "Выбранная версия базы данных не найдена.")
    zone = context["selected_energy_zone"]
    territory = f"zone_{zone.number}" if zone else "all_zones"
    return send_file(export_territory_technologies(context), as_attachment=True,
                     download_name=f"territory_{context['sheet']}_{territory}_v{version_id}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@rational_structure_module_bp.route("/territory_technologies/<int:row_id>/references", methods=["POST"])
@login_required
def update_territory_technology_references(row_id):
    if not current_user.has_admin:
        abort(403)
    target = url_for("rational_structure_module_bp.territory_technologies")
    version_id = get_current_db_version_id()
    if not FlaskForm().validate_on_submit():
        flash("Не удалось проверить форму. Обновите страницу.", "danger")
        return redirect(target)
    if version_id is None or request.form.get("database_version_id") != str(version_id):
        flash("Версия БД изменилась. Обновите страницу.", "danger")
        return redirect(target)
    row = db.session.scalar(db.select(TerritoryTechnology).where(
        TerritoryTechnology.id == row_id, TerritoryTechnology.database_version_id == version_id,
    ).with_for_update())
    if row is None:
        abort(404)
    try:
        set_technology_references(row, request.form, version_id)
        row.references_manual = True
        row.modified_by = current_user.username
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(target)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Ошибка сохранения справочников технологии")
        flash("Не удалось сохранить связи со справочниками.", "danger")
        return redirect(target)
    log_to_db(current_user.username, "Изменение справочников технологии",
              f"Версия БД id={version_id}; технология id={row_id}", entity_type="rational_structure")
    flash("Связи со справочниками сохранены. Исходное название из Excel сохранено.", "success")
    return redirect(target)


@rational_structure_module_bp.route("/territory_technologies/import", methods=["POST"])
@login_required
def import_territory_technologies():
    if not current_user.has_admin:
        abort(403)
    target = url_for("rational_structure_module_bp.territory_technologies")
    if not FlaskForm().validate_on_submit():
        flash("Не удалось проверить форму. Обновите страницу и повторите загрузку.", "danger")
        return redirect(target)
    version_id = get_current_db_version_id()
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
        counts = import_territory_inputs(raw, version_id, current_user.username, upload.filename)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(target)
    except SQLAlchemyError:
        current_app.logger.exception("Ошибка импорта исходных данных по территориям")
        flash("Данные не загружены из-за ошибки базы данных.", "danger")
        return redirect(target)
    log_to_db(current_user.username, "Импорт исходных данных по территориям",
              f"Версия БД id={version_id}; {upload.filename}: {counts}", entity_type="rational_structure")
    flash(f"Загружено технологий: {counts['technologies']}, сечений: {counts['sections']}. "
          f"Добавлено: {counts['created']}, обновлено: {counts['updated']}.", "success")
    return redirect(target)
