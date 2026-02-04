"""add union energy system external mappings

Revision ID: a8b9c0d1e2f3
Revises: d7e8f9a0b1c2
Create Date: 2026-01-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "a8b9c0d1e2f3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table(
        "gs_union_energy_system_external_mappings", schema=SCHEMA_REFDATA
    ):
        op.create_table(
            "gs_union_energy_system_external_mappings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("union_energy_system_ref_uuid", sa.String(length=36), nullable=False),
            sa.Column("external_id", sa.String(length=80), nullable=False),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            schema=SCHEMA_REFDATA,
        )

        op.create_index(
            "ix_ues_external_mappings_union_energy_system_ref_uuid",
            "gs_union_energy_system_external_mappings",
            ["union_energy_system_ref_uuid"],
            unique=False,
            schema=SCHEMA_REFDATA,
        )
        op.create_index(
            "ix_ues_external_mappings_external_id",
            "gs_union_energy_system_external_mappings",
            ["external_id"],
            unique=False,
            schema=SCHEMA_REFDATA,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table(
        "gs_union_energy_system_external_mappings", schema=SCHEMA_REFDATA
    ):
        op.drop_index(
            "ix_ues_external_mappings_external_id",
            table_name="gs_union_energy_system_external_mappings",
            schema=SCHEMA_REFDATA,
        )
        op.drop_index(
            "ix_ues_external_mappings_union_energy_system_ref_uuid",
            table_name="gs_union_energy_system_external_mappings",
            schema=SCHEMA_REFDATA,
        )
        op.drop_table(
            "gs_union_energy_system_external_mappings", schema=SCHEMA_REFDATA
        )
