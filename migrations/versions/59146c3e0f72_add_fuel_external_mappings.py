"""add fuel external mappings

Revision ID: 59146c3e0f72
Revises: p1q2r3s4t5u6
Create Date: 2026-01-30 08:09:35.236821

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = '59146c3e0f72'
down_revision = 'p1q2r3s4t5u6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUE_EM}")

    if not inspector.has_table("gs_fue_em_department", schema=SCHEMA_FUE_EM):
        op.create_table(
            "gs_fue_em_department",
            sa.Column("external_id", sa.String(length=80), primary_key=True, nullable=False),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            schema=SCHEMA_FUE_EM,
        )

    if not inspector.has_table("gs_fue_em_business_unit", schema=SCHEMA_FUE_EM):
        op.create_table(
            "gs_fue_em_business_unit",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("external_id", sa.String(length=80), nullable=False),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_bu_em_external_id",
            "gs_fue_em_business_unit",
            ["external_id"],
            unique=False,
            schema=SCHEMA_FUE_EM,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("gs_fue_em_business_unit", schema=SCHEMA_FUE_EM):
        op.drop_index(
            "ix_bu_em_external_id",
            table_name="gs_fue_em_business_unit",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_table("gs_fue_em_business_unit", schema=SCHEMA_FUE_EM)

    if inspector.has_table("gs_fue_em_department", schema=SCHEMA_FUE_EM):
        op.drop_table("gs_fue_em_department", schema=SCHEMA_FUE_EM)
