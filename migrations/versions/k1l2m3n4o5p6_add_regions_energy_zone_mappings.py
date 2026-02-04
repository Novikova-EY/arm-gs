"""add regional district/res/energy zone mappings

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "k1l2m3n4o5p6"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def _create_mapping_table(table_name: str, ref_uuid_col: str):
    short_table = table_name.replace("gs_fue_em_", "em_")
    ref_index_name = f"ix_{short_table}_uuid"
    ext_index_name = f"ix_{short_table}_ext_id"
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(ref_uuid_col, sa.String(length=36), nullable=True),
        sa.Column("external_id", sa.String(length=80), nullable=False),
        sa.Column("external_name", sa.String(length=255), nullable=True),
        sa.Column("external_nameoes", sa.String(length=255), nullable=True),
        sa.Column("external_abbr", sa.String(length=255), nullable=True),
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        ref_index_name,
        table_name,
        [ref_uuid_col],
        unique=False,
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        ext_index_name,
        table_name,
        ["external_id"],
        unique=False,
        schema=SCHEMA_FUEL,
    )


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("gs_fue_em_regional_district", schema=SCHEMA_FUEL):
        _create_mapping_table("gs_fue_em_regional_district", "regional_district_ref_uuid")

    if not inspector.has_table("gs_fue_em_regional_energy_system", schema=SCHEMA_FUEL):
        _create_mapping_table(
            "gs_fue_em_regional_energy_system",
            "regional_energy_system_ref_uuid",
        )

    if not inspector.has_table("gs_fue_em_energy_zone", schema=SCHEMA_FUEL):
        _create_mapping_table("gs_fue_em_energy_zone", "energy_zone_ref_uuid")


def downgrade():
    for table_name, ref_uuid_col in [
        ("gs_fue_em_energy_zone", "energy_zone_ref_uuid"),
        ("gs_fue_em_regional_energy_system", "regional_energy_system_ref_uuid"),
        ("gs_fue_em_regional_district", "regional_district_ref_uuid"),
    ]:
        short_table = table_name.replace("gs_fue_em_", "em_")
        ref_index_name = f"ix_{short_table}_uuid"
        ext_index_name = f"ix_{short_table}_ext_id"
        if op.get_bind().dialect.has_table(op.get_bind(), table_name, schema=SCHEMA_FUEL):
            op.drop_index(
                ext_index_name,
                table_name=table_name,
                schema=SCHEMA_FUEL,
            )
            op.drop_index(
                ref_index_name,
                table_name=table_name,
                schema=SCHEMA_FUEL,
            )
            op.drop_table(table_name, schema=SCHEMA_FUEL)
