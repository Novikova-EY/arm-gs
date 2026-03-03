"""rename _topl columns in gs_fue_em_equipment_group

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-02-27

Переименовывает code_topl->code, type_topl->type, tm_topl->tm и т.д.
в gs_fue_em_equipment_group. Модель EquipmentGroupExternalMapping
ожидает короткие имена (code, type, tm, n1, n2, p1, p2, gruppa_oborud).
name_topl остаётся без изменений.
Идемпотентно.
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUE_EM


revision = "j9k0l1m2n3o4"
down_revision = "i8j9k0l1m2n3"
branch_labels = None
depends_on = None

TABLE = "gs_fue_em_equipment_group"
SCHEMA = SCHEMA_FUE_EM

# (old_name, new_name) — name_topl не переименовываем
COLUMN_RENAMES = [
    ("code_topl", "code"),
    ("type_topl", "type"),
    ("tm_topl", "tm"),
    ("n1_topl", "n1"),
    ("n2_topl", "n2"),
    ("p1_topl", "p1"),
    ("p2_topl", "p2"),
    ("gruppa_oborud_topl", "gruppa_oborud"),
]


def _column_exists(conn, col):
    inspector = inspect(conn)
    cols = [c["name"] for c in inspector.get_columns(TABLE, schema=SCHEMA)]
    return col in cols


def upgrade():
    conn = op.get_bind()
    for old_name, new_name in COLUMN_RENAMES:
        if _column_exists(conn, old_name):
            op.alter_column(
                TABLE,
                old_name,
                new_column_name=new_name,
                schema=SCHEMA,
            )
    # Индекс code_topl -> code
    try:
        op.execute(
            f"ALTER INDEX IF EXISTS {SCHEMA}.ix_fue_em_eq_group_code_topl "
            f"RENAME TO ix_fue_em_eq_group_code"
        )
    except Exception:
        pass


def downgrade():
    conn = op.get_bind()
    try:
        op.execute(
            f"ALTER INDEX IF EXISTS {SCHEMA}.ix_fue_em_eq_group_code "
            f"RENAME TO ix_fue_em_eq_group_code_topl"
        )
    except Exception:
        pass
    for old_name, new_name in COLUMN_RENAMES:
        if _column_exists(conn, new_name):
            op.alter_column(
                TABLE,
                new_name,
                new_column_name=old_name,
                schema=SCHEMA,
            )
