"""create_database_versions_table

Revision ID: c5845b674713
Revises: de13c9499a00
Create Date: 2025-10-21 06:21:26.220508

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5845b674713'
down_revision = 'de13c9499a00'
branch_labels = None
depends_on = None


def upgrade():
    # Создание таблицы database_versions в схеме generation
    op.create_table('database_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('snapshot_path', sa.String(length=500), nullable=True),
        sa.Column('snapshot_size', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('version_number'),
        sa.UniqueConstraint('name'),
        schema='generation'
    )
    
    # Создание индексов
    op.create_index(op.f('ix_generation_database_versions_version_number'), 'database_versions', ['version_number'], unique=True, schema='generation')
    op.create_index(op.f('ix_generation_database_versions_name'), 'database_versions', ['name'], unique=True, schema='generation')
    op.create_index(op.f('ix_generation_database_versions_is_active'), 'database_versions', ['is_active'], unique=False, schema='generation')


def downgrade():
    # Удаление индексов
    op.drop_index(op.f('ix_generation_database_versions_is_active'), table_name='database_versions', schema='generation')
    op.drop_index(op.f('ix_generation_database_versions_name'), table_name='database_versions', schema='generation')
    op.drop_index(op.f('ix_generation_database_versions_version_number'), table_name='database_versions', schema='generation')
    
    # Удаление таблицы database_versions из схемы generation
    op.drop_table('database_versions', schema='generation')
