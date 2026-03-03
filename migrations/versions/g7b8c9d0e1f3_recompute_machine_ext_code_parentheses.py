"""Пересчёт Machine.external_code: расширенная нормализация скобок в имени

Revision ID: g7b8c9d0e1f3
Revises: f6a7b8c9d0e2
Create Date: 2026-02-19 16:00:00.000000

Повторный пересчёт с поддержкой (), （）, [] и повторным снятием скобок.
ПТ-60-130/13 и ПТ-60-130/13 (ПТ-80) должны получать одинаковый external_code.
"""

import re
import uuid
from alembic import op
from sqlalchemy.sql import text
from config import SCHEMA_GENERATION


revision = "g7b8c9d0e1f3"
down_revision = "f6a7b8c9d0e2"
branch_labels = None
depends_on = None


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def _normalize_num(val):
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return ""
    if s.isdigit():
        return str(int(s))
    return s


def _normalize_name(val):
    if val is None:
        return ""
    s = " ".join(str(val).split())
    # Убираем trailing части в скобках (повторно): (), （）, []
    paren_re = re.compile(r"\s*[(\uff08\u005b][^)\uff09\u005d]*[)\uff09\u005d]\s*$")
    while True:
        s2 = paren_re.sub("", s).strip()
        if s2 == s:
            break
        s = s2
    return s


def upgrade():
    conn = op.get_bind()

    machines_table = f"{SCHEMA_GENERATION}.machines"
    stations_table = f"{SCHEMA_GENERATION}.stations"
    machine_rows = conn.execute(
        text(
            f"""
            SELECT m.id, m.id_station, m.machine_number, m.machine_name,
                   m.date_exploitation, s.external_code AS station_code
            FROM {machines_table} m
            LEFT JOIN {stations_table} s ON s.id = m.id_station
            """
        )
    ).fetchall()

    for row in machine_rows:
        station_code = row.station_code or f"station_id_{row.id_station}"
        num = _normalize_num(row.machine_number)
        name = _normalize_name(row.machine_name)
        if name:
            ident = f"name|{name}"
        elif row.date_exploitation is not None:
            ident = f"exploitation|{row.date_exploitation}"
        else:
            ident = "name|"
        machine_key = f"machine|station|{station_code}|num|{num}|{ident}"
        code = _stable_uuid(machine_key)
        conn.execute(
            text(f"UPDATE {machines_table} SET external_code = :code WHERE id = :id"),
            {"code": code, "id": row.id},
        )


def downgrade():
    pass
