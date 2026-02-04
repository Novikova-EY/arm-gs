"""add equipment_group_sets

Revision ID: b8c9d0e1f2a3
Revises: e3c4f5a6b7c8
Create Date: 2026-01-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "e3c4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if not inspector.has_table("equipment_group_sets", schema=SCHEMA_GENERATION):
        op.create_table(
            "equipment_group_sets",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("id_equipment_group", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
            schema=SCHEMA_GENERATION,
        )

        op.create_index(
            "ix_equipment_group_sets_id_equipment_group",
            "equipment_group_sets",
            ["id_equipment_group"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_equipment_group_sets_database_version_id",
            "equipment_group_sets",
            ["database_version_id"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )

    if not inspector.has_table("equipment_group_set_stations", schema=SCHEMA_GENERATION):
        op.create_table(
            "equipment_group_set_stations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("equipment_group_set_id", sa.Integer(), nullable=False),
            sa.Column("station_id", sa.Integer(), nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.ForeignKeyConstraint(
                ["equipment_group_set_id"],
                [f"{SCHEMA_GENERATION}.equipment_group_sets.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["station_id"],
                [f"{SCHEMA_GENERATION}.stations.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint(
                "equipment_group_set_id",
                "station_id",
                name="uq_equipment_group_set_stations_set_station",
            ),
            schema=SCHEMA_GENERATION,
        )

        op.create_index(
            "ix_equipment_group_set_stations_set_id",
            "equipment_group_set_stations",
            ["equipment_group_set_id"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_equipment_group_set_stations_station_id",
            "equipment_group_set_stations",
            ["station_id"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_equipment_group_set_stations_database_version_id",
            "equipment_group_set_stations",
            ["database_version_id"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    if inspector.has_table("equipment_group_set_stations", schema=SCHEMA_GENERATION):
        op.drop_index(
            "ix_equipment_group_set_stations_database_version_id",
            table_name="equipment_group_set_stations",
            schema=SCHEMA_GENERATION,
        )
        op.drop_index(
            "ix_equipment_group_set_stations_station_id",
            table_name="equipment_group_set_stations",
            schema=SCHEMA_GENERATION,
        )
        op.drop_index(
            "ix_equipment_group_set_stations_set_id",
            table_name="equipment_group_set_stations",
            schema=SCHEMA_GENERATION,
        )
        op.drop_table("equipment_group_set_stations", schema=SCHEMA_GENERATION)

    if inspector.has_table("equipment_group_sets", schema=SCHEMA_GENERATION):
        op.drop_index(
            "ix_equipment_group_sets_database_version_id",
            table_name="equipment_group_sets",
            schema=SCHEMA_GENERATION,
        )
        op.drop_index(
            "ix_equipment_group_sets_id_equipment_group",
            table_name="equipment_group_sets",
            schema=SCHEMA_GENERATION,
        )
        op.drop_table("equipment_group_sets", schema=SCHEMA_GENERATION)
