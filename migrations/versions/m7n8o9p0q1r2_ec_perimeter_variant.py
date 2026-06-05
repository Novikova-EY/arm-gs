# -*- coding: utf-8 -*-
"""Потребление (gs_ec): perimeter_variant_code; слияние with_nt-таблиц; привязки ОЭС Юга / Южный ФО / ЕЭС России.

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-05-21
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

revision = "m7n8o9p0q1r2"
down_revision = "l6m7n8o9p0q1"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REF = "gs_sys"
TABLE_EES = "gs_ec_ees_russia_consumption_params"
TABLE_EES_NT = "gs_ec_ees_russia_with_nt_consumption_params"
TABLE_RU = "gs_ec_russia_federation_consumption_params"
TABLE_RU_NT = "gs_ec_russia_federation_with_nt_consumption_params"
TABLE_UES = "gs_ec_union_energy_system_consumption_params"
TABLE_FD = "gs_ec_federal_district_consumption_params"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"
UES_TABLE = "gs_sys_union_energy_systems"
FD_TABLE = "gs_sys_federal_districts"

CODE_WITH_NT = "with_nt"
CODE_WITHOUT_NT = "without_nt"
SOUTH_UES_NAME = "ОЭС Юга"
SOUTH_FD_NAME = "Южный ФО"


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table AND column_name = :col"
        ),
        {"schema": schema, "table": table, "col": column},
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


def _drop_ec_unique_indexes(conn, table: str) -> None:
    for suffix in ("year", "nullyear"):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_EC}"."uq_gs_ec_{table.replace("gs_ec_", "").replace("_consumption_params", "")[:24]}_{suffix}"'))
    pfx = table.replace("gs_ec_", "").replace("_consumption_params", "")[:24]
    for ix in (
        f"uq_gs_ec_{pfx}_year",
        f"uq_gs_ec_{pfx}_nullyear",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA_EC}"."{ix}"'))


def _add_pvc_column(conn, table: str, index_name: str) -> None:
    if not _table_exists(conn, SCHEMA_EC, table):
        return
    if not _column_exists(conn, SCHEMA_EC, table, "perimeter_variant_code"):
        op.add_column(
            table,
            sa.Column("perimeter_variant_code", sa.String(64), nullable=True),
            schema=SCHEMA_EC,
        )
        op.create_index(
            index_name,
            table,
            ["perimeter_variant_code"],
            unique=False,
            schema=SCHEMA_EC,
        )


def _dedupe_ec_rows(conn, table: str, fk_col: str | None = None) -> None:
    """Удаляет дубликаты перед UNIQUE INDEX (данные могли существовать до индексов или после слияния)."""
    fk_part = f"{fk_col}, " if fk_col else ""
    conn.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY {fk_part}year_number,
                            COALESCE(database_version_id, 0),
                            COALESCE(perimeter_variant_code, '')
                        ORDER BY id DESC
                    ) AS rn
                FROM {SCHEMA_EC}.{table}
                WHERE year_number IS NOT NULL
            )
            DELETE FROM {SCHEMA_EC}.{table} t
            USING ranked r
            WHERE t.id = r.id AND r.rn > 1
            """
        )
    )
    conn.execute(
        text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY {fk_part}COALESCE(database_version_id, 0),
                            COALESCE(perimeter_variant_code, '')
                        ORDER BY id DESC
                    ) AS rn
                FROM {SCHEMA_EC}.{table}
                WHERE year_number IS NULL
            )
            DELETE FROM {SCHEMA_EC}.{table} t
            USING ranked r
            WHERE t.id = r.id AND r.rn > 1
            """
        )
    )


def _assign_south_entity_perimeter_codes(
    conn,
    table: str,
    fk_col: str,
    ref_table: str,
    south_name: str,
) -> None:
    """Южные сущности: две строки на год без колонки → without_nt и with_nt (не обе without_nt)."""
    conn.execute(
        text(
            f"""
            WITH south_rows AS (
                SELECT
                    p.id,
                    row_number() OVER (
                        PARTITION BY p.{fk_col},
                            COALESCE(p.year_number, -1),
                            COALESCE(p.database_version_id, 0)
                        ORDER BY p.id
                    ) AS rn
                FROM {SCHEMA_EC}.{table} AS p
                INNER JOIN {SCHEMA_REF}.{ref_table} AS r ON p.{fk_col} = r.id
                WHERE lower(trim(r.name)) = lower(:south_name)
                  AND p.perimeter_variant_code IS NULL
            )
            UPDATE {SCHEMA_EC}.{table} AS t
            SET perimeter_variant_code = CASE
                WHEN s.rn = 1 THEN :without_nt
                WHEN s.rn = 2 THEN :with_nt
                ELSE :without_nt
            END
            FROM south_rows AS s
            WHERE t.id = s.id
            """
        ),
        {
            "south_name": south_name,
            "without_nt": CODE_WITHOUT_NT,
            "with_nt": CODE_WITH_NT,
        },
    )


def _reconcile_south_collapsed_variants(
    conn,
    table: str,
    fk_col: str,
    ref_table: str,
    south_name: str,
) -> None:
    """Повторный прогон: две строки с одним without_nt → вторая становится with_nt."""
    conn.execute(
        text(
            f"""
            WITH south_rows AS (
                SELECT
                    p.id,
                    count(*) OVER (
                        PARTITION BY p.{fk_col},
                            COALESCE(p.year_number, -1),
                            COALESCE(p.database_version_id, 0)
                    ) AS grp_cnt,
                    row_number() OVER (
                        PARTITION BY p.{fk_col},
                            COALESCE(p.year_number, -1),
                            COALESCE(p.database_version_id, 0)
                        ORDER BY p.id
                    ) AS rn
                FROM {SCHEMA_EC}.{table} AS p
                INNER JOIN {SCHEMA_REF}.{ref_table} AS r ON p.{fk_col} = r.id
                WHERE lower(trim(r.name)) = lower(:south_name)
            )
            UPDATE {SCHEMA_EC}.{table} AS t
            SET perimeter_variant_code = :with_nt
            FROM south_rows AS s
            WHERE t.id = s.id
              AND s.grp_cnt > 1
              AND s.rn = 2
              AND COALESCE(t.perimeter_variant_code, '') = :without_nt
            """
        ),
        {
            "south_name": south_name,
            "with_nt": CODE_WITH_NT,
            "without_nt": CODE_WITHOUT_NT,
        },
    )


def _set_default_without_nt(conn, table: str) -> None:
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_EC}.{table}
            SET perimeter_variant_code = :code
            WHERE perimeter_variant_code IS NULL
            """
        ),
        {"code": CODE_WITHOUT_NT},
    )


