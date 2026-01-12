"""add display_order to federal_districts

Revision ID: a3c03ef2f465
Revises: 9c9645936ab1
Create Date: 2026-01-12 08:47:49.966714

"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "a3c03ef2f465"
down_revision = "9c9645936ab1"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет поле display_order в справочник федеральных округов."""
    op.add_column(
        "gs_federal_districts",
        sa.Column("display_order", sa.Integer(), nullable=True),
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    """Удаляет поле display_order из справочника федеральных округов."""
    op.drop_column("gs_federal_districts", "display_order", schema=SCHEMA_REFDATA)

