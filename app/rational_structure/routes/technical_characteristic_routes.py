from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy.exc import SQLAlchemyError

from app.common.services.database_version_filter import get_current_db_version_id
from app.logs.services.logging_service import log_to_db
from app.rational_structure.routes import rational_structure_module_bp
from app.rational_structure.equipment_types import DEFAULT_PAGE, EQUIPMENT_TYPES, MATCHABLE_TYPES, PAGES
from app.rational_structure.services.technical_characteristic_export_services import export_technical_characteristics
from app.rational_structure.services.technical_characteristic_import_services import import_technical_characteristics
from app.rational_structure.services.technical_characteristic_page_services import build_technical_characteristic_context
from app.rational_structure.services.technical_characteristic_machine_services import (
    get_machine_station_id, get_machine_technical_inspection_codes, get_pgu_machine_technical_inspection_codes,
)
from app.rational_structure.services.technical_inspection_code_services import TechnicalInspectionCodes
from app.rational_structure.models import TurbineTechnicalCharacteristic
from app.generation.models.machine.machine_model import Machine
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.extensions import db


@rational_structure_module_bp.route("/")
@login_required
def hub():
    return render_template("rational_structure/rational_structure_start.html")


@rational_structure_module_bp.route(
    "/technical_characteristics/hydro", endpoint="hydro_technical_characteristics", defaults={"page_key": "hydro"},
)
@rational_structure_module_bp.route(
    "/technical_characteristics/boilers/energy", endpoint="energy_boiler_technical_characteristics", defaults={"page_key": "boiler_energy"},
)
@rational_structure_module_bp.route(
    "/technical_characteristics/boilers/water", endpoint="water_boiler_technical_characteristics", defaults={"page_key": "boiler_water"},
)
@rational_structure_module_bp.route("/technical_characteristics", defaults={"page_key": DEFAULT_PAGE})
@login_required
def technical_characteristics(page_key):
    context = build_technical_characteristic_context(request.args, get_current_db_version_id(), page_key=page_key)
    return render_template("rational_structure/technical_characteristics.html", **context, import_form=FlaskForm(), can_import=current_user.has_admin)


