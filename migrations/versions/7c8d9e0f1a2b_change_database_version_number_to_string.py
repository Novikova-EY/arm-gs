"""change database version_number to string

Revision ID: 7c8d9e0f1a2b
Revises: 6c7d8e9f0a1b
Create Date: 2026-01-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "7c8d9e0f1a2b"
down_revision = "6c7d8e9f0a1b"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "gs_database_versions",
        "version_number",
        existing_type=sa.Integer(),
        type_=sa.String(length=20),
        nullable=False,
        schema=SCHEMA_REFDATA,
        postgresql_using="version_number::varchar",
    )


def downgrade():
    op.alter_column(
        "gs_database_versions",
        "version_number",
        existing_type=sa.String(length=20),
        type_=sa.Integer(),
        nullable=False,
        schema=SCHEMA_REFDATA,
        postgresql_using="version_number::integer",
    )
