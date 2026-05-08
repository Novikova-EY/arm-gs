"""station_ges_id_prospective_place_type

Revision ID: b3c4d5e6f7a9
Revises: a1b2c3d4e5f7
Create Date: 2026-03-30

Тип площадки ГЭС на уровне площадки (station_prospective_place_ges);
значение переносится из первой связанной записи ТЭП при обновлении.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


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
    conn = op.get_bind()
    table_station_ges = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    table_tep = column_utils.ges_tep_source_project_indicators_table_name(conn, SCHEMA_GEN)
    table_types_ges = column_utils.prospective_place_types_ges_table_name(conn, SCHEMA_REF)
    if table_station_ges is None or table_tep is None or table_types_ges is None:
        return
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table_station_ges, "id_prospective_place_type_ges"):
        op.add_column(
            table_station_ges,
            sa.Column("id_prospective_place_type_ges", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_ges_id_prospective_place_type_ges"):
        op.create_foreign_key(
            "fk_station_ges_id_prospective_place_type_ges",
            table_station_ges,
            table_types_ges,
            ["id_prospective_place_type_ges"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="SET NULL",
        )
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_prospective_place_ges_id_prospective_place_type_ges"):
        op.create_index(
            "ix_station_prospective_place_ges_id_prospective_place_type_ges",
            table_station_ges,
            ["id_prospective_place_type_ges"],
            schema=SCHEMA_GEN,
        )

    # Перенос из первой по id записи ТЭП с непустым типом (PostgreSQL DISTINCT ON)
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_GEN}.{table_station_ges} AS s
            SET id_prospective_place_type_ges = x.id_prospective_place_type_ges
            FROM (
              SELECT DISTINCT ON (id_station_prospective_place_ges)
                id_station_prospective_place_ges,
                id_prospective_place_type_ges
              FROM {SCHEMA_GEN}.{table_tep}
              WHERE id_prospective_place_type_ges IS NOT NULL
              ORDER BY id_station_prospective_place_ges, id
            ) AS x
            WHERE s.id = x.id_station_prospective_place_ges
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    table_station_ges = column_utils.station_prospective_place_ges_table_name(conn, SCHEMA_GEN)
    if table_station_ges is None:
        return
    if column_utils.index_exists(conn, SCHEMA_GEN, "ix_station_prospective_place_ges_id_prospective_place_type_ges"):
        op.drop_index(
            "ix_station_prospective_place_ges_id_prospective_place_type_ges",
            table_name=table_station_ges,
            schema=SCHEMA_GEN,
        )
    if column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_station_ges_id_prospective_place_type_ges"):
        op.drop_constraint(
            "fk_station_ges_id_prospective_place_type_ges",
            table_station_ges,
            schema=SCHEMA_GEN,
            type_="foreignkey",
        )
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_station_ges, "id_prospective_place_type_ges"):
        op.drop_column(
            table_station_ges,
            "id_prospective_place_type_ges",
            schema=SCHEMA_GEN,
        )
