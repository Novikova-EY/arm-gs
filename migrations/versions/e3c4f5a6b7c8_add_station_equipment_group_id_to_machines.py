"""add station_equipment_group_id to machines

Revision ID: e3c4f5a6b7c8
Revises: d5e6f7a8b9c0
Create Date: 2026-01-16 00:00:00.000000

Добавляет ссылку агрегата на группу оборудования станции и
заполняет её на основе (id_station, id_equipment_group).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_GENERATION


# revision identifiers, used by Alembic.
revision = "e3c4f5a6b7c8"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    """Добавляет station_equipment_group_id и переносит данные."""
    op.add_column(
        "machines",
        sa.Column("station_equipment_group_id", sa.Integer(), nullable=True),
        schema=SCHEMA_GENERATION,
    )

    op.create_index(
        "ix_machine_station_equipment_group_id",
        "machines",
        ["station_equipment_group_id"],
        unique=False,
        schema=SCHEMA_GENERATION,
    )

    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table("station_equipment_groups", schema=SCHEMA_GENERATION):
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

        op.create_unique_constraint(
            "uq_station_equipment_groups_station_equipment_group",
            "station_equipment_groups",
            ["id_station", "id_equipment_group"],
            schema=SCHEMA_GENERATION,
        )

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
    """Удаляет station_equipment_group_id из machines."""
    conn = op.get_bind()
    inspector = inspect(conn)
    if inspector.has_table("machines", schema=SCHEMA_GENERATION):
        fks = inspector.get_foreign_keys("machines", schema=SCHEMA_GENERATION)
        fk_names = {fk.get("name") for fk in fks}
        if "fk_machines_station_equipment_group_id" in fk_names:
            op.drop_constraint(
                "fk_machines_station_equipment_group_id",
                "machines",
                schema=SCHEMA_GENERATION,
                type_="foreignkey",
            )

    op.drop_index(
        "ix_machine_station_equipment_group_id",
        table_name="machines",
        schema=SCHEMA_GENERATION,
    )

    op.drop_column(
        "machines",
        "station_equipment_group_id",
        schema=SCHEMA_GENERATION,
    )

    if inspector.has_table("station_equipment_groups", schema=SCHEMA_GENERATION):
        uqs = inspector.get_unique_constraints("station_equipment_groups", schema=SCHEMA_GENERATION)
        uq_names = {uq.get("name") for uq in uqs}
        if "uq_station_equipment_groups_station_equipment_group" in uq_names:
            op.drop_constraint(
                "uq_station_equipment_groups_station_equipment_group",
                "station_equipment_groups",
                schema=SCHEMA_GENERATION,
                type_="unique",
            )
