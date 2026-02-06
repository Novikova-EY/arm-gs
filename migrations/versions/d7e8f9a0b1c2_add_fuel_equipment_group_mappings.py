"""add fuel equipment group mappings

Revision ID: f6a7b8c9d0e1
Revises: 19075b3d9c87
Create Date: 2026-02-04

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "19075b3d9c87"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUE_EM}")

    if not inspector.has_table("gs_fue_em_equipment_group", schema=SCHEMA_FUE_EM):
        op.create_table(
            "gs_fue_em_equipment_group",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("equipment_group_ref_uuid", sa.String(length=36), nullable=True),
            sa.Column("name_topl", sa.String(length=255), nullable=True),
            sa.Column("code_topl", sa.Integer(), nullable=True),
            sa.Column("type_topl", sa.Integer(), nullable=True),
            sa.Column("tm_topl", sa.String(length=255), nullable=True),
            sa.Column("n1_topl", sa.Integer(), nullable=True),
            sa.Column("n2_topl", sa.Integer(), nullable=True),
            sa.Column("p1_topl", sa.Integer(), nullable=True),
            sa.Column("p2_topl", sa.Integer(), nullable=True),
            sa.Column("gruppa_oborud_topl", sa.String(length=255), nullable=True),
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_fue_em_eq_group_ref_uuid",
            "gs_fue_em_equipment_group",
            ["equipment_group_ref_uuid"],
            unique=False,
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_fue_em_eq_group_code_topl",
            "gs_fue_em_equipment_group",
            ["code_topl"],
            unique=False,
            schema=SCHEMA_FUE_EM,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("gs_fue_em_equipment_group", schema=SCHEMA_FUE_EM):
        op.drop_index(
            "ix_fue_em_eq_group_code_topl",
            table_name="gs_fue_em_equipment_group",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_index(
            "ix_fue_em_eq_group_ref_uuid",
            table_name="gs_fue_em_equipment_group",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_table("gs_fue_em_equipment_group", schema=SCHEMA_FUE_EM)

