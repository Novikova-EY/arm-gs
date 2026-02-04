"""add territories energy mapping table

Revision ID: l1m2n3o4p5q6
Revises: k1l2m3n4o5p6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "l1m2n3o4p5q6"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("gs_fue_em_territories_energy", schema=SCHEMA_FUEL):
        op.create_table(
            "gs_fue_em_territories_energy",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("regional_district_ref_uuid", sa.String(length=36), nullable=True),
            sa.Column("regional_energy_system_ref_uuid", sa.String(length=36), nullable=True),
            sa.Column("energy_zone_ref_uuid", sa.String(length=36), nullable=True),
            sa.Column("regional_district_name", sa.String(length=255), nullable=True),
            sa.Column("regional_energy_system_name", sa.String(length=255), nullable=True),
            sa.Column("energy_unit_name", sa.String(length=255), nullable=True),
            sa.Column("name_topl", sa.String(length=255), nullable=True),
            sa.Column("ao_topl", sa.String(length=255), nullable=True),
            sa.Column("obl_topl", sa.String(length=255), nullable=True),
            sa.Column("alph_topl", sa.String(length=255), nullable=True),
            sa.Column("dep_topl", sa.String(length=255), nullable=True),
            sa.Column("oes_topl", sa.String(length=255), nullable=True),
            sa.Column("er_topl", sa.String(length=255), nullable=True),
            sa.Column("terr_belyaev_topl", sa.String(length=255), nullable=True),
            sa.Column("teo90_topl", sa.String(length=255), nullable=True),
            sa.Column("fo_topl", sa.String(length=255), nullable=True),
            sa.Column("abbr_topl", sa.String(length=255), nullable=True),
            sa.Column("reu_topl", sa.String(length=255), nullable=True),
            sa.Column("pter_topl", sa.String(length=255), nullable=True),
            sa.Column("keyword_topl", sa.String(length=255), nullable=True),
            schema=SCHEMA_FUEL,
        )

        op.create_index(
            "ix_gs_fue_em_territories_energy_rd_uuid",
            "gs_fue_em_territories_energy",
            ["regional_district_ref_uuid"],
            unique=False,
            schema=SCHEMA_FUEL,
        )
        op.create_index(
            "ix_gs_fue_em_territories_energy_res_uuid",
            "gs_fue_em_territories_energy",
            ["regional_energy_system_ref_uuid"],
            unique=False,
            schema=SCHEMA_FUEL,
        )
        op.create_index(
            "ix_gs_fue_em_territories_energy_ez_uuid",
            "gs_fue_em_territories_energy",
            ["energy_zone_ref_uuid"],
            unique=False,
            schema=SCHEMA_FUEL,
        )


def downgrade():
    if op.get_bind().dialect.has_table(
        op.get_bind(), "gs_fue_em_territories_energy", schema=SCHEMA_FUEL
    ):
        op.drop_index(
            "ix_gs_fue_em_territories_energy_ez_uuid",
            table_name="gs_fue_em_territories_energy",
            schema=SCHEMA_FUEL,
        )
        op.drop_index(
            "ix_gs_fue_em_territories_energy_res_uuid",
            table_name="gs_fue_em_territories_energy",
            schema=SCHEMA_FUEL,
        )
        op.drop_index(
            "ix_gs_fue_em_territories_energy_rd_uuid",
            table_name="gs_fue_em_territories_energy",
            schema=SCHEMA_FUEL,
        )
        op.drop_table("gs_fue_em_territories_energy", schema=SCHEMA_FUEL)
