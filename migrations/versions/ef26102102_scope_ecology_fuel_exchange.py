"""Раздельные пакеты действующих и новых ТЭС.

Revision ID: ef26102102
Revises: ee26102103
"""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ECOLOGY

revision = "ef26102102"
down_revision = "ee26102103"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("gs_eco_fuel_snapshots", "gs_eco_fuel_submissions"):
        op.add_column(table, sa.Column("scope", sa.String(20), nullable=False, server_default="operating"), schema=SCHEMA_ECOLOGY)
    op.drop_constraint("uq_eco_fuel_snapshot_version_year", "gs_eco_fuel_snapshots", schema=SCHEMA_ECOLOGY, type_="unique")
    op.create_unique_constraint("uq_eco_fuel_snapshot_version_year_scope", "gs_eco_fuel_snapshots", ["database_version_id", "year_number", "scope"], schema=SCHEMA_ECOLOGY)
    op.drop_index("ix_eco_fuel_submission_version_year_status", table_name="gs_eco_fuel_submissions", schema=SCHEMA_ECOLOGY)
    op.create_index("ix_eco_fuel_submission_version_year_scope_status", "gs_eco_fuel_submissions", ["database_version_id", "year_number", "scope", "status"], schema=SCHEMA_ECOLOGY)


def downgrade():
    # Не удаляем принятые пакеты новых ТЭС при откате схемы.
    connection = op.get_bind()
    for table in ("gs_eco_fuel_snapshots", "gs_eco_fuel_submissions"):
        count = connection.execute(sa.text(f'SELECT count(*) FROM "{SCHEMA_ECOLOGY}"."{table}" WHERE scope != :scope'), {"scope": "operating"}).scalar_one()
        if count:
            raise RuntimeError("Откат невозможен: имеются пакеты новых ТЭС")
    op.drop_index("ix_eco_fuel_submission_version_year_scope_status", table_name="gs_eco_fuel_submissions", schema=SCHEMA_ECOLOGY)
    op.create_index("ix_eco_fuel_submission_version_year_status", "gs_eco_fuel_submissions", ["database_version_id", "year_number", "status"], schema=SCHEMA_ECOLOGY)
    op.drop_constraint("uq_eco_fuel_snapshot_version_year_scope", "gs_eco_fuel_snapshots", schema=SCHEMA_ECOLOGY, type_="unique")
    op.create_unique_constraint("uq_eco_fuel_snapshot_version_year", "gs_eco_fuel_snapshots", ["database_version_id", "year_number"], schema=SCHEMA_ECOLOGY)
    for table in ("gs_eco_fuel_snapshots", "gs_eco_fuel_submissions"):
        op.drop_column(table, "scope", schema=SCHEMA_ECOLOGY)
