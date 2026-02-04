"""simplify ues external mappings schema

Revision ID: c1d2e3f4a5b7
Revises: b1c2d3e4f5a6
Create Date: 2026-01-29 00:00:00.000000
"""

from alembic import op

from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    # Drop constraints/indexes tied to legacy columns
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP CONSTRAINT IF EXISTS uq_ues_extmap_source_id_version"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP CONSTRAINT IF EXISTS uq_ues_extmap_ues_source_version"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP CONSTRAINT IF EXISTS gs_union_energy_system_external_mappings_union_energy_system_id_fkey"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP CONSTRAINT IF EXISTS gs_union_energy_system_external_mappings_database_version_id_fkey"
    )

    op.execute(
        f"DROP INDEX IF EXISTS {SCHEMA_FUEL}.ix_ues_external_mappings_union_energy_system_id"
    )
    op.execute(
        f"DROP INDEX IF EXISTS {SCHEMA_FUEL}.ix_ues_external_mappings_external_source"
    )
    op.execute(
        f"DROP INDEX IF EXISTS {SCHEMA_FUEL}.ix_ues_external_mappings_database_version_id"
    )

    # Drop legacy columns
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS union_energy_system_id"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS external_source"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS local_name_snapshot"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS created_at"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS updated_at"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS created_by"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS modified_by"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS database_version_id"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "DROP COLUMN IF EXISTS version"
    )


def downgrade():
    # Best-effort rollback: restore legacy columns (nullable to avoid failures)
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS union_energy_system_id integer"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS external_source varchar(80) DEFAULT 'external'"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS local_name_snapshot varchar(80)"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS created_at timestamp with time zone DEFAULT now()"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now()"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS created_by varchar(255)"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS modified_by varchar(255)"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS database_version_id integer"
    )
    op.execute(
        f"ALTER TABLE {SCHEMA_FUEL}.gs_union_energy_system_external_mappings "
        "ADD COLUMN IF NOT EXISTS version integer DEFAULT 1"
    )
