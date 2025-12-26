"""merge heads

Revision ID: 9c9645936ab1
Revises: 942c8c81bdbd, e8b7c6d5a4f3
Create Date: 2025-12-25 11:01:49.197592

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c9645936ab1'
down_revision = ('942c8c81bdbd', 'e8b7c6d5a4f3')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
