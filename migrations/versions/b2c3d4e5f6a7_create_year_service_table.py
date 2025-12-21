"""create year service table

Revision ID: b2c3d4e5f6a7
Revises: 7e4b6c9f1a23
Create Date: 2025-01-28 12:00:00.000000

Создает таблицу gs_year_service для хранения годов СиПР (year_sipr_start, year_sipr_end)
с привязкой к версии БД (database_version_id) и полями аудита (created_at, created_by, updated_at, modified_by).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "7e4b6c9f1a23"
branch_labels = None
depends_on = None


def upgrade():
    """Создает таблицу gs_year_service с полями для годов СиПР и аудита."""
    op.create_table(
        'gs_year_service',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year_sipr_start', sa.Integer(), nullable=True),
        sa.Column('year_sipr_end', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('modified_by', sa.String(length=255), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('database_version_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['database_version_id'],
            [f'{SCHEMA_REFDATA}.gs_database_versions.id'],
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        schema=SCHEMA_REFDATA
    )
    
    # Создаем индекс для database_version_id
    op.create_index(
        op.f('ix_gs_sys_gs_year_service_database_version_id'),
        'gs_year_service',
        ['database_version_id'],
        unique=False,
        schema=SCHEMA_REFDATA
    )


def downgrade():
    """Удаляет таблицу gs_year_service."""
    op.drop_index(
        op.f('ix_gs_sys_gs_year_service_database_version_id'),
        table_name='gs_year_service',
        schema=SCHEMA_REFDATA
    )
    op.drop_table('gs_year_service', schema=SCHEMA_REFDATA)

