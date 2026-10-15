# -*- coding: utf-8 -*-
"""Удалить агрегаты перетоков внутри одной ОЭС.

Revision ID: eeoes26101202
Revises: eeoes26101201
Create Date: 2026-10-12
"""

from alembic import op
from sqlalchemy import text

revision = "eeoes26101202"
down_revision = "eeoes26101201"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        text(
            'DELETE FROM "gs_bem"."gs_bem_ee_receive_transfer_oes_values" '
            "WHERE id_source_union_energy_system = id_target_union_energy_system"
        )
    )


def downgrade():
    # Исходные значения внутри ОЭС удалены, восстановить их без пересчета исходных перетоков нельзя.
    pass
