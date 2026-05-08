"""add_external_code_to_prospective_places

Revision ID: c8d9e0f1a2b3
Revises: b2c3d4e5f6z0
Create Date: 2026-05-08

Добавляет external_code в таблицы перспективных площадок для связи
с логической электростанцией (Station.external_code) в рамках версии БД.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "c8d9e0f1a2b3"
down_revision = "b2c3d4e5f6z0"
branch_labels = None
depends_on = None

SCHEMA = "gs_gen"
COLUMN = "external_code"
TABLES = (
    (
        column_utils.station_prospective_place_aes_table_name,
        "ix_station_prospective_place_aes_external_code",
    ),
    (
        column_utils.station_prospective_place_ges_table_name,
        "ix_station_prospective_place_ges_external_code",
    ),
    (
        column_utils.station_prospective_place_gaes_table_name,
        "ix_station_prospective_place_gaes_external_code",
    ),
)


def upgrade():
    conn = op.get_bind()

    for table_name_resolver, index_name in TABLES:
        table = table_name_resolver(conn, SCHEMA)
        if not table:
            continue

        if not column_utils.table_has_column(conn, SCHEMA, table, COLUMN):
            op.add_column(
                table,
                sa.Column(COLUMN, sa.String(36), nullable=True),
                schema=SCHEMA,
            )

        if not column_utils.index_exists(conn, SCHEMA, index_name):
            op.create_index(
                index_name,
                table,
                [COLUMN],
                schema=SCHEMA,
            )


def downgrade():
    conn = op.get_bind()

    for table_name_resolver, index_name in TABLES:
        table = table_name_resolver(conn, SCHEMA)
        if not table:
            continue

        if column_utils.index_exists(conn, SCHEMA, index_name):
            op.drop_index(index_name, table_name=table, schema=SCHEMA)

        if column_utils.table_has_column(conn, SCHEMA, table, COLUMN):
            op.drop_column(table, COLUMN, schema=SCHEMA)
