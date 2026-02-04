"""expand machine name length

Revision ID: a4b5c6d7e8f9
Revises: 9c1c35d27d03
Create Date: 2026-01-30 00:00:00.000000

Увеличивает длину поля machine_name для агрегатов и ПГУ до 1024 символов.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "a4b5c6d7e8f9"
down_revision = "9c1c35d27d03"
branch_labels = None
depends_on = None


def upgrade():
    """Увеличивает длину machine_name до 1024 символов."""
    op.alter_column(
        "machines",
        "machine_name",
        type_=sa.String(1024),
        existing_type=sa.String(255),
        existing_nullable=False,
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "pgu_machines",
        "machine_name",
        type_=sa.String(1024),
        existing_type=sa.String(255),
        existing_nullable=False,
        schema=SCHEMA_GENERATION,
    )


def downgrade():
    """Возвращает длину machine_name к 255 символам."""
    op.alter_column(
        "machines",
        "machine_name",
        type_=sa.String(255),
        existing_type=sa.String(1024),
        existing_nullable=False,
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "pgu_machines",
        "machine_name",
        type_=sa.String(255),
        existing_type=sa.String(1024),
        existing_nullable=False,
        schema=SCHEMA_GENERATION,
    )
