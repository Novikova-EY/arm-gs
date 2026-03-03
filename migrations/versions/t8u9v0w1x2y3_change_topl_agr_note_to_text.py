"""change topl_agr_note to Text in MachineToplivoParam

Revision ID: t8u9v0w1x2y3
Revises: a7b8c9d0e1f2
Create Date: 2026-02-26 09:00:00.000000

Меняет тип поля topl_agr_note с INTEGER на TEXT в gs_fue_machine_toplivo_param.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


revision = "t8u9v0w1x2y3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_toplivo_param"
SCHEMA = SCHEMA_FUEL


def upgrade():
    op.alter_column(
        TABLE,
        "topl_agr_note",
        existing_type=sa.Integer(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using='topl_agr_note::text',
        schema=SCHEMA,
    )


def downgrade():
    op.alter_column(
        TABLE,
        "topl_agr_note",
        existing_type=sa.Text(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using='topl_agr_note::integer',
        schema=SCHEMA,
    )
