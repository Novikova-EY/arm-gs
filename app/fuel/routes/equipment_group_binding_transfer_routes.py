"""Two-step equipment-group binding transfer for the station/group catalog."""
from flask import abort, current_app, jsonify, render_template, request, send_file, session
from flask_login import current_user, login_required
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.services.station_services.aggregation_cache import clear_aggregation_cache
from app.fuel.services.equipment_groups.equipment_group_binding_transfer_services import (
    TransferPlan, apply_transfer_plan, load_transfer_snapshot, snapshot_fingerprint, validate_transfer_versions,
)
from app.fuel.services.equipment_groups.equipment_group_binding_transfer_export_services import export_binding_transfer_report
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from . import fuel_bp


def _signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="equipment-group-binding-transfer")


@fuel_bp.get("/stations_equipment_groups/binding_transfer/page")
@login_required
def equipment_group_binding_transfer_page():
    if not current_user.is_admin:
        abort(403)
    return render_template("fuel/equipment_groups/binding_transfer.html", csrf_token=session.get("csrf_token", ""))


@fuel_bp.route("/stations_equipment_groups/binding_transfer", methods=["GET", "POST"])
@login_required
def equipment_group_binding_transfer():
    if not current_user.is_admin:
        return jsonify(success=False, message="Недостаточно прав для переноса связей."), 403
    target = get_current_db_version_id()
    if type(target) is not int or target <= 0:
        return jsonify(success=False, message="Сначала выберите текущую версию базы данных."), 400
    data = request.get_json(silent=True) if request.method == "POST" else None
    if request.method == "POST":
        if not isinstance(data, dict):
            return jsonify(success=False, message="Ожидается JSON с параметрами переноса."), 400
        if not session.get("csrf_token") or not _csrf_ok():
            return jsonify(success=False, message="Ошибка проверки CSRF. Обновите страницу."), 400
    if data and data.get("action") == "report":
        try:
            output = export_binding_transfer_report(data.get("report"))
        except ValueError as exc:
            return jsonify(success=False, message=str(exc)), 400
        response = send_file(output, as_attachment=True, download_name="equipment_group_binding_transfer.xlsx",
                             mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response.headers["Cache-Control"] = "no-store"
        return response
    versions = {r.id: r.version_number for r in db.session.execute(
        select(DatabaseVersion.id, DatabaseVersion.version_number).where(DatabaseVersion.id > 0).order_by(DatabaseVersion.id)
    )}
    if target not in versions:
        return jsonify(success=False, message="Текущая версия базы данных не найдена."), 400
    if request.method == "GET":
        return jsonify(success=True, target={"id": target, "name": versions[target]},
                       sources=[{"id": key, "name": value} for key, value in versions.items() if key != target],
                       versions=[{"id": key, "name": value} for key, value in versions.items()])
    action = data.get("action")
    if action not in ("preview", "apply"):
        return jsonify(success=False, message="Неизвестное действие."), 400
    try:
        if action == "preview":
            explicit_target = "destination_version_id" in data
            if explicit_target:
                target = data["destination_version_id"]
                if type(target) is not int or target not in versions:
                    raise ValueError("Выберите существующую целевую версию.")
            elif type(data.get("target_version_id")) is not int or data["target_version_id"] != target:
                return jsonify(success=False, message="Текущая версия изменилась. Обновите страницу и повторите анализ."), 409
            group_id = data.get("group_id")
            if group_id is not None and (type(group_id) is not int or group_id <= 0):
                raise ValueError("Некорректная исходная группа.")
            source = data.get("source_version_id")
            create_missing = data.get("create_missing", False)
            if type(source) is not int or source not in versions or source == target or type(create_missing) is not bool:
                raise ValueError("Выберите другую версию-источник и корректные параметры.")
            validate_transfer_versions(source, target)
            snapshot = load_transfer_snapshot(source, target)
            plan = TransferPlan(snapshot, source, target, create_missing, group_id=group_id).build()
            token = _signer().dumps({"user": str(current_user.get_id()), "source": source, "target": target,
                                     "explicit_target": explicit_target, "group_id": group_id,
                                     "create_missing": create_missing, "fingerprint": snapshot_fingerprint(snapshot)})
            return jsonify(success=True, plan=plan.public(), token=token)
        token = data.get("token")
        keys = data.get("keys")
        if not isinstance(token, str) or not isinstance(keys, list) or len(keys) > 50000 or any(not isinstance(k, str) for k in keys):
            raise ValueError("Некорректный план переноса.")
        signed = _signer().loads(token)
        validate_transfer_versions(signed["source"], signed["target"])
        if signed.get("explicit_target"):
            target = signed["target"]
            if target not in versions:
                raise ValueError("Целевая версия больше недоступна.")
        if signed["user"] != str(current_user.get_id()) or signed["target"] != target:
            return jsonify(success=False, message="Пользователь или текущая версия изменились. Повторите анализ."), 409
        source = signed["source"]
        if source not in versions or source == target:
            raise ValueError("Исходная версия больше недоступна.")
        snapshot = load_transfer_snapshot(source, target, lock=True)
        if signed["fingerprint"] != snapshot_fingerprint(snapshot):
            db.session.rollback()
            return jsonify(success=False, message="После анализа данные изменились. Повторите анализ, ничего не перенесено."), 409
        plan = TransferPlan(snapshot, source, target, signed["create_missing"], group_id=signed.get("group_id")).build()
        result = apply_transfer_plan(plan, keys, current_user.username)
    except BadSignature:
        db.session.rollback()
        return jsonify(success=False, message="Подпись плана недействительна. Повторите анализ."), 409
    except ValueError as exc:
        db.session.rollback()
        return jsonify(success=False, message=str(exc)), 400
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Equipment-group binding transfer failed")
        return jsonify(success=False, message="Не удалось выполнить перенос. Изменения отменены. Повторите анализ и попытку."), 500
    try:
        clear_aggregation_cache()
    except Exception:
        # The transfer is committed; a cache failure must not be reported as a rollback.
        current_app.logger.exception("Bindings transferred, but station cache invalidation failed")
    return jsonify(success=True, result=result)
