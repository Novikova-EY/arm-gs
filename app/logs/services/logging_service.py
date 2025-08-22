# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Optional

from werkzeug.local import LocalProxy
from app.extensions import db
from app.logs.models.log_model import Log  # ваша модель лога

def _to_username(user: Any) -> Optional[str]:
    """
    Преобразует что угодно в строковый username.
    Поддерживает werkzeug.LocalProxy (current_user), ORM-модели с атрибутом .username и обычные строки.
    """
    try:
        if user is None:
            return None
        if isinstance(user, str):
            return user
        if isinstance(user, LocalProxy):
            user = user._get_current_object()
        # Модель пользователя с атрибутом username
        if hasattr(user, "username"):
            return str(getattr(user, "username"))
        # На крайний случай
        return str(user)
    except Exception:
        return None

def log_to_db(user: Any, action: str, details: Optional[str] = None) -> None:
    """
    Безопасная запись лога:
    - username приводим к строке
    - details приводим к строке при необходимости
    - при ошибке — rollback и тихий выход (не ломаем основной поток)
    """
    try:
        username = _to_username(user)
        if details is not None and not isinstance(details, str):
            details = str(details)

        rec = Log(username=username, action=action, details=details)
        db.session.add(rec)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Не выбрасываем исключение дальше, чтобы логирование не падало страницей.
        # При желании можно добавить print/лог в stdout.
        return
