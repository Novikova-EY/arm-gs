"""fill equipment_group_set external_code

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-01-27 00:00:00.000000

Заполняет external_code для equipment_group_sets, если он отсутствует.
"""

import uuid
from alembic import op
from sqlalchemy.sql import text
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def _make_code(name, equipment_group_id, version_id, row_id):
    safe_name = name or f"equipment_group_set_id_{row_id}"
    eg_id = equipment_group_id or 0
    version_token = version_id if version_id is not None else "null"
    key = f"equipment_group_set|name|{safe_name}|equipment_group_id|{eg_id}|db_version|{version_token}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def upgrade():
    conn = op.get_bind()
    rows = conn.execute(
        text(
            f"""
            SELECT id, id_equipment_group, name, database_version_id
            FROM {SCHEMA_GENERATION}.equipment_group_sets
            WHERE external_code IS NULL OR external_code = ''
            """
        )
    ).fetchall()

    for row in rows:
        row_id, equipment_group_id, name, version_id = row
        code = _make_code(name, equipment_group_id, version_id, row_id)
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_GENERATION}.equipment_group_sets
                SET external_code = :code
                WHERE id = :id
                """
            ),
            {"code": code, "id": row_id},
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_GENERATION}.equipment_group_sets
            SET external_code = NULL
            """
        )
    )
