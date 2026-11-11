from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from redis.exceptions import RedisError

from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.routes import fuel_bp
from app.fuel.services.fuel_imports.fuel_db_import_jobs import (
    get_active_fuel_db_import_job,
    get_fuel_db_import_job,
    start_fuel_db_import_job,
)
from app.logs.services.logging_service import log_to_db


def _wants_json():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"


def _public_job(job):
    if job is None:
        return None
    return {
        key: value for key, value in job.items() if key not in ("owner_id", "username")
    } | {"status_url": url_for("fuel_bp.fuel_db_import_status", job_id=job["id"])}


def start_fuel_db_import(redirect_endpoint, redirect_args):
    redirect_url = url_for(redirect_endpoint, **redirect_args)

    def reject(message, status=400):
        if _wants_json():
            return jsonify(ok=False, error=message), status
        flash(message, "danger")
        return redirect(redirect_url)

    if not FlaskForm().validate_on_submit():
        return reject("Не удалось проверить форму. Обновите страницу и повторите загрузку.")
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return reject("Файл не найден.")
    if upload.mimetype not in (
        "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ) or not upload.filename.lower().endswith((".xlsx", ".xls")):
        return reject("Неверный формат файла. Выберите Excel (.xlsx или .xls).")
    version_id = get_current_db_version_id()
    if version_id is None or version_id <= 0:
        return reject("Перед импортом выберите версию базы данных.")
    username = session.get("username") or current_user.username
    try:
        job = start_fuel_db_import_job(
            current_app._get_current_object(), upload, owner_id=current_user.get_id(),
            username=username, version_id=version_id, redirect_url=redirect_url,
        )
    except ValueError as exc:
        return reject(str(exc), 409)
    except (RedisError, OSError, RuntimeError):
        current_app.logger.exception("Не удалось запустить фоновый импорт БД Топливо")
        return reject("Не удалось запустить импорт. Проверьте Redis и доступность каталога загрузки.", 503)
    log_to_db(username, "Начата загрузка данных БД Топливо", details=f"job_id={job['id']}; filename={job['filename']}")
    if _wants_json():
        return jsonify(ok=True, job=_public_job(job)), 202
    return redirect(url_for("fuel_bp.fuel_db_import_status", job_id=job["id"]))


@fuel_bp.route("/stations_equipment_groups/import_fuel_db/status/<job_id>")
@login_required
def fuel_db_import_status(job_id):
    try:
        job = get_fuel_db_import_job(job_id, current_user.get_id())
    except RedisError:
        return jsonify(ok=False, error="Статус импорта временно недоступен. Проверка будет повторена."), 503
    if job is None:
        abort(404)
    if _wants_json():
        response = jsonify(ok=True, job=_public_job(job))
    else:
        response = current_app.make_response(render_template("fuel/import_fuel_db_status.html", job=_public_job(job)))
    response.cache_control.no_store = True
    return response


@fuel_bp.route("/stations_equipment_groups/import_fuel_db/active")
@login_required
def fuel_db_import_active():
    try:
        job = get_active_fuel_db_import_job(current_user.get_id())
    except RedisError:
        return jsonify(ok=False, error="Сервис фонового импорта временно недоступен."), 503
    response = jsonify(ok=True, job=_public_job(job))
    response.cache_control.no_store = True
    return response
