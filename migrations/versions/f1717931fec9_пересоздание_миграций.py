"""Пересоздание миграций

Revision ID: f1717931fec9
Revises: d5e6f7a8b9c0
Create Date: 2025-12-21 10:50:12.971430

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1717931fec9'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Добавляем колонку как nullable
    op.add_column(
        'gs_regional_energy_systems',
        sa.Column('name_rp', sa.String(length=255), nullable=True),
        schema='gs_sys'
    )

    # 2) Заполняем существующие строки
    # Самый логичный дефолт — скопировать из name
    op.execute("""
        UPDATE gs_sys.gs_regional_energy_systems
        SET name_rp = COALESCE(name_rp, name)
        WHERE name_rp IS NULL
    """)

    # 3) Делаем NOT NULL
    op.alter_column(
        'gs_regional_energy_systems',
        'name_rp',
        existing_type=sa.String(length=255),
        nullable=False,
        schema='gs_sys'
    )


def downgrade():
    op.drop_column('gs_regional_energy_systems', 'name_rp', schema='gs_sys')