def _merge_nt_table(conn, main_table: str, nt_table: str) -> None:
    if not _table_exists(conn, SCHEMA_EC, main_table):
        return
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_EC}.{main_table}
            SET perimeter_variant_code = :code
            WHERE perimeter_variant_code IS NULL
            """
        ),
        {"code": CODE_WITHOUT_NT},
    )
    if _table_exists(conn, SCHEMA_EC, nt_table):
        conn.execute(
            text(
                f"""
                INSERT INTO {SCHEMA_EC}.{main_table} (
                    year_number,
                    energy_consumption_mln_kvt_ch, energy_consumption_sipr_mln_kvt_ch,
                    note, database_version_id, created_by, modified_by,
                    created_at, updated_at, perimeter_variant_code
                )
                SELECT
                    s.year_number,
                    s.energy_consumption_mln_kvt_ch, s.energy_consumption_sipr_mln_kvt_ch,
                    s.note, s.database_version_id, s.created_by, s.modified_by,
                    s.created_at, s.updated_at, :code
                FROM {SCHEMA_EC}.{nt_table} s
                WHERE NOT EXISTS (
                    SELECT 1 FROM {SCHEMA_EC}.{main_table} t
                    WHERE t.perimeter_variant_code = :code
                      AND t.database_version_id IS NOT DISTINCT FROM s.database_version_id
                      AND t.year_number IS NOT DISTINCT FROM s.year_number
                )
                """
            ),
            {"code": CODE_WITH_NT},
        )
        op.drop_table(nt_table, schema=SCHEMA_EC)


def _rebuild_no_fk_indexes(conn, table: str, pfx: str) -> None:
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_year
            ON "{SCHEMA_EC}"."{table}" (
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_nullyear
            ON "{SCHEMA_EC}"."{table}" (
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NULL
            """
        )
    )


