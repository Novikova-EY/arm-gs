"""Помесячный прогноз выработки ЭЭ для перспективных площадок ГЭС/ГАЭС.

Revision ID: p2h3y4d5r6o7
Revises: o1z2p3m4a5x6
Create Date: 2026-08-26
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "p2h3y4d5r6o7"
down_revision = "o1z2p3m4a5x6"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "gs_gen_prospective_place_hydro_energy_forecasts"


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("place_kind", sa.String(length=8), nullable=False),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("scenario", sa.String(length=16), nullable=False),
        sa.Column("month_number", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "place_kind IN ('ges', 'gaes')",
            name="ck_pp_hydro_forecast_place_kind",
        ),
        sa.CheckConstraint(
            "scenario IN ('low_95', 'medium_50')",
            name="ck_pp_hydro_forecast_scenario",
        ),
        sa.CheckConstraint(
            "month_number BETWEEN 1 AND 12",
            name="ck_pp_hydro_forecast_month",
        ),
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_pp_hydro_forecast_place",
        TABLE,
        ["place_kind", "place_id"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_pp_hydro_forecast_scenario",
        TABLE,
        ["scenario"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_pp_hydro_forecast_month",
        TABLE,
        ["month_number"],
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_pp_hydro_forecast_database_version_id",
        TABLE,
        ["database_version_id"],
        schema=SCHEMA_GEN,
    )
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX uq_pp_hydro_forecast_place_scenario_month_ver "
            f"ON {SCHEMA_GEN}.{TABLE} "
            f"(place_kind, place_id, scenario, month_number, "
            f"COALESCE(database_version_id, -1))"
        )
    )
    op.create_foreign_key(
        "fk_pp_hydro_forecast_database_version",
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
        "fk_pp_hydro_forecast_database_version",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.execute(
        sa.text(
            f"DROP INDEX IF EXISTS {SCHEMA_GEN}.uq_pp_hydro_forecast_place_scenario_month_ver"
        )
    )
    for ix in (
        "ix_pp_hydro_forecast_database_version_id",
        "ix_pp_hydro_forecast_month",
        "ix_pp_hydro_forecast_scenario",
        "ix_pp_hydro_forecast_place",
    ):
        if column_utils.index_exists(conn, SCHEMA_GEN, ix):
            op.drop_index(ix, table_name=TABLE, schema=SCHEMA_GEN)
    op.drop_table(TABLE, schema=SCHEMA_GEN)
