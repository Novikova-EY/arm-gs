"""Сервисный модуль: Common tranzaction services."""

from app.extensions import db
from sqlalchemy.exc import OperationalError
from functools import wraps
import time


def _commit_with_retry(tries: int = 3, delay: float = 0.05) -> None:
    """Коммит с повтором при временных ошибках блокировок."""
    for attempt in range(tries):
        try:
            db.session.commit()
            return
        except OperationalError as e:
            db.session.rollback()
            if attempt >= tries - 1:
                raise
            time.sleep(delay * (attempt + 1))
        except Exception:
            db.session.rollback()
            raise


def _locked_get(model, id_):
    """Безопасное получение записи с блокировкой строки под обновление."""
    return db.session.query(model).filter_by(id=id_).with_for_update().one_or_none()


def no_autoflush(func):
    """Декоратор: выполняет функцию в контексте no_autoflush для ускорения массовых операций."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with db.session.no_autoflush:
            return func(*args, **kwargs)
    return wrapper

    """Коммит с повтором при временных ошибках блокировок.
    :param tries: число попыток
    :param delay: базовая задержка между попытками (увеличивается линейно)
    """
    for attempt in range(tries):
        try:
            # --- Фиксация транзакции (устойчивый коммит) ---

            _commit_with_retry()
            return
        except OperationalError as e:
            # Откатываем транзакцию и пробуем еще раз (deadlock/timeout и т.п.)
            db.session.rollback()
            if attempt >= tries - 1:
                raise
            time.sleep(delay * (attempt + 1))
        except Exception:
            # Любая другая ошибка — просто пробрасываем дальше после отката
            db.session.rollback()
            raise