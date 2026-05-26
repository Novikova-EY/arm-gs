# -*- coding: utf-8 -*-
"""Одна таблица параметров РФ с perimeter_variant_code; перенос данных из with_nt; удаление второй таблицы.

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m8n9o0
Create Date: 2026-05-20
"""
import os
import sys
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "k5l6m7n8o9p0"
down_revision = "j4k5l6m8n9o0"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"
SCHEMA_REF = "gs_sys"
TABLE = "gs_pd_russia_federation_demand_params"
TABLE_NT = "gs_pd_russia_federation_with_nt_demand_params"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"

CODE_WITH_NT = "with_nt"
CODE_WITHOUT_NT = "without_nt"


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": SCHEMA_PD, "table": table, "col": column},
    )
    return r.fetchone() is not None


def _table_exists(conn, schema: str, table: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM pg_tables WHERE schemaname = :schema AND tablename = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, SCHEMA_PD, TABLE):
        return

    if not _column_exists(conn, TABLE, "perimeter_variant_code"):
        op.add_column(
            TABLE,
            sa.Column("perimeter_variant_code", sa.String(64), nullable=True),
            schema=SCHEMA_PD,
        )
        op.create_index(
            "ix_gs_pd_russia_federation_demand_params_pvc",
            TABLE,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_PD,
        )

    for ix in (
        "uq_russia_federation_demand_params_hist",
        "uq_russia_federation_demand_params_year",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_PD}"."{ix}"'))

    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_PD}.{TABLE}
            SET perimeter_variant_code = :code
            WHERE perimeter_variant_code IS NULL
            """
        ),
        {"code": CODE_WITHOUT_NT},
    )

    if _table_exists(conn, SCHEMA_PD, TABLE_NT):
        conn.execute(
            text(
                f"""
                INSERT INTO {SCHEMA_PD}.{TABLE} (
                    is_historical_maximum, year_number,
                    max_power_consumption_mw, peak_datetime_msk, avg_daily_air_temp_c,
                    note, database_version_id, created_by, modified_by,
                    created_at, updated_at, perimeter_variant_code
                )
                SELECT
                    s.is_historical_maximum, s.year_number,
                    s.max_power_consumption_mw, s.peak_datetime_msk, s.avg_daily_air_temp_c,
                    s.note, s.database_version_id, s.created_by, s.modified_by,
                    s.created_at, s.updated_at, :code
                FROM {SCHEMA_PD}.{TABLE_NT} s
                WHERE NOT EXISTS (
                    SELECT 1 FROM {SCHEMA_PD}.{TABLE} t
                    WHERE t.perimeter_variant_code = :code
                      AND t.database_version_id IS NOT DISTINCT FROM s.database_version_id
                      AND t.is_historical_maximum = s.is_historical_maximum
                      AND t.year_number IS NOT DISTINCT FROM s.year_number
                )
                """
            ),
            {"code": CODE_WITH_NT},
        )
        op.drop_table(TABLE_NT, schema=SCHEMA_PD)

    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_russia_federation_demand_params_hist
            ON "{SCHEMA_PD}"."{TABLE}" (
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = true
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_pd_russia_federation_demand_params_year
            ON "{SCHEMA_PD}"."{TABLE}" (
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE is_historical_maximum = false
            """
        )
    )

    if not _table_exists(conn, SCHEMA_REF, TABLE_VARIANTS):
        return

    versions = conn.execute(
        text(f"SELECT id FROM {SCHEMA_REF}.gs_database_versions")
    ).fetchall()
    for (vid_row,) in versions:
        vid = int(vid_row)
        exists = conn.execute(
            text(
                f"SELECT 1 FROM {SCHEMA_REF}.{TABLE_BINDINGS} "
                "WHERE database_version_id = :vid AND entity_kind = 'russia' LIMIT 1"
            ),
            {"vid": vid},
        ).fetchone()
        if exists:
            continue
        codes = conn.execute(
            text(
                f"SELECT id, code FROM {SCHEMA_REF}.{TABLE_VARIANTS} "
                "WHERE database_version_id = :vid AND code IN (:c1, :c2)"
            ),
            {"vid": vid, "c1": CODE_WITH_NT, "c2": CODE_WITHOUT_NT},
        ).fetchall()
        code_to_id = {str(c): int(i) for i, c in codes}
        if CODE_WITH_NT not in code_to_id or CODE_WITHOUT_NT not in code_to_id:
            continue
        for ek, en, prefix, vcode, sort_o in (
            ("russia", "Россия", "Россия", CODE_WITH_NT, 0),
            ("russia", "Россия", "Россия", CODE_WITHOUT_NT, 1),
        ):
            dup = conn.execute(
                text(
                    f"SELECT 1 FROM {SCHEMA_REF}.{TABLE_BINDINGS} "
                    "WHERE database_version_id = :vid AND entity_kind = :ek AND entity_name = :en "
                    "AND id_perimeter_variant = :pvid LIMIT 1"
                ),
                {"vid": vid, "ek": ek, "en": en, "pvid": code_to_id[vcode]},
            ).fetchone()
            if dup:
                continue
            conn.execute(
                text(
                    f"""
                    INSERT INTO {SCHEMA_REF}.{TABLE_BINDINGS}
                    (entity_kind, entity_name, label_prefix, sort_order, id_perimeter_variant,
                     ref_uuid, version, database_version_id, created_by, modified_by)
                    VALUES (:ek, :en, :prefix, :sort, :pvid, :ruuid, 1, :dbvid, 'migration', 'migration')
                    """
                ),
                {
                    "ek": ek,
                    "en": en,
                    "prefix": prefix,
                    "sort": sort_o,
                    "pvid": code_to_id[vcode],
                    "ruuid": str(uuid.uuid4()),
                    "dbvid": vid,
                },
            )


def downgrade():
    pass
