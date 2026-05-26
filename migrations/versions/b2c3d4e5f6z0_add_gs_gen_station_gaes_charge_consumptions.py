"""Потребление электроэнергии ГАЭС на заряд по годам (млн кВт·ч).

Revision ID: b2c3d4e5f6z0
Revises: a1b2c3d4e5z9
Create Date: 2026-05-07
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "b2c3d4e5f6z0"
down_revision = "a1b2c3d4e5z9"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "gs_gen_station_gaes_charge_consumptions"


def upgrade():
    conn = op.get_bind()
    ref_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REF)
    if ref_versions is None:
        raise RuntimeError(
            f"Не найдена таблица версий БД в {SCHEMA_REF} "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=True),
            sa.Column("id_station", sa.Integer(), nullable=True),
            sa.Column("charge_consumption", sa.Numeric(25, 16), nullable=True),
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
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_gaes_charge_id_station"):
        op.create_index(
            "ix_station_gaes_charge_id_station",
            TABLE,
            ["id_station"],
            schema=SCHEMA_GEN,
        )
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_gaes_charge_year_number"):
        op.create_index(
            "ix_station_gaes_charge_year_number",
            TABLE,
            ["year_number"],
            schema=SCHEMA_GEN,
        )
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_gaes_charge_station_year"):
        op.create_index(
            "ix_station_gaes_charge_station_year",
            TABLE,
            ["id_station", "year_number"],
            schema=SCHEMA_GEN,
        )
    stations_tbl = column_utils.gs_gen_stations_table_name(conn, SCHEMA_GEN)
    if stations_tbl is None:
        raise RuntimeError(f"Не найдена таблица станций в {SCHEMA_GEN} (gs_gen_stations / stations).")
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_gaes_charge_station"):
        op.create_foreign_key(
            "fk_station_gaes_charge_station",
            TABLE,
            stations_tbl,
            ["id_station"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_GEN,
            ondelete="RESTRICT",
        )
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_gaes_charge_database_version"):
        op.create_foreign_key(
            "fk_station_gaes_charge_database_version",
            TABLE,
            ref_versions,
            ["database_version_id"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )


def downgrade():
    op.drop_constraint(
        "fk_station_gaes_charge_database_version",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_station_gaes_charge_station",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_station_gaes_charge_station_year",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_index(
        "ix_station_gaes_charge_year_number",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_index(
        "ix_station_gaes_charge_id_station",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_table(TABLE, schema=SCHEMA_GEN)
