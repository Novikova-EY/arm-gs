"""EquipmentGroup: add id_regional_district, id_regional_energy_system (FK)

Revision ID: eq02rdres
Revises: eq01int
Create Date: 2026-03-11

Добавляет поля id_regional_district и id_regional_energy_system в EquipmentGroup.
Значения заполняются при загрузке по obl -> TerritoriesEnergyExternalMapping -> ref_uuid.
"""
from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_REFDATA, SCHEMA_FUE_EM


revision = "eq02rdres"
down_revision = "eq01int"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_groups"
TEM_TABLE = "gs_fue_em_territories_energy"
RD_TABLE = "gs_regional_districts"
RES_TABLE = "gs_regional_energy_systems"


def upgrade():
    # Добавляем колонки (nullable)
    op.add_column(
        TABLE,
        sa.Column("id_regional_district", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )
    op.add_column(
        TABLE,
        sa.Column("id_regional_energy_system", sa.Integer(), nullable=True),
        schema=SCHEMA_FUEL,
    )

    # Заполняем значения из obl -> TerritoriesEnergyExternalMapping -> RegionalDistrict/RegionalEnergySystem
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{TABLE} eg
        SET id_regional_district = sub.rd_id
        FROM (
            SELECT eg2.id AS eg_id,
                (SELECT rd.id
                 FROM {SCHEMA_REFDATA}.{RD_TABLE} rd
                 JOIN {SCHEMA_FUE_EM}.{TEM_TABLE} tem
                   ON tem.regional_district_ref_uuid = rd.ref_uuid
                 WHERE tem.external_id = eg2.obl::text
                   AND (eg2.database_version_id IS NULL AND rd.database_version_id IS NULL
                        OR rd.database_version_id = eg2.database_version_id)
                 LIMIT 1
                ) AS rd_id
            FROM {SCHEMA_FUEL}.{TABLE} eg2
            WHERE eg2.obl IS NOT NULL
        ) sub
        WHERE eg.id = sub.eg_id AND sub.rd_id IS NOT NULL
        """
    )
    op.execute(
        f"""
        UPDATE {SCHEMA_FUEL}.{TABLE} eg
        SET id_regional_energy_system = sub.res_id
        FROM (
            SELECT eg2.id AS eg_id,
                (SELECT res.id
                 FROM {SCHEMA_REFDATA}.{RES_TABLE} res
                 JOIN {SCHEMA_FUE_EM}.{TEM_TABLE} tem
                   ON tem.regional_energy_system_ref_uuid = res.ref_uuid
                 WHERE tem.external_id = eg2.obl::text
                   AND (eg2.database_version_id IS NULL AND res.database_version_id IS NULL
                        OR res.database_version_id = eg2.database_version_id)
                 LIMIT 1
                ) AS res_id
            FROM {SCHEMA_FUEL}.{TABLE} eg2
            WHERE eg2.obl IS NOT NULL
        ) sub
        WHERE eg.id = sub.eg_id AND sub.res_id IS NOT NULL
        """
    )

    # FK и индексы
    op.create_foreign_key(
        "fk_equipment_group_regional_district",
        TABLE,
        RD_TABLE,
        ["id_regional_district"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_equipment_group_regional_energy_system",
        TABLE,
        RES_TABLE,
        ["id_regional_energy_system"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gs_fue_equipment_groups_id_regional_district",
        TABLE,
        ["id_regional_district"],
        unique=False,
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_gs_fue_equipment_groups_id_regional_energy_system",
        TABLE,
        ["id_regional_energy_system"],
        unique=False,
        schema=SCHEMA_FUEL,
    )


def downgrade():
    op.drop_index(
        "ix_gs_fue_equipment_groups_id_regional_energy_system",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )
    op.drop_index(
        "ix_gs_fue_equipment_groups_id_regional_district",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )
    op.drop_constraint(
        "fk_equipment_group_regional_energy_system",
        TABLE,
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_equipment_group_regional_district",
        TABLE,
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_column(TABLE, "id_regional_energy_system", schema=SCHEMA_FUEL)
    op.drop_column(TABLE, "id_regional_district", schema=SCHEMA_FUEL)
