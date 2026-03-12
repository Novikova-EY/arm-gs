"""equipment_group_set topl fields rename

Revision ID: j2k3l4m5n6o7
Revises: i9j0k1l2m3n4
Create Date: 2026-02-19 14:00:00.000000

Удаляет поле type, добавляет topl_name, переименовывает поля
с префиксом topl_ в gs_fue_equipment_group_sets.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "j2k3l4m5n6o7"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL

# (old_name, new_name) для переименования колонок
RENAME_MAP = [
    ("niv", "topl_niv"),
    ("comp", "topl_comp"),
    ("main", "topl_main"),
    ("d", "topl_d"),
    ("r", "topl_r"),
    ("form", "topl_form"),
    ("vedomstvo", "topl_vedomstvo"),
    ("obl", "topl_obl"),
    ("dep", "topl_dep"),
    ("oes", "topl_oes"),
    ("er", "topl_er"),
    ("fo", "topl_fo"),
    ("numb", "topl_numb"),
    ("tm", "topl_tm"),
    ("n1", "topl_n1"),
    ("n2", "topl_n2"),
    ("p1", "topl_p1"),
    ("p2", "topl_p2"),
    ("ordnumb", "topl_ordnumb"),
    ("addr", "topl_addr"),
    ("note", "topl_note"),
    ("codegor", "topl_codegor"),
    ("be", "topl_be"),
    ("gk", "topl_gk"),
    ("gkf", "topl_gkf"),
]


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return
    columns = {c["name"] for c in inspector.get_columns(TABLE, schema=SCHEMA)}
    # 1. Удалить колонку type
    if "type" in columns:
        op.drop_column(TABLE, "type", schema=SCHEMA)

    # 2. Добавить колонку topl_name
    if "topl_name" not in columns:
        op.add_column(
            TABLE,
            sa.Column("topl_name", sa.String(length=255), nullable=True),
            schema=SCHEMA,
        )

    # 3. Переименовать все колонки
    for old_name, new_name in RENAME_MAP:
        if old_name in columns:
            op.alter_column(
                TABLE,
                old_name,
                new_column_name=new_name,
                schema=SCHEMA,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(TABLE, schema=SCHEMA):
        return
    columns = {c["name"] for c in inspector.get_columns(TABLE, schema=SCHEMA)}
    # 1. Переименовать колонки обратно
    for old_name, new_name in RENAME_MAP:
        if new_name in columns:
            op.alter_column(
                TABLE,
                new_name,
                new_column_name=old_name,
                schema=SCHEMA,
            )

    # 2. Удалить topl_name
    if "topl_name" in columns:
        op.drop_column(TABLE, "topl_name", schema=SCHEMA)

    # 3. Добавить type
    if "type" not in columns:
        op.add_column(
            TABLE,
            sa.Column("type", sa.String(length=255), nullable=True),
            schema=SCHEMA,
        )
