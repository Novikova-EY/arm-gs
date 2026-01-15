"""
Скрипт для очистки таблицы версий Alembic и создания новой полной миграции.
"""
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config import Config

def reset_alembic_version():
    """Очищает таблицу alembic_version в схеме gs_auth."""
    # Получаем URL базы данных
    db_url = Config.SQLALCHEMY_DATABASE_URI
    
    # Если не установлен, формируем из переменных окружения
    if not db_url:
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASSWORD") or os.getenv("DB_PASS")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_driver = os.getenv("DB_DRIVER", "psycopg2")
        
        if not all([db_user, db_pass, db_name]):
            print("Ошибка: Не установлены переменные окружения для подключения к БД")
            print("Требуются: DB_USER, DB_PASSWORD (или DB_PASS), DB_NAME")
            sys.exit(1)
        
        db_url = f"postgresql+{db_driver}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    print(f"Подключение к БД: {db_host}:{db_port}/{db_name}")
    
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Очищаем таблицу alembic_version
            conn.execute(text("DELETE FROM gs_auth.alembic_version"))
            conn.commit()
            print("Таблица gs_auth.alembic_version очищена")
    except Exception as e:
        print(f"Ошибка при очистке таблицы alembic_version: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == "__main__":
    reset_alembic_version()

