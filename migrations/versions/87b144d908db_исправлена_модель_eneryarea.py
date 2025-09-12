"""исправлена модель eneryarea

Revision ID: 87b144d908db
Revises: ae91a94fbde3
Create Date: 2025-09-10 15:40:45.415167

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from config import SCHEMA_REFDATA

# revision identifiers, used by Alembic.
revision = '87b144d908db'
down_revision = 'ae91a94fbde3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("energy_areas", schema=SCHEMA_REFDATA) as b:
        # если constraint известно по имени — снимите его,
        # иначе batch_mode сам снимет при drop_column, но лучше явно
        try:
            b.drop_constraint("energy_areas_id_regional_energy_system_fkey", type_="foreignkey")
        except Exception:
            pass
        try:
            b.drop_index("ix_refdata_energy_areas_id_regional_energy_system")
        except Exception:
            pass
        b.drop_column("id_regional_energy_system")

def downgrade():
    with op.batch_alter_table("energy_areas", schema=SCHEMA_REFDATA) as b:
        b.add_column(sa.Column("id_regional_energy_system", sa.Integer(), nullable=False))
    op.create_foreign_key(
        "energy_areas_id_regional_energy_system_fkey",
        f"{SCHEMA_REFDATA}.energy_areas",
        f"{SCHEMA_REFDATA}.regional_energy_systems",
        ["id_regional_energy_system"], ["id"],
        source_schema=SCHEMA_REFDATA, referent_schema=SCHEMA_REFDATA, ondelete="RESTRICT"
    )
    op.create_index(
        "ix_refdata_energy_areas_id_regional_energy_system",
        f"{SCHEMA_REFDATA}.energy_areas",
        ["id_regional_energy_system"]
    )