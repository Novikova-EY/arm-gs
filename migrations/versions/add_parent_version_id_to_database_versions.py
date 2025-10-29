"""Add parent_version_id to database_versions table

Revision ID: add_parent_version
Revises: 
Create Date: 2025-10-21 13:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_parent_version'
down_revision = None  # Измените на ID последней миграции
branch_labels = None
depends_on = None


def upgrade():
    # Защитные проверки существования перед добавлением
    bind = op.get_bind()
    # 1) Колонка
    col_exists = bind.execute(sa.text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'generation'
          AND table_name = 'database_versions'
          AND column_name = 'parent_version_id'
        """
    )).fetchone() is not None

    if not col_exists:
        op.add_column(
            'database_versions',
            sa.Column('parent_version_id', sa.Integer(), nullable=True),
            schema='generation'
        )

    # 2) Индекс
    idx_exists = bind.execute(sa.text(
        """
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'generation'
          AND tablename = 'database_versions'
          AND indexname = 'ix_generation_database_versions_parent_version_id'
        """
    )).fetchone() is not None
    if not idx_exists:
        op.create_index(
            'ix_generation_database_versions_parent_version_id',
            'database_versions',
            ['parent_version_id'],
            schema='generation'
        )

    # 3) Внешний ключ
    fk_exists = bind.execute(sa.text(
        """
        SELECT 1
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'generation'
          AND tc.table_name = 'database_versions'
          AND tc.constraint_type = 'FOREIGN KEY'
          AND tc.constraint_name = 'fk_database_versions_parent_version_id'
        """
    )).fetchone() is not None
    if not fk_exists:
        op.create_foreign_key(
            'fk_database_versions_parent_version_id',
            'database_versions',
            'database_versions',
            ['parent_version_id'],
            ['id'],
            source_schema='generation',
            referent_schema='generation',
            ondelete='SET NULL'
        )


def downgrade():
    # Удаляем внешний ключ
    op.drop_constraint(
        'fk_database_versions_parent_version_id',
        'database_versions',
        schema='generation',
        type_='foreignkey'
    )
    
    # Удаляем индекс
    op.drop_index(
        'ix_generation_database_versions_parent_version_id',
        'database_versions',
        schema='generation'
    )
    
    # Удаляем колонку
    op.drop_column(
        'database_versions',
        'parent_version_id',
        schema='generation'
    )

