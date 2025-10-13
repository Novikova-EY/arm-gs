"""Сервисный модуль: Common tranzaction services."""

from app.extensions import db
from sqlalchemy.exc import OperationalError
from functools import wraps
import time
from sqlalchemy import text


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


def quick_fix_seq(schema: str, table: str, col: str = "id"):
    """
    Быстро выравнивает sequence под MAX(id) для указанной таблицы.
    """
    with db.engine.begin() as conn:
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:tbl, :col)"),
            {"tbl": f"{schema}.{table}", "col": col}
        ).scalar()
        if not seq:
            return
        max_id = conn.execute(
            text(f"SELECT COALESCE(MAX({col}), 0) FROM {schema}.{table}")
        ).scalar()

        conn.execute(
            text(f"SELECT setval('{seq}', {int(max_id)}, true)")
        )