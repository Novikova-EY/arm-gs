"""move short names to fuels

Revision ID: 3f4a5b6c7d8e
Revises: 1d2e3f4a5b6c
Create Date: 2026-01-26 10:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "3f4a5b6c7d8e"
down_revision = "1d2e3f4a5b6c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "gs_fuels",
        sa.Column("topl_nazvl", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    op.add_column(
        "gs_fuels",
        sa.Column("topl_kmbur", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )

    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_REFDATA}.gs_fuels AS f
            SET topl_nazvl = ft.topl_nazvl,
                topl_kmbur = ft.topl_kmbur
            FROM {SCHEMA_REFDATA}.gs_fuel_types AS ft
            WHERE f.id_fuel_type = ft.id
            """
        )
    )

    op.drop_column("gs_fuel_types", "topl_kmbur", schema=SCHEMA_REFDATA)
    op.drop_column("gs_fuel_types", "topl_nazvl", schema=SCHEMA_REFDATA)


def downgrade():
    op.add_column(
        "gs_fuel_types",
        sa.Column("topl_nazvl", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    op.add_column(
        "gs_fuel_types",
        sa.Column("topl_kmbur", sa.String(length=80), nullable=True),
        schema=SCHEMA_REFDATA,
    )

    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_REFDATA}.gs_fuel_types AS ft
            SET topl_nazvl = sub.topl_nazvl,
                topl_kmbur = sub.topl_kmbur
            FROM (
                SELECT id_fuel_type,
                       MAX(topl_nazvl) AS topl_nazvl,
                       MAX(topl_kmbur) AS topl_kmbur
                FROM {SCHEMA_REFDATA}.gs_fuels
                GROUP BY id_fuel_type
            ) AS sub
            WHERE ft.id = sub.id_fuel_type
            """
        )
    )

    op.drop_column("gs_fuels", "topl_kmbur", schema=SCHEMA_REFDATA)
    op.drop_column("gs_fuels", "topl_nazvl", schema=SCHEMA_REFDATA)
