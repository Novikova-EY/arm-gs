# -*- coding: utf-8 -*-
"""Исправление привязки субъектов РФ к энергозонам 7/8/9 (состав как у ОЭС).

Раньше:
- в «ОЭС Средней Волги» попадали уральские субъекты (Киров, Оренбург, Пермь,
  Башкортостан, Удмуртия);
- ХМАО и ЯНАО были в «ОЭС Урала (без Тюмени)», а не в «Тюменская ЭС».

Из‑за этого на сводке /power_demand/summary/energy_zones/ расчётные строки
суммировали неверный набор РЭС (в т.ч. полную Тюменскую РЭС и в зоне 8, и в 9),
и «Проверка» не сходилась к 0.

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-07-22
"""
from alembic import op
from sqlalchemy import text

revision = "u6v7w8x9y0z1"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None

SCHEMA = "gs_sys"
RD = f"{SCHEMA}.gs_sys_regional_districts"
EZ = f"{SCHEMA}.gs_sys_energy_zones"

# number энергозоны → имена субъектов, которые должны быть в ней после миграции
# (переносы только для ошибочно назначенных; остальные не трогаем).
_MOVE_TO_EZ8 = (
    "Кировская область",
    "Оренбургская область",
    "Пермский край",
    "Республика Башкортостан",
    "Удмуртская Республика",
)
# Точные имена (en-dash) + ILIKE-маски на случай ASCII/em-dash в справочнике.
_MOVE_TO_EZ9 = (
    "Ханты-Мансийский АО – Югра",
    "Ямало-Ненецкий АО",
)
_MOVE_TO_EZ9_ILIKE = (
    "Ханты-Мансийский АО%Югра%",
    "Ямало-Ненецкий АО",
)


def _ez_ids_for_version(conn, ver_id):
    return {
        str(num): int(eid)
        for num, eid in conn.execute(
            text(
                f"""
                SELECT number, id FROM {EZ}
                WHERE number IN ('7', '8', '9')
                  AND database_version_id IS NOT DISTINCT FROM :ver
                """
            ),
            {"ver": ver_id},
        ).fetchall()
    }


def _update_rd_zone(conn, *, ver_id, ez_id, name=None, name_ilike=None):
    if name is not None:
        conn.execute(
            text(
                f"""
                UPDATE {RD}
                SET id_energy_zone = :ez
                WHERE name = :name
                  AND database_version_id IS NOT DISTINCT FROM :ver
                """
            ),
            {"ez": ez_id, "name": name, "ver": ver_id},
        )
    if name_ilike is not None:
        conn.execute(
            text(
                f"""
                UPDATE {RD}
                SET id_energy_zone = :ez
                WHERE name ILIKE :pat
                  AND database_version_id IS NOT DISTINCT FROM :ver
                """
            ),
            {"ez": ez_id, "pat": name_ilike, "ver": ver_id},
        )


def upgrade():
    conn = op.get_bind()
    # Для каждой версии БД: zone id по number, затем UPDATE субъектов по имени.
    versions = conn.execute(
        text(f"SELECT DISTINCT database_version_id FROM {EZ} WHERE number IN ('7', '8', '9')")
    ).fetchall()
    for (ver_id,) in versions:
        ez_ids = _ez_ids_for_version(conn, ver_id)
        if "8" not in ez_ids or "9" not in ez_ids:
            continue
        for name in _MOVE_TO_EZ8:
            _update_rd_zone(conn, ver_id=ver_id, ez_id=ez_ids["8"], name=name)
        for name, pat in zip(_MOVE_TO_EZ9, _MOVE_TO_EZ9_ILIKE):
            _update_rd_zone(
                conn, ver_id=ver_id, ez_id=ez_ids["9"], name=name, name_ilike=pat
            )


def downgrade():
    conn = op.get_bind()
    versions = conn.execute(
        text(f"SELECT DISTINCT database_version_id FROM {EZ} WHERE number IN ('7', '8', '9')")
    ).fetchall()
    for (ver_id,) in versions:
        ez_ids = _ez_ids_for_version(conn, ver_id)
        if "7" not in ez_ids or "8" not in ez_ids:
            continue
        for name in _MOVE_TO_EZ8:
            _update_rd_zone(conn, ver_id=ver_id, ez_id=ez_ids["7"], name=name)
        if "9" not in ez_ids:
            continue
        for name, pat in zip(_MOVE_TO_EZ9, _MOVE_TO_EZ9_ILIKE):
            _update_rd_zone(
                conn, ver_id=ver_id, ez_id=ez_ids["8"], name=name, name_ilike=pat
            )
