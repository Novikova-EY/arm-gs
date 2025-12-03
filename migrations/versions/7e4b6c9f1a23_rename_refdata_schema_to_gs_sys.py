"""rename refdata schema to gs_sys

Revision ID: 7e4b6c9f1a23
Revises: ff9f0f8940c8
Create Date: 2025-12-02 00:00:00.000000

Миграция переименовывает схему refdata в gs_sys.

Важно:
- Перед выполнением убедитесь, что у пользователя БД есть права на ALTER SCHEMA.
- После выполнения миграции обновите переменные окружения SCHEMA_REFDATA и DB_SEARCH_PATH,
  а также при необходимости конфигурацию приложения.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "7e4b6c9f1a23"
down_revision = "ff9f0f8940c8"
branch_labels = None
depends_on = None


def upgrade():
    """
    Переименовать схему refdata в gs_sys.
    """
    # Используем "сырое" SQL, т.к. Alembic не имеет high-level API для переименования схемы
    op.execute("ALTER SCHEMA refdata RENAME TO gs_sys;")


def downgrade():
    """
    Откат: вернуть имя схемы gs_sys обратно в refdata.
    """
    op.execute("ALTER SCHEMA gs_sys RENAME TO refdata;")



