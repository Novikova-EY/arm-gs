"""add machine_names table

Revision ID: m2n3o4p5q6r7
Revises: b42547847dca
Create Date: 2026-02-06 00:00:00.000000

Создаёт таблицу machine_names (название агрегата по годам).
По аналогии с machine_fuels, но с текстовым полем name вместо id_fuel.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "m2n3o4p5q6r7"
down_revision = "b42547847dca"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "machine_names",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("id_machine", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        schema=SCHEMA_GENERATION,
    )
    op.create_index("ix_machine_name_id_machine", "machine_names", ["id_machine"], schema=SCHEMA_GENERATION)
    op.create_index("ix_machine_name_year_number", "machine_names", ["year_number"], schema=SCHEMA_GENERATION)
    op.create_index("ix_machine_names_machine_year", "machine_names", ["id_machine", "year_number"], schema=SCHEMA_GENERATION)

    op.create_foreign_key(
        None, "machine_names", "gs_database_versions",
        ["database_version_id"], ["id"],
        source_schema=SCHEMA_GENERATION, referent_schema=SCHEMA_REFDATA, ondelete="SET NULL"
    )


def downgrade():
    op.drop_table("machine_names", schema=SCHEMA_GENERATION)
