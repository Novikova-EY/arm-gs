"""add date_commission_year to machines

Revision ID: a2b3c4d5e6f7
Revises: 54b85a459de4
Create Date: 2026-02-10 09:20:00.000000

Добавляет поле date_commission_year в таблицу machines
для хранения фактического года ввода агрегата в работу.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "54b85a459de4"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет поле date_commission_year в таблицу machines."""
    op.add_column(
        "machines",
        sa.Column("date_commission_year", sa.Integer(), nullable=True),
        schema=SCHEMA_GENERATION,
    )


def downgrade():
    """Удаляет поле date_commission_year из таблицы machines."""
    op.drop_column("machines", "date_commission_year", schema=SCHEMA_GENERATION)

