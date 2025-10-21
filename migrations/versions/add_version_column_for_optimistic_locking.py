"""add version column for optimistic locking

Revision ID: add_version_col
Revises: 
Create Date: 2025-10-17

"""
from alembic import op
import sqlalchemy as sa
from config import SCHEMA_GENERATION

# revision identifiers, used by Alembic.
revision = 'add_version_col'
down_revision = '38f265d87266'
branch_labels = None
depends_on = None


def upgrade():
    """
    Добавление колонки version для оптимистической блокировки
    в таблицы stations, machines и pgu_machines.
    """
    # Добавление колонки version в таблицу stations
    op.add_column(
        'stations',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        schema=SCHEMA_GENERATION
    )
    
    # Добавление колонки version в таблицу machines
    op.add_column(
        'machines',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        schema=SCHEMA_GENERATION
    )
    
    # Добавление колонки version в таблицу pgu_machines
    op.add_column(
        'pgu_machines',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        schema=SCHEMA_GENERATION
    )
    
    # Инициализация значения version для существующих записей
    op.execute(f"UPDATE {SCHEMA_GENERATION}.stations SET version = 1 WHERE version IS NULL")
    op.execute(f"UPDATE {SCHEMA_GENERATION}.machines SET version = 1 WHERE version IS NULL")
    op.execute(f"UPDATE {SCHEMA_GENERATION}.pgu_machines SET version = 1 WHERE version IS NULL")


def downgrade():
    """
    Удаление колонки version из таблиц stations, machines и pgu_machines.
    """
    op.drop_column('stations', 'version', schema=SCHEMA_GENERATION)
    op.drop_column('machines', 'version', schema=SCHEMA_GENERATION)
    op.drop_column('pgu_machines', 'version', schema=SCHEMA_GENERATION)

