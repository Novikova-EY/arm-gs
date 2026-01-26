"""extend database version number length

Revision ID: c1d2e3f4a5b6
Revises: d5e6f7a8b9c0
Create Date: 2026-01-26 00:00:00.000000

Увеличивает длину поля version_number в таблице gs_database_versions до 30 символов.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    """Увеличивает длину поля version_number до 30 символов."""
    op.alter_column(
        "gs_database_versions",
        "version_number",
        type_=sa.String(30),
        existing_type=sa.String(20),
        existing_nullable=False,
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    """Возвращает длину поля version_number к 20 символам."""
    op.alter_column(
        "gs_database_versions",
        "version_number",
        type_=sa.String(20),
        existing_type=sa.String(30),
        existing_nullable=False,
        schema=SCHEMA_REFDATA,
    )
