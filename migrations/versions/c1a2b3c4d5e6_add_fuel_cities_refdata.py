"""add fuel cities refdata

Revision ID: c1a2b3c4d5e6
Revises: ab12cd34ef56
Create Date: 2026-02-04

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "c1a2b3c4d5e6"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_FUE_EM}")

    if not inspector.has_table("gs_fue_em_cities", schema=SCHEMA_FUE_EM):
        op.create_table(
            "gs_fue_em_cities",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("code_topl", sa.Integer(), nullable=False),
            sa.Column("name_topl", sa.String(length=255), nullable=True),
            sa.Column("naselenie", sa.Numeric(18, 2), nullable=True),
            sa.Column("gilfond", sa.Numeric(18, 2), nullable=True),
            sa.Column("obesp_cts", sa.String(length=255), nullable=True),
            sa.Column("dprom_ao", sa.String(length=255), nullable=True),
            sa.Column("dgkh_ao", sa.String(length=255), nullable=True),
            sa.Column("obl", sa.Integer(), nullable=True),
            sa.UniqueConstraint("code_topl", name="uq_fue_em_cities_code_topl"),
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_fue_em_cities_code_topl",
            "gs_fue_em_cities",
            ["code_topl"],
            unique=True,
            schema=SCHEMA_FUE_EM,
        )
        op.create_index(
            "ix_fue_em_cities_obl",
            "gs_fue_em_cities",
            ["obl"],
            unique=False,
            schema=SCHEMA_FUE_EM,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("gs_fue_em_cities", schema=SCHEMA_FUE_EM):
        op.drop_index(
            "ix_fue_em_cities_obl",
            table_name="gs_fue_em_cities",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_index(
            "ix_fue_em_cities_code_topl",
            table_name="gs_fue_em_cities",
            schema=SCHEMA_FUE_EM,
        )
        op.drop_table("gs_fue_em_cities", schema=SCHEMA_FUE_EM)

