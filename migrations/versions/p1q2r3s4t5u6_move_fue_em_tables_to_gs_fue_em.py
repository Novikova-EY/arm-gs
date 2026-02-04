"""move fue em tables to gs_fue_em

Revision ID: p1q2r3s4t5u6
Revises: o1p2q3r4s5t6
Create Date: 2026-01-30 08:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL, SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "p1q2r3s4t5u6"
down_revision = "o1p2q3r4s5t6"
branch_labels = None
depends_on = None


TABLES = [
    "gs_fue_em_business_unit",
    "gs_fue_em_department",
    "gs_fue_em_federal_district",
    "gs_fue_em_territories_energy",
    "gs_fue_em_union_energy_system",
]

SEQUENCES = [
    "gs_fue_em_business_unit_id_seq",
    "gs_fue_em_department_id_seq",
    "gs_fue_em_federal_district_id_seq",
    "gs_fue_em_territories_energy_id_seq",
    "gs_fue_em_union_energy_system_id_seq",
]


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUE_EM}")

    for table_name in TABLES:
        if inspector.has_table(table_name, schema=SCHEMA_FUEL):
            op.execute(
                f"ALTER TABLE {SCHEMA_FUEL}.{table_name} SET SCHEMA {SCHEMA_FUE_EM}"
            )

    for seq_name in SEQUENCES:
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUEL}.{seq_name} "
            f"SET SCHEMA {SCHEMA_FUE_EM}"
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUEL}")

    for table_name in TABLES:
        if inspector.has_table(table_name, schema=SCHEMA_FUE_EM):
            op.execute(
                f"ALTER TABLE {SCHEMA_FUE_EM}.{table_name} SET SCHEMA {SCHEMA_FUEL}"
            )

    for seq_name in SEQUENCES:
        op.execute(
            f"ALTER SEQUENCE IF EXISTS {SCHEMA_FUE_EM}.{seq_name} "
            f"SET SCHEMA {SCHEMA_FUEL}"
        )
