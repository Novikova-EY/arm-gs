"""subject_rf_to_regional_district_fk

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-03-19

Заменяет subject_rf (текст) на FK id_regional_district -> gs_regional_districts.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "r0s1t2u3v4w5"
down_revision = "q9r0s1t2u3v4"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "station_prospective_place_aes"
TABLE_RD = "gs_regional_districts"


def upgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    table_rd = column_utils.refdata_table_name(conn, SCHEMA_REF, TABLE_RD)
    if table is None or table_rd is None:
        return
    # 1. Добавляем колонку id_regional_district
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, "id_regional_district"):
        op.add_column(
            table,
            sa.Column("id_regional_district", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_prospective_place_aes_id_regional_district"):
        op.create_index(
            "ix_station_prospective_place_aes_id_regional_district",
            table,
            ["id_regional_district"],
            schema=SCHEMA_GEN,
        )

    # 2. Миграция данных: только если legacy-колонка subject_rf еще существует.
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, "subject_rf"):
        conn.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA_GEN}.{table} sppa
                SET id_regional_district = rd.id
                FROM {SCHEMA_REF}.{table_rd} rd
                WHERE sppa.subject_rf IS NOT NULL
                  AND TRIM(sppa.subject_rf) != ''
                  AND (rd.name_full = TRIM(sppa.subject_rf) OR rd.name = TRIM(sppa.subject_rf))
                """
            )
        )

    # 3. Создаем FK
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_prospective_place_aes_regional_district"):
        op.create_foreign_key(
            "fk_station_prospective_place_aes_regional_district",
            table,
            table_rd,
            ["id_regional_district"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )

    # 4. Удаляем subject_rf
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, "subject_rf"):
        op.drop_column(table, "subject_rf", schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    table = column_utils.station_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    table_rd = column_utils.refdata_table_name(conn, SCHEMA_REF, TABLE_RD)
    if table is None or table_rd is None:
        return
    # 1. Восстанавливаем subject_rf
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table, "subject_rf"):
        op.add_column(
            table,
            sa.Column("subject_rf", sa.String(length=255), nullable=True),
            schema=SCHEMA_GEN,
        )

    # 2. Заполняем subject_rf из regional_district перед удалением FK.
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, "id_regional_district"):
        conn.execute(
            sa.text(
                f"""
                UPDATE {SCHEMA_GEN}.{table} sppa
                SET subject_rf = rd.name_full
                FROM {SCHEMA_REF}.{table_rd} rd
                WHERE sppa.id_regional_district = rd.id
                """
            )
        )

    # 3. Удаляем FK и индекс
    if column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_prospective_place_aes_regional_district"):
        op.drop_constraint(
            "fk_station_prospective_place_aes_regional_district",
            table,
            schema=SCHEMA_GEN,
            type_="foreignkey",
        )
    if column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_prospective_place_aes_id_regional_district"):
        op.drop_index(
            "ix_station_prospective_place_aes_id_regional_district",
            table_name=table,
            schema=SCHEMA_GEN,
        )
    if column_utils.table_has_column(conn, SCHEMA_GEN, table, "id_regional_district"):
        op.drop_column(table, "id_regional_district", schema=SCHEMA_GEN)
