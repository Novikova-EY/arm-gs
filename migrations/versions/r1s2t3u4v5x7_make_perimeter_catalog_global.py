# -*- coding: utf-8 -*-
"""Сделать справочник вариантов периметра общим для всех версий БД.

Revision ID: r1s2t3u4v5x7
Revises: q1r2s3t4u5v7
Create Date: 2026-05-22
"""
from alembic import op
from sqlalchemy import text

revision = "r1s2t3u4v5x7"
down_revision = "q1r2s3t4u5v7"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_VARIANTS = "gs_sys_perimeter_variants"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"


def upgrade():
    conn = op.get_bind()

    conn.execute(
        text(
            f"""
            ALTER TABLE {SCHEMA_REF}.{TABLE_BINDINGS}
            DROP CONSTRAINT IF EXISTS uq_gs_sys_entity_perimeter_bindings_ver_entity_variant
            """
        )
    )
    conn.execute(
        text(
            f"""
            ALTER TABLE {SCHEMA_REF}.{TABLE_VARIANTS}
            DROP CONSTRAINT IF EXISTS uq_gs_sys_perimeter_variants_ver_code
            """
        )
    )

    conn.execute(
        text(
            f"""
            WITH canonical AS (
                SELECT
                    id,
                    first_value(id) OVER (
                        PARTITION BY code
                        ORDER BY (database_version_id IS NULL) DESC,
                                 display_order NULLS LAST,
                                 id
                    ) AS canonical_id
                FROM {SCHEMA_REF}.{TABLE_VARIANTS}
            )
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS} b
            SET id_perimeter_variant = c.canonical_id,
                database_version_id = NULL,
                modified_by = 'migration'
            FROM canonical c
            WHERE b.id_perimeter_variant = c.id
              AND b.id_perimeter_variant <> c.canonical_id
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
                        PARTITION BY entity_kind, entity_name, id_perimeter_variant
                        ORDER BY (database_version_id IS NULL) DESC,
                                 sort_order,
                                 id
                    ) AS rn
                FROM {SCHEMA_REF}.{TABLE_BINDINGS}
            )
            DELETE FROM {SCHEMA_REF}.{TABLE_BINDINGS} b
            USING ranked r
            WHERE b.id = r.id
              AND r.rn > 1
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
                        PARTITION BY code
                        ORDER BY (database_version_id IS NULL) DESC,
                                 display_order NULLS LAST,
                                 id
                    ) AS rn
                FROM {SCHEMA_REF}.{TABLE_VARIANTS}
            )
            DELETE FROM {SCHEMA_REF}.{TABLE_VARIANTS} v
            USING ranked r
            WHERE v.id = r.id
              AND r.rn > 1
            """
        )
    )

    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_VARIANTS}
            SET database_version_id = NULL,
                modified_by = 'migration'
            WHERE database_version_id IS NOT NULL
            """
        )
    )
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
            SET database_version_id = NULL,
                modified_by = 'migration'
            WHERE database_version_id IS NOT NULL
            """
        )
    )

    conn.execute(
        text(
            f"""
            ALTER TABLE {SCHEMA_REF}.{TABLE_VARIANTS}
            DROP CONSTRAINT IF EXISTS uq_gs_sys_perimeter_variants_code
            """
        )
    )
    conn.execute(
        text(
            f"""
            ALTER TABLE {SCHEMA_REF}.{TABLE_BINDINGS}
            DROP CONSTRAINT IF EXISTS uq_gs_sys_entity_perimeter_bindings_entity_variant
            """
        )
    )
    op.create_unique_constraint(
        "uq_gs_sys_perimeter_variants_code",
        TABLE_VARIANTS,
        ["code"],
        schema=SCHEMA_REF,
    )
    op.create_unique_constraint(
        "uq_gs_sys_entity_perimeter_bindings_entity_variant",
        TABLE_BINDINGS,
        ["entity_kind", "entity_name", "id_perimeter_variant"],
        schema=SCHEMA_REF,
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            ALTER TABLE {SCHEMA_REF}.{TABLE_BINDINGS}
            DROP CONSTRAINT IF EXISTS uq_gs_sys_entity_perimeter_bindings_entity_variant
            """
        )
    )
    conn.execute(
        text(
            f"""
            ALTER TABLE {SCHEMA_REF}.{TABLE_VARIANTS}
            DROP CONSTRAINT IF EXISTS uq_gs_sys_perimeter_variants_code
            """
        )
    )
    op.create_unique_constraint(
        "uq_gs_sys_perimeter_variants_ver_code",
        TABLE_VARIANTS,
        ["database_version_id", "code"],
        schema=SCHEMA_REF,
    )
    op.create_unique_constraint(
        "uq_gs_sys_entity_perimeter_bindings_ver_entity_variant",
        TABLE_BINDINGS,
        ["database_version_id", "entity_kind", "entity_name", "id_perimeter_variant"],
        schema=SCHEMA_REF,
    )
