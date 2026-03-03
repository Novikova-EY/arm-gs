"""MachineToplivoParam: add topl_agr_stnumb, topl_agr_note VARCHAR(255)

Revision ID: u9v0w1x2y3z4
Revises: t8u9v0w1x2y3
Create Date: 2026-02-26 09:30:00.000000

- Добавляет колонку topl_agr_stnumb (Integer, nullable).
- Меняет topl_agr_note с TEXT на VARCHAR(255).
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


revision = "u9v0w1x2y3z4"
down_revision = "t8u9v0w1x2y3"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_toplivo_param"
SCHEMA = SCHEMA_FUEL


def upgrade():
    op.add_column(
        TABLE,
        sa.Column("topl_agr_stnumb", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.alter_column(
        TABLE,
        "topl_agr_note",
        existing_type=sa.Text(),
        type_=sa.String(255),
        existing_nullable=True,
        postgresql_using="left(topl_agr_note::text, 255)",
        schema=SCHEMA,
    )


def downgrade():
    op.alter_column(
        TABLE,
        "topl_agr_note",
        existing_type=sa.String(255),
        type_=sa.Text(),
        existing_nullable=True,
        schema=SCHEMA,
    )
    op.drop_column(TABLE, "topl_agr_stnumb", schema=SCHEMA)
