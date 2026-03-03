"""grcode: String(255) -> Integer

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-02-26

Меняет тип MachineFuelParam.grcode с String(255) на Integer.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL


revision = "r9s0t1u2v3w4"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None

TABLE = "gs_fue_machine_fuel_param"


def upgrade():
    op.drop_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )
    op.alter_column(
        TABLE,
        "grcode",
        existing_type=sa.String(255),
        type_=sa.Integer(),
        schema=SCHEMA_FUEL,
        postgresql_using="NULLIF(REGEXP_REPLACE(TRIM(grcode), '[^0-9-]', '', 'g'), '')::integer",
    )
    op.create_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        TABLE,
        ["grcode"],
        unique=False,
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.drop_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )
    op.alter_column(
        TABLE,
        "grcode",
        existing_type=sa.Integer(),
        type_=sa.String(255),
        schema=SCHEMA_FUEL,
        postgresql_using="grcode::varchar(255)",
    )
    op.create_index(
        "ix_gs_fue_machine_fuel_param_grcode",
        TABLE,
        ["grcode"],
        unique=False,
        schema=SCHEMA_FUEL,
    )
