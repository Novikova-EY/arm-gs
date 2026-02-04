"""add fuel gen company mappings

Revision ID: 9c1c35d27d03
Revises: 99e81af1e9f8
Create Date: 2026-01-30 13:23:31.370900

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = '9c1c35d27d03'
down_revision = '99e81af1e9f8'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUE_EM}")

    if not inspector.has_table("gs_fue_em_gen_company", schema=SCHEMA_FUE_EM):
        op.create_table(
            "gs_fue_em_gen_company",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("gen_company_ref_uuid", sa.String(length=36), nullable=True),
            sa.Column("external_id", sa.String(length=80), nullable=True),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            sa.Column("external_name1", sa.String(length=255), nullable=True),
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_gen_company_em_gen_company_ref_uuid",
            "gs_fue_em_gen_company",
            ["gen_company_ref_uuid"],
            unique=False,
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_gen_company_em_external_id",
            "gs_fue_em_gen_company",
            ["external_id"],
            unique=True,
            schema=SCHEMA_FUE_EM,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("gs_fue_em_gen_company", schema=SCHEMA_FUE_EM):
        op.drop_index(
            "ix_gen_company_em_external_id",
            table_name="gs_fue_em_gen_company",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_index(
            "ix_gen_company_em_gen_company_ref_uuid",
            table_name="gs_fue_em_gen_company",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_table("gs_fue_em_gen_company", schema=SCHEMA_FUE_EM)
