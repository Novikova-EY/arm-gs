"""recompute station external_code by name

Revision ID: 2c3d4e5f6a7b
Revises: 1f2e3d4c5b6a
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision = "2c3d4e5f6a7b"
down_revision = "1f2e3d4c5b6a"
branch_labels = None
depends_on = None


def _station_key(name, name_combined, district_id) -> str:
    if name:
        return f"station|name|{name}"
    if name_combined:
        return f"station|combined|{name_combined}"
    return f"station|name|{name or ''}|district|{district_id or ''}"


def upgrade():
    conn = op.get_bind()
    select_stmt = sa.text(
        """
        SELECT id, name, name_combined, id_regional_district
        FROM gs_gen.stations
        """
    )
    update_stmt = sa.text(
        """
        UPDATE gs_gen.stations
        SET external_code = :external_code
        WHERE id = :id
        """
    )

    result = conn.execute(select_stmt)
    batch = []
    while True:
        rows = result.fetchmany(1000)
        if not rows:
            break
        for row in rows:
            key = _station_key(row.name, row.name_combined, row.id_regional_district)
            batch.append(
                {
                    "id": row.id,
                    "external_code": str(uuid.uuid5(uuid.NAMESPACE_URL, key)),
                }
            )
        conn.execute(update_stmt, batch)
        batch.clear()


def downgrade():
    # Безопасного отката нет: предыдущие external_code не восстановить.
    pass
