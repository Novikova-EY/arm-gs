"""move ues external mappings to gs_fue

Revision ID: b1c2d3e4f5a6
Revises: a8b9c0d1e2f3
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_REFDATA, SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def _move_sequence(old_schema: str, new_schema: str, seq_name: str) -> None:
    op.execute(
        f"ALTER SEQUENCE IF EXISTS {old_schema}.{seq_name} SET SCHEMA {new_schema}"
    )


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUEL}")

    if inspector.has_table(
        "gs_union_energy_system_external_mappings", schema=SCHEMA_REFDATA
    ):
        op.execute(
            f"ALTER TABLE {SCHEMA_REFDATA}.gs_union_energy_system_external_mappings "
            f"SET SCHEMA {SCHEMA_FUEL}"
        )
        _move_sequence(
            SCHEMA_REFDATA,
            SCHEMA_FUEL,
            "gs_union_energy_system_external_mappings_id_seq",
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table(
        "gs_union_energy_system_external_mappings", schema=SCHEMA_FUEL
    ):
        op.execute(
            f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
            f"SET SCHEMA {SCHEMA_REFDATA}"
        )
        _move_sequence(
            SCHEMA_FUEL,
            SCHEMA_REFDATA,
            "gs_union_energy_system_external_mappings_id_seq",
        )