@rational_structure_module_bp.route("/technical_characteristics/export")
@login_required
def export_technical_characteristics_excel():
    page_key = request.args.get("section", DEFAULT_PAGE)
    if page_key not in PAGES:
        abort(400)
    context = build_technical_characteristic_context(request.args, get_current_db_version_id(), page_key=page_key)
    return send_file(
        export_technical_characteristics(context),
        as_attachment=True,
        download_name="technical_characteristics.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@rational_structure_module_bp.route("/technical_characteristics/import", methods=["POST"])
@login_required
def import_technical_characteristics_excel():
    if not current_user.has_admin:
        abort(403)
    report_year = request.form.get("year", type=int)
    page_key = request.form.get("section", DEFAULT_PAGE)
    if page_key not in PAGES:
        abort(400)
    target = url_for(PAGES[page_key]["endpoint"], year=report_year)
    form = FlaskForm()
    if not form.validate_on_submit():
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
        counts = import_technical_characteristics(raw, get_current_db_version_id(), current_user.username)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(target)
    except SQLAlchemyError:
        current_app.logger.exception("Ошибка импорта технических характеристик турбин")
        flash("Данные не загружены. Ошибка базы данных, подробности в журнале сервера.", "danger")
        return redirect(target)
    log_to_db(current_user.username, "Импорт технических характеристик оборудования", f"{upload.filename}, все годы файла: {counts}", entity_type="rational_structure")
    summary = ", ".join(f"{label}: {counts.get(kind, 0)}" for kind, label in EQUIPMENT_TYPES.items())
    flash(f"Загрузка за все годы файла завершена. Добавлено: {counts['created']}, обновлено: {counts['updated']}. {summary}.", "success")
    return redirect(target)


@rational_structure_module_bp.route("/technical_characteristics/save_machine_id", methods=["PATCH"])
@login_required
def save_machine_id():
    """Сохранение ID агрегата для записи технических характеристик."""
    if not request.is_json:
        return jsonify({"ok": False, "error": "Ожидается JSON"}), 400

    data = request.get_json()
    turbine_id = data.get("turbine_id")
    machine_id = data.get("machine_id")
    station_id = data.get("station_id")

    if turbine_id is None:
        return jsonify({"ok": False, "error": "Не указан ID записи"}), 400

    version_id = get_current_db_version_id()
    if version_id is None:
        return jsonify({"ok": False, "error": "Не выбрана версия БД"}), 400

    try:
        turbine = TurbineTechnicalCharacteristic.query.filter_by(
            id=turbine_id, database_version_id=version_id
        ).first()
        if not turbine:
            return jsonify({"ok": False, "error": "Запись не найдена"}), 404
        if turbine.equipment_type not in MATCHABLE_TYPES:
            return jsonify({"ok": False, "error": "Сопоставление с агрегатом недоступно для котлов"}), 400

        raw_id = str(machine_id).strip() if machine_id else ""
        new_machine_id = None
        new_pgu_machine_id = None
        if raw_id:
            if "/" in raw_id:
                parts = [part.strip() for part in raw_id.split("/")]
                if len(parts) != 2 or not all(part.isdigit() for part in parts):
                    return jsonify({"ok": False, "error": "ID агрегата вводится как \"ID агрегата/ID составляющей ПГУ\""}), 400
                new_machine_id = int(parts[0])
                new_pgu_machine_id = int(parts[1])
            elif raw_id.isdigit():
                new_machine_id = int(raw_id)
            else:
                return jsonify({"ok": False, "error": "ID агрегата должен быть числом или парой через дробь"}), 400

        # Проверяем, что агрегат существует и принадлежит к указанной станции
        if new_machine_id is not None:
            machine = Machine.query.filter_by(
                id=new_machine_id, database_version_id=version_id
            ).first()
            if not machine:
                return jsonify({"ok": False, "error": "Агрегат не найден в текущей версии БД"}), 404
            if station_id and machine.id_station != int(station_id):
                return jsonify({"ok": False, "error": "Агрегат не принадлежит к указанной станции"}), 400

        if new_pgu_machine_id is not None:
            pgu_machine = PGUMachine.query.filter_by(
                id=new_pgu_machine_id, database_version_id=version_id
            ).first()
            if not pgu_machine:
                return jsonify({"ok": False, "error": "Компонент ПГУ не найден в текущей версии БД"}), 404
            if pgu_machine.id_parent_machine != new_machine_id:
                return jsonify({"ok": False, "error": "Компонент ПГУ не принадлежит указанному агрегату"}), 400

        codes = TechnicalInspectionCodes()
        if new_machine_id is not None:
            codes.remember(turbine.equipment_code, new_machine_id, new_pgu_machine_id,
                           current_user.username, replace=True, sync_characteristics=True)
        elif turbine.machine_id is not None:
            codes.change_code(turbine.equipment_code, "", turbine.machine_id,
                              turbine.pgu_machine_id, current_user.username)
        turbine.machine_id = new_machine_id
        turbine.pgu_machine_id = new_pgu_machine_id
        turbine.match_status = "matched" if new_machine_id is not None else "not_checked"
        turbine.match_details = {}
        db.session.commit()

        # Возвращаем обновленный статус
        return jsonify({
            "ok": True,
            "machine_id": new_machine_id,
            "pgu_machine_id": new_pgu_machine_id,
            "match_status": turbine.match_status,
        })
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Ошибка сохранения ID агрегата")
        return jsonify({"ok": False, "error": "Ошибка базы данных"}), 500


@rational_structure_module_bp.route("/technical_characteristics/save_technical_inspection_code", methods=["PATCH"])
@login_required
def save_technical_inspection_code():
    """Сохранение кода Техинспекции для агрегата."""
    if not request.is_json:
        return jsonify({"ok": False, "error": "Ожидается JSON"}), 400

    data = request.get_json()
    machine_id = data.get("machine_id")
    pgu_machine_id = data.get("pgu_machine_id")
    equipment_code = data.get("equipment_code") or ""
    if not isinstance(equipment_code, str) or len(equipment_code.strip()) > 100:
        return jsonify({"ok": False, "error": "Код Техинспекции должен содержать не более 100 символов"}), 400
    equipment_code = equipment_code.strip()

    if machine_id is None and pgu_machine_id is None:
        return jsonify({"ok": False, "error": "Не указан ID агрегата"}), 400

    version_id = get_current_db_version_id()
    if version_id is None:
        return jsonify({"ok": False, "error": "Не выбрана версия БД"}), 400

    try:
        if pgu_machine_id is not None:
            pgu_machine = PGUMachine.query.filter_by(
                id=pgu_machine_id, database_version_id=version_id
            ).first()
            if not pgu_machine:
                return jsonify({"ok": False, "error": "Компонент ПГУ не найден в текущей версии БД"}), 404
            machine_id = pgu_machine.id_parent_machine
            pgu_machine_id = pgu_machine.id
            existing_codes = get_pgu_machine_technical_inspection_codes(pgu_machine_id, version_id)
        else:
            machine = Machine.query.filter_by(
                id=machine_id, database_version_id=version_id
            ).first()
            if not machine:
                return jsonify({"ok": False, "error": "Агрегат не найден в текущей версии БД"}), 404
            machine_id = machine.id
            existing_codes = get_machine_technical_inspection_codes(machine_id, version_id)

        old_code = data.get("previous_code")
        if old_code is None:
            old_code = existing_codes[0] if len(existing_codes) == 1 else None
        if old_code and old_code not in existing_codes:
            return jsonify({"ok": False, "error": "Исходный код не связан с этим агрегатом"}), 400
        TechnicalInspectionCodes().change_code(old_code, equipment_code, machine_id,
                                               pgu_machine_id, current_user.username)
        db.session.commit()
        return jsonify({"ok": True, "equipment_code": equipment_code})
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Ошибка сохранения кода Техинспекции")
        return jsonify({"ok": False, "error": "Ошибка базы данных"}), 500
