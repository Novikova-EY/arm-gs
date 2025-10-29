"""merge heads 2025-10-29

Revision ID: dcb7ade888b9
Revises: fix_fd_unique_20251029, 8264aa5b0a0b
Create Date: 2025-10-29 07:10:46.834860

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dcb7ade888b9'
down_revision = ('fix_fd_unique_20251029', '8264aa5b0a0b')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
