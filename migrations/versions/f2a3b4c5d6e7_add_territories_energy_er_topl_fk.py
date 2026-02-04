"""add economic region fk to territories energy

Revision ID: f2a3b4c5d6e7
Revises: d9e8f7c6b5a4
Create Date: 2026-01-30 09:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "a42134136694"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "gs_fue_em_economic_region", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.alter_column("external_id", nullable=True)
        batch_op.create_unique_constraint(
            "uq_gs_fue_em_economic_region_external_id", ["external_id"]
        )

    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_economic_region
        SET external_id = NULL
        WHERE external_id IS NULL OR external_id IN ('', '0')
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_territories_energy
        SET er_topl = NULL
        WHERE er_topl IS NULL
            OR er_topl IN ('', '0')
            OR NOT EXISTS (
                SELECT 1
                FROM {SCHEMA_FUE_EM}.gs_fue_em_economic_region er
                WHERE er.external_id = {SCHEMA_FUE_EM}.gs_fue_em_territories_energy.er_topl
            )
        """
    )

    with op.batch_alter_table(
        "gs_fue_em_territories_energy", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.alter_column(
            "er_topl",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_territories_energy_er_topl",
            "gs_fue_em_economic_region",
            ["er_topl"],
            ["external_id"],
            referent_schema=SCHEMA_FUE_EM,
        )


def downgrade():
    with op.batch_alter_table(
        "gs_fue_em_territories_energy", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_territories_energy_er_topl", type_="foreignkey"
        )
        batch_op.alter_column(
            "er_topl",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )

    with op.batch_alter_table(
        "gs_fue_em_economic_region", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_gs_fue_em_economic_region_external_id", type_="unique"
        )
        batch_op.alter_column("external_id", nullable=True)

    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_economic_region
        SET external_id = ''
        WHERE external_id IS NULL
        """
    )

    with op.batch_alter_table(
        "gs_fue_em_economic_region", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.alter_column("external_id", nullable=False)
