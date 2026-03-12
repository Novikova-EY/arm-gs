"""EquipmentGroup: niv, comp, main, d, r, forem, vedomstvo, obl, dep, oes, er, fo, numb, codegor, be, gk, gkf -> Integer

Revision ID: eq01int
Revises: 281dc31bfeaf, d0e1f2a3b4c5
Create Date: 2026-03-11

Меняет тип полей модели EquipmentGroup с String на Integer.
"""
from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


revision = "eq01int"
down_revision = "281dc31bfeaf"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_groups"

# String(255) or String(80) -> Integer
COLUMNS_TO_INTEGER = [
    "niv",
    "comp",
    "main",
    "d",
    "r",
    "forem",
    "vedomstvo",
    "obl",
    "dep",
    "oes",
    "er",
    "fo",
    "numb",
    "codegor",
    "be",
    "gk",
    "gkf",
]

# Колонки с индексами (нужно пересоздать)
INDEXED_COLUMNS = ["obl", "dep", "oes", "er", "fo", "be", "gk", "gkf"]

USING_CLAUSE = "NULLIF(REGEXP_REPLACE(TRIM(\"{col}\"), '[^0-9-]', '', 'g'), '')::integer"


def upgrade():
    conn = op.get_bind()

    # Удаляем индексы для колонок, которые меняем (IF EXISTS для безопасности)
    for col in INDEXED_COLUMNS:
        idx_name = f"ix_gs_fue_equipment_groups_{col}"
        conn.execute(sa.text(f'DROP INDEX IF EXISTS {SCHEMA_FUEL}.{idx_name}'))

    # Меняем тип колонок
    for col in COLUMNS_TO_INTEGER:
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.String(255) if col in ("niv", "comp", "main", "d", "r", "forem", "vedomstvo", "numb", "codegor") else sa.String(80),
            type_=sa.Integer(),
            schema=SCHEMA_FUEL,
            postgresql_using=USING_CLAUSE.format(col=col),
        )

    # Восстанавливаем индексы
    for col in INDEXED_COLUMNS:
        op.create_index(
            f"ix_gs_fue_equipment_groups_{col}",
            TABLE,
            [col],
            unique=False,
            schema=SCHEMA_FUEL,
        )


def downgrade():
    conn = op.get_bind()

    for col in INDEXED_COLUMNS:
        idx_name = f"ix_gs_fue_equipment_groups_{col}"
        conn.execute(sa.text(f'DROP INDEX IF EXISTS {SCHEMA_FUEL}.{idx_name}'))

    VARCHAR255_COLS = ("niv", "comp", "main", "d", "r", "forem", "vedomstvo", "numb", "codegor")
    for col in COLUMNS_TO_INTEGER:
        varchar_len = 255 if col in VARCHAR255_COLS else 80
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.Integer(),
            type_=sa.String(varchar_len),
            schema=SCHEMA_FUEL,
            postgresql_using=f'"{col}"::varchar({varchar_len})',
        )

    for col in INDEXED_COLUMNS:
        op.create_index(
            f"ix_gs_fue_equipment_groups_{col}",
            TABLE,
            [col],
            unique=False,
            schema=SCHEMA_FUEL,
        )
