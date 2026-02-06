"""expand multi-date fields for machines

Revision ID: f8a9b0c1d2e3
Revises: a4b5c6d7e8f9
Create Date: 2026-02-04 00:00:00.000000

Увеличивает длину полей date_relabing_fact и date_update_fact,
чтобы разрешить хранить несколько дат в текстовом виде.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "f8a9b0c1d2e3"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade():
    """Расширяет длину полей дат для агрегатов и ПГУ."""
    for table in ("machines", "pgu_machines"):
        op.alter_column(
            table,
            "date_relabing_fact",
            type_=sa.String(255),
            existing_type=sa.String(10),
            existing_nullable=True,
            schema=SCHEMA_GENERATION,
        )
        op.alter_column(
            table,
            "date_update_fact",
            type_=sa.String(255),
            existing_type=sa.String(10),
            existing_nullable=True,
            schema=SCHEMA_GENERATION,
        )


def downgrade():
    """Возвращает длину полей дат к 10 символам."""
    for table in ("machines", "pgu_machines"):
        op.alter_column(
            table,
            "date_relabing_fact",
            type_=sa.String(10),
            existing_type=sa.String(255),
            existing_nullable=True,
            schema=SCHEMA_GENERATION,
        )
        op.alter_column(
            table,
            "date_update_fact",
            type_=sa.String(10),
            existing_type=sa.String(255),
            existing_nullable=True,
            schema=SCHEMA_GENERATION,
        )

