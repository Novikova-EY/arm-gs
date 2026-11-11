"""Адресный сброс настроек без изменения сессий авторизации и общего кеша."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from flask import current_app, request, session
from flask_login import current_user

from app.extensions import db
from app.auth.models.user_model import User
from app.logs.services.logging_service import log_to_db


_SESSION_SETTINGS = (
    "station_list_last_query_args",
    "generation_years_version_id",
    "external_code_check_filters",
)


def _reset_path(user_id: int) -> Path:
    return Path(current_app.instance_path) / "user_settings_resets" / f"{int(user_id)}.txt"


def get_settings_reset_token(user_id: int) -> str:
    try:
        return _reset_path(user_id).read_text(encoding="ascii")
    except FileNotFoundError:
        return ""


def reset_user_settings(actor, user_id: int) -> str:
    target = db.get_or_404(User, user_id)
    path = _reset_path(target.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Маркер вне кеша: общая очистка кеша не должна отменять отложенный сброс.
    temporary = NamedTemporaryFile(mode="w", encoding="ascii", dir=path.parent, delete=False)
    try:
        with temporary:
            temporary.write(uuid4().hex)
        os.replace(temporary.name, path)
    finally:
        Path(temporary.name).unlink(missing_ok=True)
    log_to_db(actor, "Сброс личных настроек пользователя", f"Пользователь: {target.username}")
    return target.username


def init_user_settings_reset(app):
    @app.before_request
    def apply_settings_reset():
        if request.endpoint == "static" or not current_user.is_authenticated:
            return
        token = get_settings_reset_token(current_user.id)
        if token and session.get("_settings_reset_token") != token:
            for key in _SESSION_SETTINGS:
                session.pop(key, None)
            session["_settings_reset_token"] = token

    @app.context_processor
    def settings_reset_context():
        if not current_user.is_authenticated:
            return {"user_settings_reset": None}
        return {"user_settings_reset": {
            "userId": str(current_user.id),
            "token": get_settings_reset_token(current_user.id),
        }}
