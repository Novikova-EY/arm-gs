"""add equipment_group_toplivo_param table

Revision ID: x1y2z3a4b5c6d7
Revises: w0x1y2z3a4b5c6
Create Date: 2026-02-24 20:00:00.000000

Создаёт таблицу gs_fue_equipment_group_toplivo_param в схеме gs_fue.
Одна запись на одну связь EquipmentGroupSetStation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import NUMERIC
from config import SCHEMA_FUEL, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "x1y2z3a4b5c6d7"
down_revision = "w0x1y2z3a4b5c6"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_group_toplivo_param"
SCHEMA = SCHEMA_FUEL
STATIONS_TABLE = "gs_fue_equipment_group_set_stations"


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "equipment_group_set_station_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("name", sa.String(512), nullable=True),
        # Целочисленные
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("obor", sa.Integer(), nullable=True),
        sa.Column("ved", sa.Integer(), nullable=True),
        sa.Column("вед", sa.Integer(), nullable=True),  # вед (cyrillic)
        sa.Column("obl", sa.Integer(), nullable=True),
        sa.Column("dep", sa.Integer(), nullable=True),
        sa.Column("oes", sa.Integer(), nullable=True),
        sa.Column("ees", sa.Integer(), nullable=True),
        sa.Column("er", sa.Integer(), nullable=True),
        sa.Column("gk", sa.Integer(), nullable=True),
        sa.Column("be", sa.Integer(), nullable=True),
        sa.Column("numb1120", sa.Integer(), nullable=True),
        sa.Column("numb1", sa.Integer(), nullable=True),
        # Числовые (Numeric)
        sa.Column("nust", NUMERIC(20, 6), nullable=True),
        sa.Column("nr", NUMERIC(20, 6), nullable=True),
        sa.Column("e", NUMERIC(20, 6), nullable=True),
        sa.Column("eotp", NUMERIC(20, 6), nullable=True),
        sa.Column("eurt", NUMERIC(20, 6), nullable=True),
        sa.Column("eust", NUMERIC(20, 6), nullable=True),
        sa.Column("q", NUMERIC(20, 6), nullable=True),
        sa.Column("turt", NUMERIC(20, 6), nullable=True),
        sa.Column("tust", NUMERIC(20, 6), nullable=True),
        sa.Column("b", NUMERIC(20, 6), nullable=True),
        sa.Column("gaz", NUMERIC(20, 6), nullable=True),
        sa.Column("isk_gaz", NUMERIC(20, 6), nullable=True),
        sa.Column("mazut", NUMERIC(20, 6), nullable=True),
        sa.Column("torf", NUMERIC(20, 6), nullable=True),
        sa.Column("slan", NUMERIC(20, 6), nullable=True),
        sa.Column("proch", NUMERIC(20, 6), nullable=True),
        sa.Column("ugol", NUMERIC(20, 6), nullable=True),
        sa.Column("don", NUMERIC(20, 6), nullable=True),
        sa.Column("podm", NUMERIC(20, 6), nullable=True),
        sa.Column("pech", NUMERIC(20, 6), nullable=True),
        sa.Column("arkt", NUMERIC(20, 6), nullable=True),
        sa.Column("kuzn", NUMERIC(20, 6), nullable=True),
        sa.Column("ural", NUMERIC(20, 6), nullable=True),
        sa.Column("bashk", NUMERIC(20, 6), nullable=True),
        sa.Column("kazah", NUMERIC(20, 6), nullable=True),
        sa.Column("kan", NUMERIC(20, 6), nullable=True),
        sa.Column("tung", NUMERIC(20, 6), nullable=True),
        sa.Column("irkut", NUMERIC(20, 6), nullable=True),
        sa.Column("hak", NUMERIC(20, 6), nullable=True),
        sa.Column("tuv", NUMERIC(20, 6), nullable=True),
        sa.Column("bur", NUMERIC(20, 6), nullable=True),
        sa.Column("chit", NUMERIC(20, 6), nullable=True),
        sa.Column("yakut", NUMERIC(20, 6), nullable=True),
        sa.Column("amur", NUMERIC(20, 6), nullable=True),
        sa.Column("urg", NUMERIC(20, 6), nullable=True),
        sa.Column("ushum", NUMERIC(20, 6), nullable=True),
        sa.Column("prim", NUMERIC(20, 6), nullable=True),
        sa.Column("mag", NUMERIC(20, 6), nullable=True),
        sa.Column("chukot", NUMERIC(20, 6), nullable=True),
        sa.Column("kamch", NUMERIC(20, 6), nullable=True),
        sa.Column("sah", NUMERIC(20, 6), nullable=True),
        sa.Column("qotr", NUMERIC(20, 6), nullable=True),
        sa.Column("snk", NUMERIC(20, 6), nullable=True),
        sa.Column("sn_t", NUMERIC(20, 6), nullable=True),
        sa.Column("ewtp", NUMERIC(20, 6), nullable=True),
        sa.Column("nt", NUMERIC(20, 6), nullable=True),
        sa.Column("nt_sum", NUMERIC(20, 6), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["equipment_group_set_station_id"],
            [f"{SCHEMA}.{STATIONS_TABLE}.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "equipment_group_set_station_id",
            name="uq_equipment_group_toplivo_param_station_link",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_gs_fue_equipment_group_toplivo_param_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    op.drop_index(
        "ix_gs_fue_equipment_group_toplivo_param_database_version_id",
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_table(TABLE, schema=SCHEMA)
