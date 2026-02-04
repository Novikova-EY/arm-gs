"""merge heads

Revision ID: 8656120d4c9b
Revises: 7c8d9e0f1a2b, b8c9d0e1f2a3, c1d2e3f4a5b6
Create Date: 2026-01-26 14:24:46.003797

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8656120d4c9b'
down_revision = ('7c8d9e0f1a2b', 'b8c9d0e1f2a3', 'c1d2e3f4a5b6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
