# -*- coding: utf-8 -*-
"""Drop gs_gen.gs_gen_station_powers — мощности станции считаются из MachinePower.

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-07-21
"""
from alembic import op
from sqlalchemy import text

revision = "t5u6v7w8x9y0"
down_revision = "s4t5u6v7w8x9"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "gs_gen_station_powers"


def upgrade():
    conn = op.get_bind()
    # Drop dependent indexes/constraints via DROP TABLE CASCADE.
    conn.execute(
        text(
            f"""
            DROP TABLE IF EXISTS {SCHEMA_GEN}.{TABLE} CASCADE
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA_GEN}.{TABLE} (
                id SERIAL PRIMARY KEY,
                year_number INTEGER REFERENCES gs_sys.gs_sys_years(number) ON DELETE RESTRICT,
                id_station INTEGER REFERENCES {SCHEMA_GEN}.gs_gen_stations(id) ON DELETE RESTRICT,
                p_ust NUMERIC(25, 16),
                p_ogr NUMERIC(25, 16),
                p_rasp NUMERIC(25, 16),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                database_version_id INTEGER
                    REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_station_power_id_station
                ON {SCHEMA_GEN}.{TABLE} (id_station)
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_station_power_year_number
                ON {SCHEMA_GEN}.{TABLE} (year_number)
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_station_powers_station_year
                ON {SCHEMA_GEN}.{TABLE} (id_station, year_number)
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_{TABLE}_database_version_id
                ON {SCHEMA_GEN}.{TABLE} (database_version_id)
            """
        )
    )
