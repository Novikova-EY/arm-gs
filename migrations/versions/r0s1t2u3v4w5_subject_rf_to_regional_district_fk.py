"""subject_rf_to_regional_district_fk

Revision ID: r0s1t2u3v4w5
Revises: q9r0s1t2u3v4
Create Date: 2026-03-19

Заменяет subject_rf (текст) на FK id_regional_district -> gs_regional_districts.
"""
from alembic import op
import sqlalchemy as sa


revision = "r0s1t2u3v4w5"
down_revision = "q9r0s1t2u3v4"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE = "station_prospective_place_aes"
TABLE_RD = "gs_regional_districts"


def upgrade():
    # 1. Добавляем колонку id_regional_district
    op.add_column(
        TABLE,
        sa.Column("id_regional_district", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_station_prospective_place_aes_id_regional_district",
        TABLE,
        ["id_regional_district"],
        schema=SCHEMA_GEN,
    )

    # 2. Миграция данных: сопоставляем subject_rf с name_full/name из gs_regional_districts
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_GEN}.{TABLE} sppa
            SET id_regional_district = rd.id
            FROM {SCHEMA_REF}.{TABLE_RD} rd
            WHERE sppa.subject_rf IS NOT NULL
              AND TRIM(sppa.subject_rf) != ''
              AND (rd.name_full = TRIM(sppa.subject_rf) OR rd.name = TRIM(sppa.subject_rf))
            """
        )
    )

    # 3. Создаем FK
    op.create_foreign_key(
        "fk_station_prospective_place_aes_regional_district",
        TABLE,
        TABLE_RD,
        ["id_regional_district"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )

    # 4. Удаляем subject_rf
    op.drop_column(TABLE, "subject_rf", schema=SCHEMA_GEN)


def downgrade():
    # 1. Восстанавливаем subject_rf
    op.add_column(
        TABLE,
        sa.Column("subject_rf", sa.String(length=255), nullable=True),
        schema=SCHEMA_GEN,
    )

    # 2. Заполняем subject_rf из regional_district перед удалением FK
    conn = op.get_bind()
    conn.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_GEN}.{TABLE} sppa
            SET subject_rf = rd.name_full
            FROM {SCHEMA_REF}.{TABLE_RD} rd
            WHERE sppa.id_regional_district = rd.id
            """
        )
    )

    # 3. Удаляем FK и индекс
    op.drop_constraint(
        "fk_station_prospective_place_aes_regional_district",
        TABLE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_station_prospective_place_aes_id_regional_district",
        table_name=TABLE,
        schema=SCHEMA_GEN,
    )
    op.drop_column(TABLE, "id_regional_district", schema=SCHEMA_GEN)
