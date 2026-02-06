"""merge heads after cities

Revision ID: 19075b3d9c87
Revises: c1a2b3c4d5e6, e1f2a3b4c5d6
Create Date: 2026-02-04 07:45:13.905088

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '19075b3d9c87'
down_revision = ('c1a2b3c4d5e6', 'e1f2a3b4c5d6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
