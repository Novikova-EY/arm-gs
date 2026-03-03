"""
Исправляет orphan-ревизию в alembic_version.
Когда БД ссылается на ревизию (например d3241f809ea6), которой нет в коде,
Alembic не может запуститься. Скрипт оставляет в alembic_version одну запись — head.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config import Config

# Ревизия head (см. flask db heads). При нескольких heads — заменить на нужную.
HEAD_REVISION = "1e1fdaf90b94"


def fix_alembic_version():
    """Приводит gs_auth.alembic_version к одной записи — head."""
    db_url = Config.SQLALCHEMY_DATABASE_URI
    if not db_url:
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASSWORD") or os.getenv("DB_PASS")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_driver = os.getenv("DB_DRIVER", "psycopg2")
        if not all([db_user, db_pass, db_name]):
            print("Ошибка: Не заданы DB_USER, DB_PASSWORD, DB_NAME")
            sys.exit(1)
        db_url = f"postgresql+{db_driver}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    schema = getattr(Config, "SCHEMA_AUTH", "gs_auth")
    table = f'"{schema}".alembic_version'

    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"DELETE FROM {table}"))
            conn.execute(
                text(f"INSERT INTO {table} (version_num) VALUES (:rev)"),
                {"rev": HEAD_REVISION},
            )
            conn.commit()
            print(f"Готово: alembic_version = {HEAD_REVISION} (head)")
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    fix_alembic_version()
