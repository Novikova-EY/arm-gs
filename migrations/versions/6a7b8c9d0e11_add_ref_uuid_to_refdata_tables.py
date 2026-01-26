"""add ref_uuid to refdata tables

Revision ID: 6a7b8c9d0e11
Revises: 2a7c3e4f5b61
Create Date: 2026-01-22 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
import uuid
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "6a7b8c9d0e11"
down_revision = "2a7c3e4f5b61"
branch_labels = None
depends_on = None


REFDATA_TABLES = [
    "gs_federal_districts",
    "gs_regional_districts",
    "gs_energy_system_types",
    "gs_union_energy_systems",
    "gs_regional_energy_systems",
    "gs_synchronous_areas",
    "gs_energy_zones",
    "gs_energy_areas",
    "gs_energy_units",
    "gs_station_types",
    "gs_condition_types",
    "gs_machine_types",
    "gs_tes_types",
    "gs_tes_machine_types",
    "gs_pgu_tes_machine_types",
    "gs_technology_types",
    "gs_technology_availabilities",
    "gs_equipment_groups",
    "gs_fuel_categories",
    "gs_fuel_types",
    "gs_fuels",
    "gs_companies",
]


def _backfill_ref_uuid(conn, table_name: str) -> None:
    select_query = sa.text(
        f"SELECT id FROM {SCHEMA_REFDATA}.{table_name} WHERE ref_uuid IS NULL"
    )
    update_query = sa.text(
        f"UPDATE {SCHEMA_REFDATA}.{table_name} SET ref_uuid = :ref_uuid WHERE id = :id"
    )
    rows = conn.execute(select_query).fetchall()
    for row in rows:
        conn.execute(update_query, {"id": row[0], "ref_uuid": str(uuid.uuid4())})


def upgrade():
    conn = op.get_bind()
    for table_name in REFDATA_TABLES:
        op.add_column(
            table_name,
            sa.Column("ref_uuid", sa.String(length=36), nullable=True),
            schema=SCHEMA_REFDATA,
        )
        _backfill_ref_uuid(conn, table_name)
        op.alter_column(
            table_name,
            "ref_uuid",
            nullable=False,
            schema=SCHEMA_REFDATA,
        )
        op.create_index(
            f"ix_{table_name}_ref_uuid",
            table_name,
            ["ref_uuid"],
            unique=False,
            schema=SCHEMA_REFDATA,
        )


def downgrade():
    for table_name in REFDATA_TABLES:
        op.drop_index(
            f"ix_{table_name}_ref_uuid",
            table_name=table_name,
            schema=SCHEMA_REFDATA,
        )
        op.drop_column(table_name, "ref_uuid", schema=SCHEMA_REFDATA)