def _rebuild_fk_indexes(conn, table: str, fk_col: str, pfx: str) -> None:
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_year
            ON "{SCHEMA_EC}"."{table}" (
                {fk_col},
                year_number,
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_ec_{pfx}_nullyear
            ON "{SCHEMA_EC}"."{table}" (
                {fk_col},
                COALESCE(database_version_id, 0),
                COALESCE(perimeter_variant_code, '')
            )
            WHERE year_number IS NULL
            """
        )
    )


def _seed_bindings(conn) -> None:
    if not _table_exists(conn, SCHEMA_REF, TABLE_VARIANTS):
        return
    versions = conn.execute(
        text(f"SELECT id FROM {SCHEMA_REF}.gs_database_versions")
    ).fetchall()
    seeds = (
        ("federal_district", SOUTH_FD_NAME, "Южный ФО", CODE_WITH_NT, 0),
        ("federal_district", SOUTH_FD_NAME, "Южный ФО", CODE_WITHOUT_NT, 1),
        ("union_energy_system", SOUTH_UES_NAME, "ОЭС Юга", CODE_WITH_NT, 0),
        ("union_energy_system", SOUTH_UES_NAME, "ОЭС Юга", CODE_WITHOUT_NT, 1),
        ("energy_system_type", "ЕЭС России", "ЕЭС России", CODE_WITH_NT, 0),
        ("energy_system_type", "ЕЭС России", "ЕЭС России", CODE_WITHOUT_NT, 1),
    )
    for (vid_row,) in versions:
        vid = int(vid_row)
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
        for ek, en, prefix, vcode, sort_o in seeds:
            dup = conn.execute(
                text(
                    f"SELECT 1 FROM {SCHEMA_REF}.{TABLE_BINDINGS} "
                    "WHERE database_version_id = :vid AND entity_kind = :ek "
                    "AND entity_name = :en AND id_perimeter_variant = :pvid LIMIT 1"
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


def upgrade():
    conn = op.get_bind()

    for table, nt_table, pfx in (
        (TABLE_EES, TABLE_EES_NT, "ees_russia"),
        (TABLE_RU, TABLE_RU_NT, "russia_federation"),
    ):
        if not _table_exists(conn, SCHEMA_EC, table):
            continue
        _drop_ec_unique_indexes(conn, table)
        _add_pvc_column(conn, table, f"ix_gs_ec_{pfx}_pvc")
        _merge_nt_table(conn, table, nt_table)
        _dedupe_ec_rows(conn, table)
        _rebuild_no_fk_indexes(conn, table, pfx)

    if _table_exists(conn, SCHEMA_EC, TABLE_UES):
        _drop_ec_unique_indexes(conn, TABLE_UES)
        _add_pvc_column(conn, TABLE_UES, "ix_gs_ec_union_energy_system_pvc")
        _assign_south_entity_perimeter_codes(
            conn,
            TABLE_UES,
            "id_union_energy_system",
            UES_TABLE,
            SOUTH_UES_NAME,
        )
        _set_default_without_nt(conn, TABLE_UES)
        _reconcile_south_collapsed_variants(
            conn,
            TABLE_UES,
            "id_union_energy_system",
            UES_TABLE,
            SOUTH_UES_NAME,
        )
        _dedupe_ec_rows(conn, TABLE_UES, "id_union_energy_system")
        _rebuild_fk_indexes(conn, TABLE_UES, "id_union_energy_system", "union_energy_system")

    if _table_exists(conn, SCHEMA_EC, TABLE_FD):
        _drop_ec_unique_indexes(conn, TABLE_FD)
        _add_pvc_column(conn, TABLE_FD, "ix_gs_ec_federal_district_pvc")
        _assign_south_entity_perimeter_codes(
            conn,
            TABLE_FD,
            "id_federal_district",
            FD_TABLE,
            SOUTH_FD_NAME,
        )
        _set_default_without_nt(conn, TABLE_FD)
        _reconcile_south_collapsed_variants(
            conn,
            TABLE_FD,
            "id_federal_district",
            FD_TABLE,
            SOUTH_FD_NAME,
        )
        _dedupe_ec_rows(conn, TABLE_FD, "id_federal_district")
        _rebuild_fk_indexes(conn, TABLE_FD, "id_federal_district", "federal_district")

    _seed_bindings(conn)


def downgrade():
    pass
