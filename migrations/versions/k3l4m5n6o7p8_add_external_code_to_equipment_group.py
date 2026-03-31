"""add_external_code_to_equipment_group

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-03-18

Добавляет поле external_code в gs_fue_equipment_groups для стабильной
трёхсторонней привязки (станция — группа оборудования — агрегат).
"""
import uuid
from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


revision = "k3l4m5n6o7p8"
down_revision = "j2k3l4m5n6o7"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_groups"
COLUMN = "external_code"


def _equipment_group_key(name, name_ext, numb, regional_district_id, regional_energy_system_id) -> str:
    """Формирует стабильный ключ для генерации external_code."""
    return (
        f"equipment_group|name|{name or ''}|name_ext|{name_ext or ''}|numb|{numb or ''}"
        f"|district|{regional_district_id or ''}|res|{regional_energy_system_id or ''}"
    )


def upgrade():
    # 1. Добавляем столбец как nullable для заполнения существующих строк
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.String(36), nullable=True),
        schema=SCHEMA,
    )

    # 2. Заполняем external_code для существующих записей
    conn = op.get_bind()
    result = conn.execute(
        text(
            f"SELECT id, name, name_ext, numb, regional_district_id, regional_energy_system_id "
            f"FROM {SCHEMA}.{TABLE}"
        )
    )
    for row in result:
        key = _equipment_group_key(
            row.name,
            row.name_ext,
            row.numb,
            row.regional_district_id,
            row.regional_energy_system_id,
        )
        code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
        conn.execute(
            text(f"UPDATE {SCHEMA}.{TABLE} SET {COLUMN} = :code WHERE id = :id"),
            {"code": code, "id": row.id},
        )

    # 3. Делаем столбец NOT NULL
    op.alter_column(
        TABLE,
        COLUMN,
        existing_type=sa.String(36),
        nullable=False,
        schema=SCHEMA,
    )

    # 4. Создаём индекс
    op.create_index(
        "ix_equipment_group_external_code",
        TABLE,
        [COLUMN],
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index(
        "ix_equipment_group_external_code",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_column(TABLE, COLUMN, schema=SCHEMA)
