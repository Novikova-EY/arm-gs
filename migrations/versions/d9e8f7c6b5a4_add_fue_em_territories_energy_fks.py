"""add foreign keys to territories energy mappings

Revision ID: d9e8f7c6b5a4
Revises: 59146c3e0f72
Create Date: 2026-01-30 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUE_EM


# revision identifiers, used by Alembic.
revision = "d9e8f7c6b5a4"
down_revision = "59146c3e0f72"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "gs_fue_em_union_energy_system", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.alter_column("external_id", nullable=True)

    with op.batch_alter_table(
        "gs_fue_em_federal_district", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.alter_column("external_id", nullable=True)

    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_union_energy_system
        SET external_id = NULL
        WHERE external_id IS NULL OR external_id IN ('', '0')
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_federal_district
        SET external_id = NULL
        WHERE external_id IS NULL OR external_id = ''
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_territories_energy
        SET dep_topl = NULL
        WHERE dep_topl IS NULL OR dep_topl IN ('', '0')
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_territories_energy
        SET oes_topl = NULL
        WHERE oes_topl IS NULL OR oes_topl IN ('', '0')
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_FUE_EM}.gs_fue_em_territories_energy
        SET fo_topl = NULL
        WHERE fo_topl IS NULL OR fo_topl IN ('', '0')
        """
    )

    with op.batch_alter_table(
        "gs_fue_em_union_energy_system", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.create_unique_constraint(
            "uq_gs_fue_em_union_energy_system_external_id", ["external_id"]
        )

    with op.batch_alter_table(
        "gs_fue_em_federal_district", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.create_unique_constraint(
            "uq_gs_fue_em_federal_district_external_id", ["external_id"]
        )

    with op.batch_alter_table(
        "gs_fue_em_territories_energy", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.alter_column(
            "dep_topl",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.alter_column(
            "oes_topl",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.alter_column(
            "fo_topl",
            existing_type=sa.String(length=255),
            type_=sa.String(length=80),
            nullable=True,
        )
        batch_op.create_foreign_key(
            "fk_territories_energy_dep_topl",
            "gs_fue_em_department",
            ["dep_topl"],
            ["external_id"],
            referent_schema=SCHEMA_FUE_EM,
        )
        batch_op.create_foreign_key(
            "fk_territories_energy_oes_topl",
            "gs_fue_em_union_energy_system",
            ["oes_topl"],
            ["external_id"],
            referent_schema=SCHEMA_FUE_EM,
        )
        batch_op.create_foreign_key(
            "fk_territories_energy_fo_topl",
            "gs_fue_em_federal_district",
            ["fo_topl"],
            ["external_id"],
            referent_schema=SCHEMA_FUE_EM,
        )


def downgrade():
    with op.batch_alter_table(
        "gs_fue_em_federal_district", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_gs_fue_em_federal_district_external_id", type_="unique"
        )
        batch_op.alter_column("external_id", nullable=False)

    with op.batch_alter_table(
        "gs_fue_em_union_energy_system", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_gs_fue_em_union_energy_system_external_id", type_="unique"
        )
        batch_op.alter_column("external_id", nullable=False)

    with op.batch_alter_table(
        "gs_fue_em_territories_energy", schema=SCHEMA_FUE_EM
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_territories_energy_fo_topl", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_territories_energy_oes_topl", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_territories_energy_dep_topl", type_="foreignkey"
        )
        batch_op.alter_column(
            "fo_topl",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )
        batch_op.alter_column(
            "oes_topl",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )
        batch_op.alter_column(
            "dep_topl",
            existing_type=sa.String(length=80),
            type_=sa.String(length=255),
            nullable=True,
        )
