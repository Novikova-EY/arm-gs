"""add id_department FK to equipment_group_sets

Revision ID: o2p3q4r5s6t7
Revises: n4o5p6q7r8s9
Create Date: 2026-02-24 08:00:00.000000

Добавляет внешний ключ id_department -> Department (gs_sys.gs_departments)
в таблицу gs_fue_equipment_group_sets.
FK создаётся только если таблица gs_departments существует.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUEL, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "o2p3q4r5s6t7"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL
DEPARTMENTS_TABLE = "gs_departments"
DEPARTMENTS_SCHEMA = SCHEMA_REFDATA


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.add_column(
        TABLE,
        sa.Column(
            "id_department",
            sa.Integer(),
            nullable=True,
        ),
        schema=SCHEMA,
    )

    if inspector.has_table(DEPARTMENTS_TABLE, schema=DEPARTMENTS_SCHEMA):
        op.create_foreign_key(
            "fk_equipment_group_sets_id_department",
            TABLE,
            DEPARTMENTS_TABLE,
            ["id_department"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=DEPARTMENTS_SCHEMA,
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_gs_fue_equipment_group_sets_id_department",
        TABLE,
        ["id_department"],
        schema=SCHEMA,
    )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table(DEPARTMENTS_TABLE, schema=DEPARTMENTS_SCHEMA):
        op.drop_constraint(
            "fk_equipment_group_sets_id_department",
            TABLE,
            type_="foreignkey",
            schema=SCHEMA,
        )
    op.drop_index(
        "ix_gs_fue_equipment_group_sets_id_department",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_column(TABLE, "id_department", schema=SCHEMA)
