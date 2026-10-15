# -*- coding: utf-8 -*-
"""Удалить ручную строку экспорта из баланса ЭЭ.

Revision ID: ee2610120303
Revises: eeoes26101202
Create Date: 2026-10-13
"""
from alembic import op
from sqlalchemy import text

revision = "ee2610120303"
down_revision = "eeoes26101202"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text('DROP TABLE IF EXISTS "gs_bem"."gs_bem_ee_balance_export_values" CASCADE')
    )


def downgrade():
    # Значения удалённой строки нельзя восстановить после удаления таблицы.
    pass
