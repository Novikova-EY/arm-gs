"""add dates to year service

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-01-28 13:00:00.000000

Добавляет поля date_sipr_start и date_sipr_end в таблицу gs_year_service
для хранения дат начала и конца периода СиПР.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет поля date_sipr_start и date_sipr_end в таблицу gs_year_service."""
    op.add_column(
        'gs_year_service',
        sa.Column('date_sipr_start', sa.Date(), nullable=True),
        schema=SCHEMA_REFDATA
    )
    op.add_column(
        'gs_year_service',
        sa.Column('date_sipr_end', sa.Date(), nullable=True),
        schema=SCHEMA_REFDATA
    )


def downgrade():
    """Удаляет поля date_sipr_start и date_sipr_end из таблицы gs_year_service."""
    op.drop_column('gs_year_service', 'date_sipr_end', schema=SCHEMA_REFDATA)
    op.drop_column('gs_year_service', 'date_sipr_start', schema=SCHEMA_REFDATA)










