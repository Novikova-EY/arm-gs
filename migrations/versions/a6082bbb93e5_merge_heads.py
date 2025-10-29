"""merge heads

Revision ID: a6082bbb93e5
Revises: add_parent_version, cf626c919b75
Create Date: 2025-10-21 13:27:16.260971

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6082bbb93e5'
down_revision = ('add_parent_version', 'cf626c919b75')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
