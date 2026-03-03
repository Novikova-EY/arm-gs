"""add machine_topl_agr table to gs_fue

Revision ID: l2m3n4o5p6q7
Revises: k3l4m5n6o7p8
Create Date: 2026-02-21 00:00:00.000000

Создаёт таблицу gs_fue_machine_topl_agr в схеме gs_fue с привязкой к machines.id.
Одна запись на одну машину (UniqueConstraint на machine_id).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import NUMERIC
from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "l2m3n4o5p6q7"
down_revision = "k3l4m5n6o7p8"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_topl_agr"
SCHEMA = SCHEMA_FUEL


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("topl_agr_numb1120", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_numb", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_station_number", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_yearin", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_dem", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_nt", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_grcode", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_note", NUMERIC(20, 6), nullable=True),
        sa.Column("topl_agr_station_name", sa.String(1024), nullable=True),
        sa.Column("topl_agr_opesname", sa.String(1024), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            [f"{SCHEMA_GENERATION}.machines.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("machine_id", name="uq_machine_topl_agr_machine_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_machine_topl_agr_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index(
        "ix_gs_fue_machine_topl_agr_database_version_id",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_table(TABLE, schema=SCHEMA)
