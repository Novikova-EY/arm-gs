# -*- coding: utf-8 -*-
"""Ненецкий АО → энергозона 2 (Коми-Архангельская ЭС).

Субъект был в «не указано», из‑за чего РЭС «Архангельской области и Ненецкого АО»
считалась частичной для зоны 2 и выпадала из расчётных сумм (после защиты от
полного показателя частично пересекающихся РЭС).

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-07-22
"""
from alembic import op
from sqlalchemy import text

revision = "v7w8x9y0z1a2"
down_revision = "u6v7w8x9y0z1"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
RD = f"{SCHEMA}.gs_sys_regional_districts"
EZ = f"{SCHEMA}.gs_sys_energy_zones"

_NENETS_NAME = "Ненецкий АО"
_EZ2_NUMBER = "2"
_PLACEHOLDER_NUMBER = "не указано"


def upgrade():
    conn = op.get_bind()
    versions = conn.execute(
        text(
            f"""
            SELECT DISTINCT database_version_id FROM {EZ}
            WHERE number = :ez2
            """
        ),
        {"ez2": _EZ2_NUMBER},
    ).fetchall()
    for (ver_id,) in versions:
        ez2 = conn.execute(
            text(
                f"""
                SELECT id FROM {EZ}
                WHERE number = :ez2
                  AND database_version_id IS NOT DISTINCT FROM :ver
                """
            ),
            {"ez2": _EZ2_NUMBER, "ver": ver_id},
        ).fetchone()
        if ez2 is None:
            continue
        conn.execute(
            text(
                f"""
                UPDATE {RD}
                SET id_energy_zone = :ez2_id
                WHERE name = :name
                  AND database_version_id IS NOT DISTINCT FROM :ver
                """
            ),
            {"ez2_id": int(ez2[0]), "name": _NENETS_NAME, "ver": ver_id},
        )


def downgrade():
    conn = op.get_bind()
    versions = conn.execute(
        text(
            f"""
            SELECT DISTINCT database_version_id FROM {EZ}
            WHERE number IN (:ez2, :ph)
            """
        ),
        {"ez2": _EZ2_NUMBER, "ph": _PLACEHOLDER_NUMBER},
    ).fetchall()
    for (ver_id,) in versions:
        ph = conn.execute(
            text(
                f"""
                SELECT id FROM {EZ}
                WHERE number = :ph
                  AND database_version_id IS NOT DISTINCT FROM :ver
                """
            ),
            {"ph": _PLACEHOLDER_NUMBER, "ver": ver_id},
        ).fetchone()
        if ph is None:
            continue
        conn.execute(
            text(
                f"""
                UPDATE {RD}
                SET id_energy_zone = :ph_id
                WHERE name = :name
                  AND database_version_id IS NOT DISTINCT FROM :ver
                """
            ),
            {"ph_id": int(ph[0]), "name": _NENETS_NAME, "ver": ver_id},
        )
