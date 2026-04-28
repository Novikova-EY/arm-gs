# -*- coding: utf-8 -*-
"""Типы перспективных площадок: схема gs_gen, имена gs_gen_prospective_place_types_*

Revision ID: d0e1f2a3b4c5
Revises: b8c9d0e1f2a3
Create Date: 2026-04-24

Перенос из gs_sys в gs_gen и переименование (вместо gs_gen_gs_prospective_place_types*).
"""
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None

SCHEMA_REFDATA = "gs_sys"
SCHEMA_GENERATION = "gs_gen"

# (имя в gs_sys, целевое имя в gs_gen)
_MIGRATIONS = [
    ("gs_gen_gs_prospective_place_types", "gs_gen_prospective_place_types"),
    ("gs_gen_gs_prospective_place_types_ges", "gs_gen_prospective_place_types_ges"),
    ("gs_gen_gs_prospective_place_types_gaes", "gs_gen_prospective_place_types_gaes"),
]


def upgrade():
    for old, new in _MIGRATIONS:
        op.execute(
            f'ALTER TABLE "{SCHEMA_REFDATA}"."{old}" SET SCHEMA "{SCHEMA_GENERATION}"'
        )
        op.rename_table(old, new, schema=SCHEMA_GENERATION)


def downgrade():
    for old, new in reversed(_MIGRATIONS):
        op.rename_table(new, old, schema=SCHEMA_GENERATION)
        op.execute(
            f'ALTER TABLE "{SCHEMA_GENERATION}"."{old}" SET SCHEMA "{SCHEMA_REFDATA}"'
        )
