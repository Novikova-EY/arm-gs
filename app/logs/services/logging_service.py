# app/logs/services/logging_service.py

from __future__ import annotations
from typing import Any, Optional
from werkzeug.local import LocalProxy
from flask import current_app, has_app_context, g
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, DataError, DBAPIError
from app.extensions import db
from app.logs.models.log_model import Log

# Жесткие лимиты под типы колонок
MAX_USERNAME = 100
MAX_ACTION = 500
MAX_ENTITY_TYPE = 50

def _to_username(user: Any) -> Optional[str]:
    try:
        if user is None:
            return None
        if isinstance(user, str):
            return user
        if isinstance(user, LocalProxy):
            user = user._get_current_object()
        if hasattr(user, "username"):
            return str(getattr(user, "username"))
        return str(user)
    except Exception:
        return None

def _safe_trim(s: Optional[str], limit: int) -> str:
    if s is None:
        return ""
    s = str(s)
    return s if len(s) <= limit else (s[:limit-1] + "…")

def _make_independent_session():
    """
    Возвращает независимую сессию, связанную с тем же engine, что и db.session.
    Безопасный fallback для разных версий Flask-SQLAlchemy.
    """
    try:
        engine = db.get_engine() if hasattr(db, "get_engine") else db.engine
        Session = sessionmaker(bind=engine)
        session = Session()
        # Защита на случай, если внезапно вернули текущую scoped-сессию
        try:
            if session is db.session:
                session.close()
                session = Session()
        except Exception:
            pass
        return session
    except Exception as e:
        if has_app_context():
            current_app.logger.error(f"log_to_db: cannot create session: {e!r}")
        return None

def log_to_db(
    user: Any,
    action: str,
    details: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None
) -> None:
    session = None
    try:
        username = _safe_trim(_to_username(user) or "Неизвестный пользователь", MAX_USERNAME)
        safe_action = _safe_trim(action or "", MAX_ACTION)
        safe_entity_type = _safe_trim(entity_type, MAX_ENTITY_TYPE) if entity_type else None

        # details — Text, но на всякий случай приводим к строке
        if details is not None and not isinstance(details, str):
            details = str(details)

        # Создаем независимую сессию заранее — ее же используем для версии БД
        session = _make_independent_session()
        # Если создать независимую сессию не удалось — тихо выходим,
        # чтобы не коммитить основной db.session и не инвалидировать объекты
        if session is None:
            return

        # Эта сессия используется только для записи служебных логов.
        # Ее commit не должен триггерить очистку refdata-кэшей в listeners after_commit.
        try:
            session.info["_skip_refdata_cache_invalidation"] = True
        except Exception:
            pass

        # Получаем текущую версию БД, не трогая основной db.session (может быть в flush)
        database_version_id = None
        try:
            if has_app_context() and hasattr(g, "current_db_version"):
                database_version_id = g.current_db_version
            else:
                from app.common.models.database_version_model import DatabaseVersion
                active_version = session.query(DatabaseVersion).filter_by(is_active=True).first()
                database_version_id = active_version.id if active_version else None
        except Exception:
            # Если не удалось получить версию, продолжаем без нее
            pass

        rec = Log(
            username=username,
            action=safe_action,
            details=details,
            entity_type=safe_entity_type,
            entity_id=entity_id,
            database_version_id=database_version_id,
        )

        session.add(rec)
        session.commit()

    except (DataError, DBAPIError, SQLAlchemyError, Exception) as e:
        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
        try:
            if has_app_context():
                current_app.logger.warning(f"log_to_db error: {e!r}")
        except Exception:
            pass
        # Не пробрасываем исключение — логирование не должно валить основной поток
    finally:
        try:
            # Закрываем только если это НЕ db.session (иначе закроешь глобальную)
            if session is not None and session is not db.session:
                session.close()
        except Exception:
            pass
