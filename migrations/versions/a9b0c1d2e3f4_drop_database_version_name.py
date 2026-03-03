"""drop database version name column

Revision ID: a9b0c1d2e3f4
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28 00:00:00.000000

Удаляет столбец name из таблицы gs_database_versions.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "a9b0c1d2e3f4"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Удаляем индекс по name (IF EXISTS для совместимости с разными средами)
    op.execute(
        sa.text(
            f'DROP INDEX IF EXISTS "{SCHEMA_REFDATA}".ix_refdata_database_versions_name'
        )
    )
    op.execute(
        sa.text(
            f'DROP INDEX IF EXISTS "{SCHEMA_REFDATA}".ix_gs_database_versions_name'
        )
    )
    # Удаляем столбец name
    op.drop_column(
        "gs_database_versions",
        "name",
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    # Добавляем столбец name обратно
    op.add_column(
        "gs_database_versions",
        sa.Column("name", sa.String(255), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    # Заполняем name из version_number для существующих записей
    op.execute(
        sa.text(
            f'UPDATE "{SCHEMA_REFDATA}".gs_database_versions SET name = version_number WHERE name IS NULL'
        )
    )
    op.alter_column(
        "gs_database_versions",
        "name",
        nullable=False,
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        "ix_gs_database_versions_name",
        "gs_database_versions",
        ["name"],
        unique=True,
        schema=SCHEMA_REFDATA,
    )
