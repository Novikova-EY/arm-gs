"""add fuel gen company branch mappings

Revision ID: ab12cd34ef56
Revises: 9c1c35d27d03
Create Date: 2026-02-04

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "9c1c35d27d03"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUE_EM}")

    if not inspector.has_table("gs_fue_em_gen_company_branch", schema=SCHEMA_FUE_EM):
        op.create_table(
            "gs_fue_em_gen_company_branch",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("gen_company_ref_uuid", sa.String(length=36), nullable=True),
            sa.Column("external_id", sa.String(length=80), nullable=True),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            sa.Column("local_name", sa.String(length=255), nullable=True),
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_gc_branch_em_gen_company_ref_uuid",
            "gs_fue_em_gen_company_branch",
            ["gen_company_ref_uuid"],
            unique=False,
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_gc_branch_em_external_id",
            "gs_fue_em_gen_company_branch",
            ["external_id"],
            unique=False,
            schema=SCHEMA_FUE_EM,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("gs_fue_em_gen_company_branch", schema=SCHEMA_FUE_EM):
        op.drop_index(
            "ix_gc_branch_em_external_id",
            table_name="gs_fue_em_gen_company_branch",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_index(
            "ix_gc_branch_em_gen_company_ref_uuid",
            table_name="gs_fue_em_gen_company_branch",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_table("gs_fue_em_gen_company_branch", schema=SCHEMA_FUE_EM)

