"""change_equipment_group_k_to_integer

Revision ID: f8g9h0i1j2k3
Revises: e6f7a8b9c0d1
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8g9h0i1j2k3'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    # Изменяем тип столбца k с Numeric(20,6) на Integer
    # При конвертации округляем значение (ROUND)
    op.execute("""
        ALTER TABLE gs_fue.gs_fue_equipment_groups
        ALTER COLUMN k TYPE integer USING ROUND(k)::integer
    """)


def downgrade():
    op.alter_column(
        'gs_fue_equipment_groups',
        'k',
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=20, scale=6),
        existing_nullable=True,
        schema='gs_fue',
    )
