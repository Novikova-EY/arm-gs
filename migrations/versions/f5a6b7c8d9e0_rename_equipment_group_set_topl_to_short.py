"""rename equipment_group_set topl_* to short column names

Revision ID: f5a6b7c8d9e0
Revises: 1e1fdaf90b94
Create Date: 2026-02-27

Переименовывает колонки topl_* в gs_fue_equipment_group_sets в короткие имена
(obl, dep, oes, er, fo, name_ext, niv, ...).
Выполняется только если ещё есть колонки topl_* (идемпотентно).
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL


revision = "f5a6b7c8d9e0"
down_revision = "1e1fdaf90b94"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_sets"
SCHEMA = SCHEMA_FUEL

# (old_name, new_name)
RENAMES = [
    ("topl_name", "name_ext"),
    ("topl_niv", "niv"),
    ("topl_comp", "comp"),
    ("topl_main", "main"),
    ("topl_d", "d"),
    ("topl_r", "r"),
    ("topl_forem", "forem"),
    ("topl_vedomstvo", "vedomstvo"),
    ("topl_obl", "obl"),
    ("topl_dep", "dep"),
    ("topl_oes", "oes"),
    ("topl_er", "er"),
    ("topl_fo", "fo"),
    ("topl_numb", "numb"),
    ("topl_tm", "tm"),
    ("topl_n1", "n1"),
    ("topl_n2", "n2"),
    ("topl_p1", "p1"),
    ("topl_p2", "p2"),
    ("topl_ordnumb", "ordnumb"),
    ("topl_addr", "addr"),
    ("topl_note", "note"),
    ("topl_codegor", "codegor"),
    ("topl_be", "be"),
    ("topl_gk", "gk"),
    ("topl_gkf", "gkf"),
]


def _columns_exist(conn, col_names):
    """Проверяет, существуют ли колонки в таблице."""
    inspector = inspect(conn)
    cols = [c["name"] for c in inspector.get_columns(TABLE, schema=SCHEMA)]
    return all(c in cols for c in col_names)


def upgrade():
    conn = op.get_bind()
    # Если topl_obl ещё есть — переименовываем
    if not _columns_exist(conn, ["topl_obl"]):
        return
    for old_name, new_name in RENAMES:
        if _columns_exist(conn, [old_name]):
            op.alter_column(
                TABLE,
                old_name,
                new_column_name=new_name,
                schema=SCHEMA,
            )


def downgrade():
    conn = op.get_bind()
    # Если obl есть — переименовываем обратно
    if not _columns_exist(conn, ["obl"]):
        return
    for old_name, new_name in RENAMES:
        if _columns_exist(conn, [new_name]):
            op.alter_column(
                TABLE,
                new_name,
                new_column_name=old_name,
                schema=SCHEMA,
            )
