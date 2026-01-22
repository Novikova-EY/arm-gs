"""add display_order to equipment groups

Revision ID: 19c0f94da999
Revises: 8ff7f02abc20
Create Date: 2026-01-21 17:26:32.486495

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '19c0f94da999'
down_revision = '8ff7f02abc20'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'gs_equipment_groups',
        sa.Column('display_order', sa.Integer(), nullable=True),
        schema='gs_sys',
    )


def downgrade():
    op.drop_column('gs_equipment_groups', 'display_order', schema='gs_sys')
