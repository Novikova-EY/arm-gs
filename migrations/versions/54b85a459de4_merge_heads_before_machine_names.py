"""merge_heads_before_machine_names

Revision ID: 54b85a459de4
Revises: 0123abcd4567, f6a7b8c9d0e1, f8a9b0c1d2e3, m2n3o4p5q6r7
Create Date: 2026-02-06 12:05:37.037359

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54b85a459de4'
down_revision = ('0123abcd4567', 'f6a7b8c9d0e1', 'f8a9b0c1d2e3', 'm2n3o4p5q6r7')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
