"""extend power precision to 16 digits

Revision ID: z1y2x3w4v5u6
Revises: a2b3c4d5e6f7
Create Date: 2026-02-13 00:00:00.000000

Расширяет точность полей мощностей (p_ust, p_ogr, p_rasp) до 16 знаков
после запятой для согласования с импортом из Excel.
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "z1y2x3w4v5u6"
down_revision = "f9g0h1i2j3k4"
branch_labels = None
depends_on = None


def upgrade():
    # machine_powers
    op.alter_column(
        "machine_powers",
        "p_ust",
        type_=sa.Numeric(25, 16),
        existing_type=sa.Numeric(25, 15),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "machine_powers",
        "p_ogr",
        type_=sa.Numeric(25, 16),
        existing_type=sa.Numeric(25, 15),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "machine_powers",
        "p_rasp",
        type_=sa.Numeric(25, 16),
        existing_type=sa.Numeric(25, 15),
        schema=SCHEMA_GENERATION,
    )

    # station_powers
    op.alter_column(
        "station_powers",
        "p_ust",
        type_=sa.Numeric(25, 16),
        existing_type=sa.Numeric(25, 15),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "station_powers",
        "p_ogr",
        type_=sa.Numeric(25, 16),
        existing_type=sa.Numeric(25, 15),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "station_powers",
        "p_rasp",
        type_=sa.Numeric(25, 16),
        existing_type=sa.Numeric(25, 15),
        schema=SCHEMA_GENERATION,
    )

    # pgu_machine_powers
    op.alter_column(
        "pgu_machine_powers",
        "p_ust",
        type_=sa.Numeric(25, 16),
        existing_type=sa.Numeric(25, 15),
        schema=SCHEMA_GENERATION,
    )


def downgrade():
    # pgu_machine_powers
    op.alter_column(
        "pgu_machine_powers",
        "p_ust",
        type_=sa.Numeric(25, 15),
        existing_type=sa.Numeric(25, 16),
        schema=SCHEMA_GENERATION,
    )

    # station_powers
    op.alter_column(
        "station_powers",
        "p_ust",
        type_=sa.Numeric(25, 15),
        existing_type=sa.Numeric(25, 16),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "station_powers",
        "p_ogr",
        type_=sa.Numeric(25, 15),
        existing_type=sa.Numeric(25, 16),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "station_powers",
        "p_rasp",
        type_=sa.Numeric(25, 15),
        existing_type=sa.Numeric(25, 16),
        schema=SCHEMA_GENERATION,
    )

    # machine_powers
    op.alter_column(
        "machine_powers",
        "p_ust",
        type_=sa.Numeric(25, 15),
        existing_type=sa.Numeric(25, 16),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "machine_powers",
        "p_ogr",
        type_=sa.Numeric(25, 15),
        existing_type=sa.Numeric(25, 16),
        schema=SCHEMA_GENERATION,
    )
    op.alter_column(
        "machine_powers",
        "p_rasp",
        type_=sa.Numeric(25, 15),
        existing_type=sa.Numeric(25, 16),
        schema=SCHEMA_GENERATION,
    )

