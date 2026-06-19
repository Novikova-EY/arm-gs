# -*- coding: utf-8 -*-
"""Таблица контрольной выработки ЭЭ по РЭС (млн кВт·ч).

Revision ID: y9z0a1b2c3d4
Revises: x8y9z0a1b2c3
Create Date: 2026-06-09
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "y9z0a1b2c3d4"
down_revision = "x8y9z0a1b2c3"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "gs_gen_regional_energy_system_energy_generations"
UNIQUE_INDEX = "uq_res_energy_gen_res_year_month_ver"
RES_YEAR_MONTH_INDEX = "ix_res_energy_gen_res_year_month"
MONTH_INDEX = "ix_res_energy_gen_month_number"
YEAR_INDEX = "ix_res_energy_gen_year_number"
RES_INDEX = "ix_res_energy_gen_id_regional_energy_system"

PERIOD_YEAR = 0


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    inspector = sa.inspect(conn)
    if TABLE in inspector.get_table_names(schema=SCHEMA_GEN):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column(
            "month_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text(str(PERIOD_YEAR)),
        ),
        sa.Column("id_regional_energy_system", sa.Integer(), nullable=True),
        sa.Column("electricity_generation", sa.Numeric(25, 16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_GEN,
    )

    op.create_index(RES_INDEX, TABLE, ["id_regional_energy_system"], schema=SCHEMA_GEN)
    op.create_index(YEAR_INDEX, TABLE, ["year_number"], schema=SCHEMA_GEN)
    op.create_index(MONTH_INDEX, TABLE, ["month_number"], schema=SCHEMA_GEN)
    op.create_index(
        RES_YEAR_MONTH_INDEX,
        TABLE,
        ["id_regional_energy_system", "year_number", "month_number"],
        schema=SCHEMA_GEN,
    )
    op.execute(
        text(
            f"""
            CREATE UNIQUE INDEX {UNIQUE_INDEX}
            ON "{SCHEMA_GEN}"."{TABLE}" (
                id_regional_energy_system,
                year_number,
                month_number,
                COALESCE(database_version_id, -1)
            )
            """
        )
    )

    op.create_foreign_key(
        "fk_res_energy_gen_regional_energy_system",
        TABLE,
        "gs_sys_regional_energy_systems",
        ["id_regional_energy_system"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_res_energy_gen_database_version",
        TABLE,
        ref_versions,
        ["database_version_id"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        return

    op.drop_constraint(
        "fk_res_energy_gen_database_version",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_res_energy_gen_regional_energy_system",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    if column_utils.index_exists(conn, SCHEMA_GEN, UNIQUE_INDEX):
        op.drop_index(UNIQUE_INDEX, table_name=TABLE, schema=SCHEMA_GEN)
    if column_utils.index_exists(conn, SCHEMA_GEN, RES_YEAR_MONTH_INDEX):
        op.drop_index(RES_YEAR_MONTH_INDEX, table_name=TABLE, schema=SCHEMA_GEN)
    if column_utils.index_exists(conn, SCHEMA_GEN, MONTH_INDEX):
        op.drop_index(MONTH_INDEX, table_name=TABLE, schema=SCHEMA_GEN)
    if column_utils.index_exists(conn, SCHEMA_GEN, YEAR_INDEX):
        op.drop_index(YEAR_INDEX, table_name=TABLE, schema=SCHEMA_GEN)
    if column_utils.index_exists(conn, SCHEMA_GEN, RES_INDEX):
        op.drop_index(RES_INDEX, table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_table(TABLE, schema=SCHEMA_GEN)
