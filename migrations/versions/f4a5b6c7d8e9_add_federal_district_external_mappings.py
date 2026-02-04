"""add federal district external mappings

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("gs_fue_em_federal_district", schema=SCHEMA_FUEL):
        op.create_table(
            "gs_fue_em_federal_district",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("federal_district_ref_uuid", sa.String(length=36), nullable=False),
            sa.Column("external_id", sa.String(length=80), nullable=False),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            schema=SCHEMA_FUEL,
        )
        op.create_index(
            "ix_fd_em_federal_district_ref_uuid",
            "gs_fue_em_federal_district",
            ["federal_district_ref_uuid"],
            unique=False,
            schema=SCHEMA_FUEL,
        )
        op.create_index(
            "ix_fd_em_external_id",
            "gs_fue_em_federal_district",
            ["external_id"],
            unique=False,
            schema=SCHEMA_FUEL,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("gs_fue_em_federal_district", schema=SCHEMA_FUEL):
        op.drop_index(
            "ix_fd_em_external_id",
            table_name="gs_fue_em_federal_district",
            schema=SCHEMA_FUEL,
        )
        op.drop_index(
            "ix_fd_em_federal_district_ref_uuid",
            table_name="gs_fue_em_federal_district",
            schema=SCHEMA_FUEL,
        )
        op.drop_table("gs_fue_em_federal_district", schema=SCHEMA_FUEL)
