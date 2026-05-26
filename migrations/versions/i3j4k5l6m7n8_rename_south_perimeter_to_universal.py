# -*- coding: utf-8 -*-
"""Переименование south_perimeter_variant → perimeter_variant_code (универсальный каталог).

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "i3j4k5l6m7n8"
down_revision = "h2i3j4k5l6m7"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
TABLE = "gs_pd_union_energy_system_demand_params"
OLD_COL = "south_perimeter_variant"
NEW_COL = "perimeter_variant_code"
KNOWN_CODES = (
    "with_nt",
    "without_nt",
    "without_crimea_sev",
    "without_nt_with_kaliningrad_es",
    "without_nt_without_kaliningrad_es",
)
CODES_SQL = ", ".join(f"'{c}'" for c in KNOWN_CODES)


def _column_exists(connection, column: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
        ),
        {"schema": SCHEMA_PD, "table": TABLE, "column": column},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _column_exists(conn, NEW_COL):
        return
    if _column_exists(conn, OLD_COL):
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
        op.alter_column(
            TABLE,
            OLD_COL,
            new_column_name=NEW_COL,
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=True,
            schema=SCHEMA_PD,
        )
    else:
        op.add_column(
            TABLE,
            sa.Column(NEW_COL, sa.String(length=64), nullable=True),
            schema=SCHEMA_PD,
        )
    op.create_index(
        f"ix_gs_pd_ues_demand_params_{NEW_COL}",
        TABLE,
        [NEW_COL],
        unique=False,
        schema=SCHEMA_PD,
    )
    op.create_check_constraint(
        f"ck_gs_ues_demand_params_{NEW_COL}",
        TABLE,
        f"{NEW_COL} IS NULL OR {NEW_COL} IN ({CODES_SQL})",
        schema=SCHEMA_PD,
    )


def downgrade():
    conn = op.get_bind()
    if not _column_exists(conn, NEW_COL):
        return
    op.drop_constraint(
        f"ck_gs_ues_demand_params_{NEW_COL}",
        TABLE,
        schema=SCHEMA_PD,
        type_="check",
    )
    op.drop_index(
        f"ix_gs_pd_ues_demand_params_{NEW_COL}",
        table_name=TABLE,
        schema=SCHEMA_PD,
    )
    op.alter_column(
        TABLE,
        NEW_COL,
        new_column_name=OLD_COL,
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=True,
        schema=SCHEMA_PD,
    )
    op.create_index(
        "ix_gs_pd_ues_demand_params_south_perimeter_variant",
        TABLE,
        [OLD_COL],
        unique=False,
        schema=SCHEMA_PD,
    )
    op.create_check_constraint(
        "ck_gs_ues_demand_params_south_perimeter_variant",
        TABLE,
        f"{OLD_COL} IS NULL OR {OLD_COL} IN ('with_nt', 'without_nt', 'without_crimea_sev')",
        schema=SCHEMA_PD,
    )
