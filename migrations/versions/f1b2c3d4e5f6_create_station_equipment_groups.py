"""create station_equipment_groups

Revision ID: f1b2c3d4e5f6
Revises: b367194f3325
Create Date: 2026-01-16 00:00:00.000000

Создаёт таблицу station_equipment_groups и достраивает связи/данные
для station_equipment_group_id в machines.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "f1b2c3d4e5f6"
down_revision = "b367194f3325"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("station_equipment_groups", schema=SCHEMA_GENERATION):
        op.create_table(
            "station_equipment_groups",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("id_station", sa.Integer(), nullable=False),
            sa.Column("id_equipment_group", sa.Integer(), nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.ForeignKeyConstraint(
                ["id_station"],
                [f"{SCHEMA_GENERATION}.stations.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["id_equipment_group"],
                [f"{SCHEMA_REFDATA}.gs_equipment_groups.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint(
                "id_station",
                "id_equipment_group",
                name="uq_station_equipment_groups_station_equipment_group",
            ),
            schema=SCHEMA_GENERATION,
        )

        op.create_index(
            "ix_station_equipment_groups_id_station",
            "station_equipment_groups",
            ["id_station"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_station_equipment_groups_id_equipment_group",
            "station_equipment_groups",
            ["id_equipment_group"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_station_equipment_groups_database_version_id",
            "station_equipment_groups",
            ["database_version_id"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )

    # Создаем FK на machines -> station_equipment_groups, если еще нет
    fks = inspector.get_foreign_keys("machines", schema=SCHEMA_GENERATION)
    fk_names = {fk.get("name") for fk in fks}
    if "fk_machines_station_equipment_group_id" not in fk_names:
        op.create_foreign_key(
            "fk_machines_station_equipment_group_id",
            "machines",
            "station_equipment_groups",
            ["station_equipment_group_id"],
            ["id"],
            source_schema=SCHEMA_GENERATION,
            referent_schema=SCHEMA_GENERATION,
            ondelete="RESTRICT",
        )

    # Заполняем station_equipment_groups и проставляем FK в machines
    op.execute(
        f"""
        INSERT INTO {SCHEMA_GENERATION}.station_equipment_groups (id_station, id_equipment_group)
        SELECT DISTINCT m.id_station, m.id_equipment_group
        FROM {SCHEMA_GENERATION}.machines m
        WHERE m.id_station IS NOT NULL
          AND m.id_equipment_group IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM {SCHEMA_GENERATION}.station_equipment_groups seg
              WHERE seg.id_station = m.id_station
                AND seg.id_equipment_group = m.id_equipment_group
          )
        """
    )

    op.execute(
        f"""
        UPDATE {SCHEMA_GENERATION}.machines m
        SET station_equipment_group_id = seg.id
        FROM {SCHEMA_GENERATION}.station_equipment_groups seg
        WHERE m.id_station = seg.id_station
          AND m.id_equipment_group = seg.id_equipment_group
        """
    )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    fks = inspector.get_foreign_keys("machines", schema=SCHEMA_GENERATION)
    fk_names = {fk.get("name") for fk in fks}
    if "fk_machines_station_equipment_group_id" in fk_names:
        op.drop_constraint(
            "fk_machines_station_equipment_group_id",
            "machines",
            schema=SCHEMA_GENERATION,
            type_="foreignkey",
        )

    if inspector.has_table("station_equipment_groups", schema=SCHEMA_GENERATION):
        op.drop_index(
            "ix_station_equipment_groups_database_version_id",
            table_name="station_equipment_groups",
            schema=SCHEMA_GENERATION,
        )
        op.drop_index(
            "ix_station_equipment_groups_id_equipment_group",
            table_name="station_equipment_groups",
            schema=SCHEMA_GENERATION,
        )
        op.drop_index(
            "ix_station_equipment_groups_id_station",
            table_name="station_equipment_groups",
            schema=SCHEMA_GENERATION,
        )
        op.drop_table("station_equipment_groups", schema=SCHEMA_GENERATION)
