"""cleanup equipment_group_sets where database_version_id != equipment_group.database_version_id

Revision ID: h8i9j0k1l2m3
Revises: g7b8c9d0e1f3
Create Date: 2026-02-19

Удаляет лишние записи в gs_fue_equipment_group_set_stations и gs_fue_equipment_group_sets,
где database_version_id набора не соответствует database_version_id группы оборудования
(egs.database_version_id IS DISTINCT FROM eg.database_version_id).
"""

from alembic import op
from sqlalchemy import text

from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "h8i9j0k1l2m3"
down_revision = "g7b8c9d0e1f3"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Удаляем связи gs_fue_equipment_group_set_stations, где набор имеет
    #    несоответствующий equipment_group (по версии)
    links_table = f"{SCHEMA_FUEL}.gs_fue_equipment_group_set_stations"
    sets_table = f"{SCHEMA_FUEL}.gs_fue_equipment_group_sets"
    eg_table = f"{SCHEMA_REFDATA}.gs_equipment_groups"

    del_links = text(f"""
        DELETE FROM {links_table}
        WHERE equipment_group_set_id IN (
            SELECT egs.id FROM {sets_table} egs
            JOIN {eg_table} eg ON eg.id = egs.id_equipment_group
            WHERE (egs.database_version_id IS DISTINCT FROM eg.database_version_id)
        )
    """)
    conn.execute(del_links)

    # 2. Обнуляем equipment_group_set_id у машин, ссылающихся на несоответствующие наборы,
    #    чтобы избежать нарушения FK при удалении наборов
    machines_table = f"{SCHEMA_GENERATION}.machines"
    op.execute(text(f"""
        UPDATE {machines_table} m
        SET equipment_group_set_id = NULL
        FROM {sets_table} egs
        JOIN {eg_table} eg ON eg.id = egs.id_equipment_group
        WHERE m.equipment_group_set_id = egs.id
          AND (egs.database_version_id IS DISTINCT FROM eg.database_version_id)
    """))

    # 3. Удаляем наборы, где database_version_id не соответствует equipment_group
    del_sets = text(f"""
        DELETE FROM {sets_table} egs
        WHERE EXISTS (
            SELECT 1 FROM {eg_table} eg
            WHERE eg.id = egs.id_equipment_group
              AND (egs.database_version_id IS DISTINCT FROM eg.database_version_id)
        )
    """)
    conn.execute(del_sets)


def downgrade():
    # Нельзя восстановить удалённые записи
    pass
