"""Пересоздание миграций 2

Revision ID: 942c8c81bdbd
Revises: f1717931fec9
Create Date: 2025-12-21 11:07:35.830233

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '942c8c81bdbd'
down_revision = 'f1717931fec9'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Добавляем колонку как nullable
    op.add_column(
        'gs_regional_districts',
        sa.Column('name_rp', sa.String(length=255), nullable=True),
        schema='gs_sys'
    )

    # 2) Заполняем существующие строки
    op.execute("""
        UPDATE gs_sys.gs_regional_districts
        SET name_rp = COALESCE(name_rp, name)
        WHERE name_rp IS NULL
    """)

    # 3) Делаем NOT NULL
    op.alter_column(
        'gs_regional_districts',
        'name_rp',
        existing_type=sa.String(length=255),
        nullable=False,
        schema='gs_sys'
    )


def downgrade():
    op.drop_column('gs_regional_districts', 'name_rp', schema='gs_sys')