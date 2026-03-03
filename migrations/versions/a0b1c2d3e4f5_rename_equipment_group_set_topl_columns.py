"""rename equipment_group_set topl_* columns to short names

Revision ID: a0b1c2d3e4f5
Revises: z9a0b1c2d3e4
Create Date: 2026-02-26

Переименовывает колонки topl_* в gs_fue_equipment_group_sets в короткие имена.
"""

from alembic import op
from config import SCHEMA_FUEL


revision = "a0b1c2d3e4f5"
down_revision = "z9a0b1c2d3e4"
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


def upgrade():
    for old_name, new_name in RENAMES:
        op.alter_column(
            TABLE,
            old_name,
            new_column_name=new_name,
            schema=SCHEMA,
        )


def downgrade():
    for old_name, new_name in RENAMES:
        op.alter_column(
            TABLE,
            new_name,
            new_column_name=old_name,
            schema=SCHEMA,
        )
