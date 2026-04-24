# -*- coding: utf-8 -*-
"""Третий тип площадки ГАЭС («Площадки размещения новых ГАЭС») — как у ГЭС для ТЭП основных.

Revision ID: b5c6d7e8f9a0
Revises: a3b4c5d6e7f8
Create Date: 2026-04-17

Без этой строки в справочнике строки ТЭП с данным типом не попадали ни в «основные»,
ни в «резервные» при разбиении для /gaes/tep-main/ и /gaes/tep-reserve/.
"""
from alembic import op
import sqlalchemy as sa


revision = "b5c6d7e8f9a0"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None

SCHEMA_REF = "gs_sys"
TABLE_TYPES_GAES = "gs_prospective_place_types_gaes"

THIRD_TYPE_NAME = "Площадки размещения новых ГАЭС"


def upgrade():
    bind = op.get_bind()
    ins = sa.text(
        f'INSERT INTO "{SCHEMA_REF}"."{TABLE_TYPES_GAES}" (name, created_at, updated_at) '
        "VALUES (:n, now(), now()) ON CONFLICT (name) DO NOTHING"
    )
    bind.execute(ins, {"n": THIRD_TYPE_NAME})


def downgrade():
    bind = op.get_bind()
    del_ = sa.text(
        f'DELETE FROM "{SCHEMA_REF}"."{TABLE_TYPES_GAES}" WHERE name = :n'
    )
    bind.execute(del_, {"n": THIRD_TYPE_NAME})
