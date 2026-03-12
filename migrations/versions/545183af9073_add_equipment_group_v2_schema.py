"""add equipment group v2 schema

Revision ID: 545183af9073
Revises: f905013835c2
Create Date: 2026-03-04 16:49:30.993690

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "545183af9073"
down_revision = "f905013835c2"
branch_labels = None
depends_on = None


def upgrade():
    # Create v2 equipment group tables only.
    op.create_table(
        "gs_fue_equipment_groups_v2",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("name_ext", sa.String(length=255), nullable=True),
        sa.Column("niv", sa.String(length=255), nullable=True),
        sa.Column("comp", sa.String(length=255), nullable=True),
        sa.Column("main", sa.String(length=255), nullable=True),
        sa.Column("d", sa.String(length=255), nullable=True),
        sa.Column("r", sa.String(length=255), nullable=True),
        sa.Column("forem", sa.String(length=255), nullable=True),
        sa.Column("vedomstvo", sa.String(length=255), nullable=True),
        sa.Column("obl", sa.String(length=80), nullable=True),
        sa.Column("dep", sa.String(length=80), nullable=True),
        sa.Column("id_department", sa.Integer(), nullable=True),
        sa.Column("oes", sa.String(length=80), nullable=True),
        sa.Column("er", sa.String(length=80), nullable=True),
        sa.Column("fo", sa.String(length=80), nullable=True),
        sa.Column("numb", sa.String(length=255), nullable=True),
        sa.Column("tm", sa.String(length=255), nullable=True),
        sa.Column("n1", sa.String(length=255), nullable=True),
        sa.Column("n2", sa.String(length=255), nullable=True),
        sa.Column("p1", sa.String(length=255), nullable=True),
        sa.Column("p2", sa.String(length=255), nullable=True),
        sa.Column("ordnumb", sa.String(length=255), nullable=True),
        sa.Column("addr", sa.String(length=255), nullable=True),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("codegor", sa.String(length=255), nullable=True),
        sa.Column("be", sa.String(length=80), nullable=True),
        sa.Column("gk", sa.String(length=80), nullable=True),
        sa.Column("gkf", sa.String(length=80), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            ["gs_sys.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="gs_fue",
    )
    op.create_table(
        "gs_fue_equipment_group_type_stations_v2",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("equipment_group_type_id", sa.Integer(), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            ["gs_sys.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_group_type_id"],
            ["gs_sys.gs_equipment_groups.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["gs_gen.stations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "station_id",
            "equipment_group_type_id",
            "database_version_id",
            name="uq_eq_group_type_station_version_v2",
        ),
        schema="gs_fue",
    )
    op.create_table(
        "gs_fue_equipment_group_sets_v2",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("equipment_group_id", sa.Integer(), nullable=False),
        sa.Column("equipment_group_set_station_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["equipment_group_id"],
            ["gs_fue.gs_fue_equipment_groups_v2.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_group_set_station_id"],
            ["gs_fue.gs_fue_equipment_group_type_stations_v2.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "equipment_group_id",
            "equipment_group_set_station_id",
            name="uq_equipment_group_set_link_v2",
        ),
        schema="gs_fue",
    )


def downgrade():
    op.drop_table("gs_fue_equipment_group_sets_v2", schema="gs_fue")
    op.drop_table("gs_fue_equipment_group_type_stations_v2", schema="gs_fue")
    op.drop_table("gs_fue_equipment_groups_v2", schema="gs_fue")
