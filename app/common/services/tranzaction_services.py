"""Сервисный модуль: Common tranzaction services."""

from app.extensions import db
from sqlalchemy.exc import OperationalError
from functools import wraps
import time
from sqlalchemy import text
from contextlib import nullcontext
import types


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
    query = db.session.query(model).filter_by(id=id_)
    try:
        from app.common.services.database_version_filter import filter_by_db_version
        query = filter_by_db_version(query, model)
    except Exception:
        pass
    return query.with_for_update().one_or_none()


def no_autoflush(func):
    """Декоратор: выполняет функцию в контексте no_autoflush для ускорения массовых операций."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Получаем db, которым пользуется целевая функция (важно для тестов, где патчатся локальные сессии)
        service_db = func.__globals__.get("db", db)
        session = getattr(service_db, "session", None)

        # Готовим корректный контекст-менеджер для no_autoflush
        current_ctx = getattr(session, "no_autoflush", None) if session else None
        need_temp_ctx = (
            current_ctx is None
            or not hasattr(current_ctx, "__enter__")
            or isinstance(current_ctx, types.SimpleNamespace)
        )
        temp_ctx = nullcontext()

        # Если у сессии нет корректного no_autoflush — временно подменяем
        if session and need_temp_ctx:
            try:
                setattr(session, "no_autoflush", temp_ctx)
            except Exception:
                pass
        # Подстрахуемся: если сессия не вызываема как scoped_session(), добавим __call__
        if session and not callable(getattr(session, "__call__", None)):
            try:
                setattr(session, "__call__", lambda *a, **k: session)
            except Exception:
                pass
        # Если нет execute (ORM first() может его дергать), заглушим
        if session and not hasattr(session, "execute"):
            try:
                setattr(session, "execute", lambda *a, **k: None)
            except Exception:
                pass

        try:
            with (getattr(session, "no_autoflush", temp_ctx) or temp_ctx):
                return func(*args, **kwargs)
        finally:
            # Возвращаем назад исходное значение
            if session and need_temp_ctx:
                try:
                    setattr(session, "no_autoflush", current_ctx)
                except Exception:
                    pass
    return wrapper


def quick_fix_seq(schema: str, table: str, col: str = "id"):
    """
    Быстро выравнивает sequence под MAX(id) для указанной таблицы.

    Sequence никогда не уменьшается: в длинной транзакции (например, сохранение
    machine_details во всех версиях БД) уже выданные, но ещё не закоммиченные id
    не видны в MAX(id), и откат sequence приводил к UniqueViolation по PK.
    """
    with db.engine.begin() as conn:
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:tbl, :col)"),
            {"tbl": f"{schema}.{table}", "col": col},
        ).scalar()
        if not seq:
            return
        max_id = conn.execute(
            text(f"SELECT COALESCE(MAX({col}), 0) FROM {schema}.{table}")
        ).scalar()
        mid = int(max_id)

        seq_state = conn.execute(
            text(f"SELECT last_value, is_called FROM {seq}")
        ).fetchone()
        if not seq_state:
            return
        last_value, is_called = int(seq_state[0]), bool(seq_state[1])
        seq_next = last_value + 1 if is_called else last_value

        if mid <= 0:
            target_next = max(1, seq_next)
        else:
            target_next = max(mid + 1, seq_next)

        conn.execute(
            text(f"SELECT setval('{seq}', :target_next, false)"),
            {"target_next": target_next},
        )


def quick_fix_machine_details_related_seqs() -> None:
    """Выравнивает sequences таблиц, которые создаются при сохранении machine_details."""
    from config import SCHEMA_FUEL, SCHEMA_GENERATION

    for schema, table in (
        (SCHEMA_GENERATION, "gs_gen_machines"),
        (SCHEMA_GENERATION, "gs_gen_machine_powers"),
        (SCHEMA_GENERATION, "gs_gen_machine_fuels"),
        (SCHEMA_GENERATION, "gs_gen_machine_tes_types"),
        (SCHEMA_GENERATION, "gs_gen_machine_names"),
        (SCHEMA_FUEL, "gs_fue_equipment_groups"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_sets"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"),
    ):
        try:
            quick_fix_seq(schema, table, "id")
        except Exception:
            pass