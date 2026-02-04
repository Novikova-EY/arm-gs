"""drop territories energy name columns

Revision ID: n1o2p3q4r5s6
Revises: m1n2o3p4q5r6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "n1o2p3q4r5s6"
down_revision = "m1n2o3p4q5r6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = {ix["name"] for ix in inspector.get_indexes("gs_fue_em_territories_energy", schema=SCHEMA_FUEL)}

    for name in [
        "ix_gs_fue_em_territories_energy_regional_district_name",
        "ix_gs_fue_em_territories_energy_regional_energy_system_name",
        "ix_gs_fue_em_territories_energy_energy_unit_name",
    ]:
        if name in indexes:
            op.drop_index(name, table_name="gs_fue_em_territories_energy", schema=SCHEMA_FUEL)

    with op.batch_alter_table("gs_fue_em_territories_energy", schema=SCHEMA_FUEL) as batch_op:
        batch_op.drop_column("regional_district_name")
        batch_op.drop_column("regional_energy_system_name")
        batch_op.drop_column("energy_unit_name")


def downgrade():
    with op.batch_alter_table("gs_fue_em_territories_energy", schema=SCHEMA_FUEL) as batch_op:
        batch_op.add_column(
            sa.Column("regional_district_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("regional_energy_system_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("energy_unit_name", sa.String(length=255), nullable=True)
        )

    op.create_index(
        "ix_gs_fue_em_territories_energy_regional_district_name",
        "gs_fue_em_territories_energy",
        ["regional_district_name"],
        unique=False,
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_gs_fue_em_territories_energy_regional_energy_system_name",
        "gs_fue_em_territories_energy",
        ["regional_energy_system_name"],
        unique=False,
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_gs_fue_em_territories_energy_energy_unit_name",
        "gs_fue_em_territories_energy",
        ["energy_unit_name"],
        unique=False,
        schema=SCHEMA_FUEL,
    )
