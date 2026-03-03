"""add external_id and external_name to territories_energy

Revision ID: q3r4s5t6u7v8
Revises: p2q3r4s5t6u7
Create Date: 2026-02-24 14:00:00.000000

Добавляет external_id и external_name в gs_fue_em_territories_energy
для связи с EquipmentGroupSet.topl_obl (аналогично topl_dep -> department).
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "q3r4s5t6u7v8"
down_revision = "p2q3r4s5t6u7"
branch_labels = None
depends_on = None

TABLE = "gs_fue_em_territories_energy"
SCHEMA = SCHEMA_FUE_EM


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("external_id", sa.String(length=80), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column("external_name", sa.String(length=255), nullable=True),
        schema=SCHEMA,
    )

    # Заполнить из obl_topl и name_topl; при дубликатах obl_topl берём только первую запись (min id)
    op.execute(
        f"""
        UPDATE {SCHEMA}.{TABLE} te
        SET external_id = te.obl_topl, external_name = te.name_topl
        FROM (
            SELECT DISTINCT ON (obl_topl) id
            FROM {SCHEMA}.{TABLE}
            WHERE obl_topl IS NOT NULL AND TRIM(obl_topl) != ''
            ORDER BY obl_topl, id
        ) sub
        WHERE te.id = sub.id
        """
    )

    op.create_index(
        "ix_gs_fue_em_territories_energy_external_id",
        TABLE,
        ["external_id"],
        unique=True,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index(
        "ix_gs_fue_em_territories_energy_external_id",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_column(TABLE, "external_name", schema=SCHEMA)
    op.drop_column(TABLE, "external_id", schema=SCHEMA)
