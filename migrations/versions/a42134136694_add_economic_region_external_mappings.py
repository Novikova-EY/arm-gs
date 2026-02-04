"""add economic region external mappings

Revision ID: a42134136694
Revises: d9e8f7c6b5a4
Create Date: 2026-01-30 08:46:32.175941

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a42134136694'
down_revision = 'd9e8f7c6b5a4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gs_fue_em_economic_region",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=False),
        sa.Column("external_name", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="gs_fue_em",
    )


def downgrade():
    op.drop_table("gs_fue_em_economic_region", schema="gs_fue_em")
