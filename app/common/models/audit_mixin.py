# -*- coding: utf-8 -*-
"""
Миксин для автоматического заполнения полей created_by и modified_by.

Используется в моделях refdata, чтобы хранить пользователя,
создавшего и изменившего запись.
"""

from typing import Optional

from sqlalchemy import event
from app.extensions import db


class AuditMixin:
    """
    Миксин для добавления полей аудита в модели.

    Поля:
    - created_by: Пользователь, создавший запись
    - modified_by: Пользователь, последним изменивший запись
    """

    created_by = db.Column(db.String(255), nullable=True)
    modified_by = db.Column(db.String(255), nullable=True)


def _get_current_username() -> str:
    """
    Пытаемся получить имя текущего пользователя.

    Приоритет:
    1) flask_login.current_user.username / email
    2) session['username']
    3) 'Неизвестный пользователь'
    """
    from flask import session, has_request_context

    if not has_request_context():
        return "Неизвестный пользователь"

    try:
        from flask_login import current_user

        if current_user and current_user.is_authenticated:
            # Пытаемся использовать username, иначе email
            username = getattr(current_user, "username", None) or getattr(
                current_user, "email", None
            )
            if username:
                return str(username)
    except Exception:
        # Любые ошибки при обращении к current_user игнорируем
        pass

    return session.get("username", "Неизвестный пользователь")


@event.listens_for(AuditMixin, "before_insert", propagate=True)
def _set_created_by(mapper, connection, target):
    """
    Перед вставкой:
    - устанавливаем created_by, если оно ещё не задано.
    - modified_by трогать не обязательно (останется NULL).
    """
    if hasattr(target, "created_by") and not getattr(target, "created_by", None):
        setattr(target, "created_by", _get_current_username())


@event.listens_for(AuditMixin, "before_update", propagate=True)
def _set_modified_by(mapper, connection, target):
    """
    Перед обновлением:
    - всегда обновляем modified_by на текущего пользователя.

    Это синхронизировано с обновлением поля updated_at (modified_at),
    которое у моделей refdata обновляется через onupdate=func.now().
    """
    if hasattr(target, "modified_by"):
        setattr(target, "modified_by", _get_current_username())


