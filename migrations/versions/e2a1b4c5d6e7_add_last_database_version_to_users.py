"""add last_database_version_id to users

Revision ID: e2a1b4c5d6e7
Revises: d5e6f7a8b9c0
Create Date: 2026-01-19 00:00:00.000000

Добавляет ссылку на последнюю выбранную пользователем версию БД.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_AUTH, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "e2a1b4c5d6e7"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет last_database_version_id в таблицу users."""
    op.add_column(
        "users",
        sa.Column("last_database_version_id", sa.Integer(), nullable=True),
        schema=SCHEMA_AUTH,
    )
    op.create_index(
        "ix_users_last_database_version_id",
        "users",
        ["last_database_version_id"],
        schema=SCHEMA_AUTH,
    )
    op.create_foreign_key(
        "fk_users_last_database_version_id",
        source_table="users",
        referent_table="gs_database_versions",
        local_cols=["last_database_version_id"],
        remote_cols=["id"],
        source_schema=SCHEMA_AUTH,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )


def downgrade():
    """Удаляет last_database_version_id из таблицы users."""
    op.drop_constraint(
        "fk_users_last_database_version_id",
        "users",
        schema=SCHEMA_AUTH,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_users_last_database_version_id",
        table_name="users",
        schema=SCHEMA_AUTH,
    )
    op.drop_column("users", "last_database_version_id", schema=SCHEMA_AUTH)
