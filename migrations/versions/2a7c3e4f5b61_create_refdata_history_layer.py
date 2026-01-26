"""create refdata history layer

Revision ID: 2a7c3e4f5b61
Revises: 19c0f94da999
Create Date: 2026-01-22 12:00:00.000000

Creates base refdata history tables:
- gs_refdata_entities: UUID registry for refdata items
- gs_refdata_entity_years: yearly snapshots
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func
from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "2a7c3e4f5b61"
down_revision = "19c0f94da999"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gs_refdata_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("ref_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "database_version_id",
            name="uq_refdata_entities_type_id_version",
        ),
        sa.UniqueConstraint("ref_uuid", name="uq_refdata_entities_uuid"),
        schema=SCHEMA_REFDATA,
    )

    op.create_index(
        op.f("ix_gs_refdata_entities_entity_type"),
        "gs_refdata_entities",
        ["entity_type"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        op.f("ix_gs_refdata_entities_entity_id"),
        "gs_refdata_entities",
        ["entity_id"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        op.f("ix_gs_refdata_entities_database_version_id"),
        "gs_refdata_entities",
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        op.f("ix_gs_refdata_entities_ref_uuid"),
        "gs_refdata_entities",
        ["ref_uuid"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )

    op.create_table(
        "gs_refdata_entity_years",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("refdata_entity_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["refdata_entity_id"],
            [f"{SCHEMA_REFDATA}.gs_refdata_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "refdata_entity_id",
            "year",
            "database_version_id",
            name="uq_refdata_entity_years_entity_year_version",
        ),
        schema=SCHEMA_REFDATA,
    )

    op.create_index(
        op.f("ix_gs_refdata_entity_years_refdata_entity_id"),
        "gs_refdata_entity_years",
        ["refdata_entity_id"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        op.f("ix_gs_refdata_entity_years_year"),
        "gs_refdata_entity_years",
        ["year"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )
    op.create_index(
        op.f("ix_gs_refdata_entity_years_database_version_id"),
        "gs_refdata_entity_years",
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_index(
        op.f("ix_gs_refdata_entity_years_database_version_id"),
        table_name="gs_refdata_entity_years",
        schema=SCHEMA_REFDATA,
    )
    op.drop_index(
        op.f("ix_gs_refdata_entity_years_year"),
        table_name="gs_refdata_entity_years",
        schema=SCHEMA_REFDATA,
    )
    op.drop_index(
        op.f("ix_gs_refdata_entity_years_refdata_entity_id"),
        table_name="gs_refdata_entity_years",
        schema=SCHEMA_REFDATA,
    )
    op.drop_table("gs_refdata_entity_years", schema=SCHEMA_REFDATA)

    op.drop_index(
        op.f("ix_gs_refdata_entities_ref_uuid"),
        table_name="gs_refdata_entities",
        schema=SCHEMA_REFDATA,
    )
    op.drop_index(
        op.f("ix_gs_refdata_entities_database_version_id"),
        table_name="gs_refdata_entities",
        schema=SCHEMA_REFDATA,
    )
    op.drop_index(
        op.f("ix_gs_refdata_entities_entity_id"),
        table_name="gs_refdata_entities",
        schema=SCHEMA_REFDATA,
    )
    op.drop_index(
        op.f("ix_gs_refdata_entities_entity_type"),
        table_name="gs_refdata_entities",
        schema=SCHEMA_REFDATA,
    )
    op.drop_table("gs_refdata_entities", schema=SCHEMA_REFDATA)
