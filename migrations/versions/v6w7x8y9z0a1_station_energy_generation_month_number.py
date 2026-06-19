# -*- coding: utf-8 -*-
"""Выработка электростанции: хранение по годам и месяцам (month_number).

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
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

revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "gs_gen_station_energy_generations"
OLD_UNIQUE_INDEX = "uq_station_energy_gen_station_year_ver"
NEW_UNIQUE_INDEX = "uq_station_energy_gen_station_year_month_ver"
OLD_STATION_YEAR_INDEX = "ix_station_energy_gen_station_year"
NEW_STATION_YEAR_MONTH_INDEX = "ix_station_energy_gen_station_year_month"
MONTH_INDEX = "ix_station_energy_gen_month_number"

# 0 — годовое значение («год»); 1–12 — номер месяца
PERIOD_YEAR = 0


def upgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        return

    if not column_utils.table_has_column(conn, SCHEMA_GEN, TABLE, "month_number"):
        op.add_column(
            TABLE,
            sa.Column(
                "month_number",
                sa.Integer(),
                nullable=False,
                server_default=sa.text(str(PERIOD_YEAR)),
            ),
            schema=SCHEMA_GEN,
        )

    op.execute(
        text(
            f"""
            UPDATE "{SCHEMA_GEN}"."{TABLE}"
            SET month_number = {PERIOD_YEAR}
            WHERE month_number IS NULL
            """
        )
    )

    if column_utils.index_exists(conn, SCHEMA_GEN, OLD_UNIQUE_INDEX):
        op.drop_index(OLD_UNIQUE_INDEX, table_name=TABLE, schema=SCHEMA_GEN)

    if not column_utils.index_exists(conn, SCHEMA_GEN, NEW_UNIQUE_INDEX):
        op.execute(
            text(
                f"""
                CREATE UNIQUE INDEX {NEW_UNIQUE_INDEX}
                ON "{SCHEMA_GEN}"."{TABLE}" (
                    id_station,
                    year_number,
                    month_number,
                    COALESCE(database_version_id, -1)
                )
                """
            )
        )

    if column_utils.index_exists(conn, SCHEMA_GEN, OLD_STATION_YEAR_INDEX):
        op.drop_index(OLD_STATION_YEAR_INDEX, table_name=TABLE, schema=SCHEMA_GEN)

    if not column_utils.index_exists(conn, SCHEMA_GEN, NEW_STATION_YEAR_MONTH_INDEX):
        op.create_index(
            NEW_STATION_YEAR_MONTH_INDEX,
            TABLE,
            ["id_station", "year_number", "month_number"],
            unique=False,
            schema=SCHEMA_GEN,
        )

    if not column_utils.index_exists(conn, SCHEMA_GEN, MONTH_INDEX):
        op.create_index(
            MONTH_INDEX,
            TABLE,
            ["month_number"],
            unique=False,
            schema=SCHEMA_GEN,
        )


def downgrade():
    conn = op.get_bind()
    if not column_utils.table_exists(conn, SCHEMA_GEN, TABLE):
        return

    if column_utils.index_exists(conn, SCHEMA_GEN, MONTH_INDEX):
        op.drop_index(MONTH_INDEX, table_name=TABLE, schema=SCHEMA_GEN)

    if column_utils.index_exists(conn, SCHEMA_GEN, NEW_STATION_YEAR_MONTH_INDEX):
        op.drop_index(
            NEW_STATION_YEAR_MONTH_INDEX,
            table_name=TABLE,
            schema=SCHEMA_GEN,
        )

    if not column_utils.index_exists(conn, SCHEMA_GEN, OLD_STATION_YEAR_INDEX):
        op.create_index(
            OLD_STATION_YEAR_INDEX,
            TABLE,
            ["id_station", "year_number"],
            unique=False,
            schema=SCHEMA_GEN,
        )

    if column_utils.index_exists(conn, SCHEMA_GEN, NEW_UNIQUE_INDEX):
        op.drop_index(NEW_UNIQUE_INDEX, table_name=TABLE, schema=SCHEMA_GEN)

    dup_rows = conn.execute(
        text(
            f"""
            SELECT id_station, year_number, COALESCE(database_version_id, -1) AS ver_key
            FROM "{SCHEMA_GEN}"."{TABLE}"
            GROUP BY id_station, year_number, COALESCE(database_version_id, -1)
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    if dup_rows:
        raise RuntimeError(
            "Откат невозможен: есть несколько строк с разными month_number "
            "для одной пары (электростанция, год, версия БД). "
            "Удалите месячные строки вручную."
        )

    if not column_utils.index_exists(conn, SCHEMA_GEN, OLD_UNIQUE_INDEX):
        op.execute(
            text(
                f"""
                CREATE UNIQUE INDEX {OLD_UNIQUE_INDEX}
                ON "{SCHEMA_GEN}"."{TABLE}" (
                    id_station,
                    year_number,
                    COALESCE(database_version_id, -1)
                )
                """
            )
        )

    if column_utils.table_has_column(conn, SCHEMA_GEN, TABLE, "month_number"):
        op.drop_column(TABLE, "month_number", schema=SCHEMA_GEN)
