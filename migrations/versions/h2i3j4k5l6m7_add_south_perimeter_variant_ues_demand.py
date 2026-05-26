# -*- coding: utf-8 -*-
"""gs_pd_union_energy_system_demand_params: вариант периметра ОЭС Юга.

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "h2i3j4k5l6m7"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_union_energy_system_demand_params"
SCHEMA_REF = "gs_sys"
UES_TABLE = "gs_sys_union_energy_systems"
SOUTH_NAME = "ОЭС Юга"
DEFAULT_VARIANT = "without_nt"


def _column_exists(connection, schema: str, table: str, column: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": schema, "table": table, "column": column},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, SCHEMA_PD, TABLE, "south_perimeter_variant"):
        op.add_column(
            TABLE,
            sa.Column("south_perimeter_variant", sa.String(length=32), nullable=True),
            schema=SCHEMA_PD,
        )
        op.create_index(
            "ix_gs_pd_ues_demand_params_south_perimeter_variant",
            TABLE,
            ["south_perimeter_variant"],
            unique=False,
            schema=SCHEMA_PD,
        )
        op.create_check_constraint(
            "ck_gs_ues_demand_params_south_perimeter_variant",
            TABLE,
            "south_perimeter_variant IS NULL OR south_perimeter_variant IN "
            "('with_nt', 'without_nt', 'without_crimea_sev')",
            schema=SCHEMA_PD,
        )

    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_PD}.{TABLE} AS p
            SET south_perimeter_variant = :variant
            FROM {SCHEMA_REF}.{UES_TABLE} AS u
            WHERE p.id_union_energy_system = u.id
              AND lower(trim(u.name)) = lower(:south_name)
              AND p.south_perimeter_variant IS NULL
            """
        ),
        {"variant": DEFAULT_VARIANT, "south_name": SOUTH_NAME},
    )


def downgrade():
    conn = op.get_bind()
    if not _column_exists(conn, SCHEMA_PD, TABLE, "south_perimeter_variant"):
        return
    op.drop_constraint(
        "ck_gs_ues_demand_params_south_perimeter_variant",
        TABLE,
        schema=SCHEMA_PD,
        type_="check",
    )
    op.drop_index(
        "ix_gs_pd_ues_demand_params_south_perimeter_variant",
        table_name=TABLE,
        schema=SCHEMA_PD,
    )
    op.drop_column(TABLE, "south_perimeter_variant", schema=SCHEMA_PD)
