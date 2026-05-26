# -*- coding: utf-8 -*-
"""Привязки периметра: entity_kind агрегатов по префиксам моделей.

- russia → russia_federation
- energy_system_type + «ЭЭС России» (агрегат, ошибочно заведённый как ЕЭС) → ees_russia
- energy_system_type + «ЭЭС России» (справочник) — не трогаем

Revision ID: q1r2s3t4u5v7
Revises: p0q1r2s3t4u6
Create Date: 2026-05-22
"""
from alembic import op
from sqlalchemy import text

revision = "q1r2s3t4u5v7"
down_revision = "p0q1r2s3t4u6"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_BINDINGS = "gs_sys_entity_perimeter_bindings"

# Каноническое имя агрегата ЭЭС (электроэнергетические системы России).
_EES_RUSSIA_AGGREGATE_NAME = "ЭЭС России"
# Опечатка «ЕЭС» в старых сидах (l6/m7) — те же привязки агрегата, не справочник ЕЭС.
_LEGACY_EES_AGGREGATE_NAMES = ("ЕЭС России", "ЭЭС России")


def upgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
            SET entity_kind = 'russia_federation',
                modified_by = 'migration'
            WHERE entity_kind = 'russia'
            """
        )
    )
    # Уже переименованные подписи (o9p0q1r2s3t4): только смена entity_kind.
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
            SET entity_kind = 'ees_russia',
                modified_by = 'migration'
            WHERE entity_kind = 'energy_system_type'
              AND lower(trim(entity_name)) = lower(:canonical)
            """
        ),
        {"canonical": _EES_RUSSIA_AGGREGATE_NAME},
    )
    # Старые сиды: energy_system_type + «ЕЭС России» (агрегат с опечаткой) → ees_russia + каноническое «ЭЭС».
    for legacy_name in _LEGACY_EES_AGGREGATE_NAMES:
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
                SET entity_kind = 'ees_russia',
                    entity_name = :canonical,
                    label_prefix = :canonical,
                    modified_by = 'migration'
                WHERE entity_kind = 'energy_system_type'
                  AND entity_name = :legacy
                """
            ),
            {"canonical": _EES_RUSSIA_AGGREGATE_NAME, "legacy": legacy_name},
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
            SET entity_kind = 'russia',
                modified_by = 'migration'
            WHERE entity_kind = 'russia_federation'
            """
        )
    )
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_REF}.{TABLE_BINDINGS}
            SET entity_kind = 'energy_system_type',
                modified_by = 'migration'
            WHERE entity_kind = 'ees_russia'
              AND lower(trim(entity_name)) = lower(:canonical)
            """
        ),
        {"canonical": _EES_RUSSIA_AGGREGATE_NAME},
    )
