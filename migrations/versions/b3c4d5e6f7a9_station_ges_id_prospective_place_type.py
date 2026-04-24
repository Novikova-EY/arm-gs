"""station_ges_id_prospective_place_type

Revision ID: b3c4d5e6f7a9
Revises: a1b2c3d4e5f7
Create Date: 2026-03-30

Тип площадки ГЭС на уровне площадки (station_prospective_place_ges);
значение переносится из первой связанной записи ТЭП при обновлении.
"""
from alembic import op
import sqlalchemy as sa


revision = "b3c4d5e6f7a9"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"

TABLE_STATION_GES = "station_prospective_place_ges"
TABLE_TEP = "ges_tep_source_project_indicators"
TABLE_TYPES_GES = "gs_prospective_place_types_ges"


def upgrade():
    op.add_column(
        TABLE_STATION_GES,
        sa.Column("id_prospective_place_type_ges", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.create_foreign_key(
        "fk_station_ges_id_prospective_place_type_ges",
        TABLE_STATION_GES,
        TABLE_TYPES_GES,
        ["id_prospective_place_type_ges"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_station_prospective_place_ges_id_prospective_place_type_ges",
        TABLE_STATION_GES,
        ["id_prospective_place_type_ges"],
        schema=SCHEMA_GEN,
    )

    # Перенос из первой по id записи ТЭП с непустым типом (PostgreSQL DISTINCT ON)
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_GEN}.{TABLE_STATION_GES} AS s
            SET id_prospective_place_type_ges = x.id_prospective_place_type_ges
            FROM (
              SELECT DISTINCT ON (id_station_prospective_place_ges)
                id_station_prospective_place_ges,
                id_prospective_place_type_ges
              FROM {SCHEMA_GEN}.{TABLE_TEP}
              WHERE id_prospective_place_type_ges IS NOT NULL
              ORDER BY id_station_prospective_place_ges, id
            ) AS x
            WHERE s.id = x.id_station_prospective_place_ges
            """
        )
    )


def downgrade():
    op.drop_index(
        "ix_station_prospective_place_ges_id_prospective_place_type_ges",
        table_name=TABLE_STATION_GES,
        schema=SCHEMA_GEN,
    )
    op.drop_constraint(
        "fk_station_ges_id_prospective_place_type_ges",
        TABLE_STATION_GES,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_column(
        TABLE_STATION_GES,
        "id_prospective_place_type_ges",
        schema=SCHEMA_GEN,
    )
