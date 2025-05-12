"""обновлена модель Station note

Revision ID: 8e353bd6a6b1
Revises: da679aa9d18c
Create Date: 2025-05-02 14:15:42.172442

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '8e353bd6a6b1'
down_revision = 'da679aa9d18c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('machines') as batch_op:
        batch_op.alter_column(
            'date_exploitation',
            existing_type=sa.String(length=10),
            type_=sa.Integer(),
            existing_nullable=True,
            existing_server_default=None  # ← обязательно!
        )

def downgrade():
    with op.batch_alter_table('machines') as batch_op:
        batch_op.alter_column(
            'date_exploitation',
            existing_type=sa.Integer(),
            type_=sa.String(length=10),
            existing_nullable=True,
            existing_server_default=None
        )

    # ### end Alembic commands ###
