"""Link imported territory technologies to reference data."""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA

revision = "gs26102901"
down_revision = "gs26102702"
branch_labels = None
depends_on = None


def upgrade():
    table = "gs_rs_territory_technologies"
    for column, target in (("technology_type_id", "gs_sys_technology_types"),
                           ("equipment_group_type_id", "gs_sys_equipment_groups")):
        op.add_column(table, sa.Column(column, sa.Integer(), nullable=True), schema=SCHEMA_RATIONAL_STRUCTURE)
        op.create_foreign_key(f"fk_rs_technology_{column}", table, target, [column], ["id"],
                              source_schema=SCHEMA_RATIONAL_STRUCTURE, referent_schema=SCHEMA_REFDATA,
                              ondelete="SET NULL")
    op.add_column(table, sa.Column("fuel_category", sa.String(10), nullable=True), schema=SCHEMA_RATIONAL_STRUCTURE)
    op.add_column(table, sa.Column("references_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
                  schema=SCHEMA_RATIONAL_STRUCTURE)


def downgrade():
    table = "gs_rs_territory_technologies"
    for column in ("references_manual", "fuel_category", "equipment_group_type_id", "technology_type_id"):
        if column.endswith("_id"):
            op.drop_constraint(f"fk_rs_technology_{column}", table, schema=SCHEMA_RATIONAL_STRUCTURE, type_="foreignkey")
        op.drop_column(table, column, schema=SCHEMA_RATIONAL_STRUCTURE)
