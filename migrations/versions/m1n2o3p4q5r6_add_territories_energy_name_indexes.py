"""add territories energy name indexes

Revision ID: m1n2o3p4q5r6
Revises: l1m2n3o4p5q6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "m1n2o3p4q5r6"
down_revision = "l1m2n3o4p5q6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = {ix["name"] for ix in inspector.get_indexes("gs_fue_em_territories_energy", schema=SCHEMA_FUEL)}

    if "ix_gs_fue_em_territories_energy_regional_district_name" not in indexes:
        op.create_index(
            "ix_gs_fue_em_territories_energy_regional_district_name",
            "gs_fue_em_territories_energy",
            ["regional_district_name"],
            unique=False,
            schema=SCHEMA_FUEL,
        )
    if "ix_gs_fue_em_territories_energy_regional_energy_system_name" not in indexes:
        op.create_index(
            "ix_gs_fue_em_territories_energy_regional_energy_system_name",
            "gs_fue_em_territories_energy",
            ["regional_energy_system_name"],
            unique=False,
            schema=SCHEMA_FUEL,
        )
    if "ix_gs_fue_em_territories_energy_energy_unit_name" not in indexes:
        op.create_index(
            "ix_gs_fue_em_territories_energy_energy_unit_name",
            "gs_fue_em_territories_energy",
            ["energy_unit_name"],
            unique=False,
            schema=SCHEMA_FUEL,
        )


def downgrade():
    for name in [
        "ix_gs_fue_em_territories_energy_energy_unit_name",
        "ix_gs_fue_em_territories_energy_regional_energy_system_name",
        "ix_gs_fue_em_territories_energy_regional_district_name",
    ]:
        op.drop_index(name, table_name="gs_fue_em_territories_energy", schema=SCHEMA_FUEL)
