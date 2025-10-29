# -*- coding: utf-8 -*-
"""
Bulk: fix unique constraints in refdata to be per database_version_id

Revision ID: bulk_refdata_unique_20251029
Revises: fix_rd_unique_20251029
Create Date: 2025-10-29 08:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'bulk_refdata_unique_20251029'
down_revision = 'fix_rd_unique_20251029'
branch_labels = None
depends_on = None


def _drop_if_exists(schema: str, table: str, constraint_names: list[str]):
    conn = op.get_bind()
    for cname in constraint_names:
        conn.execute(sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_namespace n ON n.oid = c.connamespace
                    WHERE c.conname = :cname AND n.nspname = :schema
                ) THEN
                    EXECUTE 'ALTER TABLE ' || quote_ident(:schema) || '.' || quote_ident(:table) ||
                            ' DROP CONSTRAINT ' || quote_ident(:cname);
                END IF;
            END$$;
            """
        ), {"cname": cname, "schema": schema, "table": table})


def upgrade():
    # energy_units
    _drop_if_exists('refdata', 'energy_units', ['energy_units_name_key'])
    op.create_unique_constraint('uq_refdata_energy_units_ver_name', 'energy_units', ['database_version_id', 'name'], schema='refdata')

    # energy_areas
    _drop_if_exists('refdata', 'energy_areas', ['energy_areas_name_key'])
    op.create_unique_constraint('uq_refdata_energy_areas_ver_name', 'energy_areas', ['database_version_id', 'name'], schema='refdata')

    # energy_zones
    _drop_if_exists('refdata', 'energy_zones', ['energy_zones_number_key', 'energy_zones_name_key'])
    op.create_unique_constraint('uq_refdata_energy_zones_ver_number', 'energy_zones', ['database_version_id', 'number'], schema='refdata')
    op.create_unique_constraint('uq_refdata_energy_zones_ver_name', 'energy_zones', ['database_version_id', 'name'], schema='refdata')

    # union_energy_systems
    _drop_if_exists('refdata', 'union_energy_systems', ['union_energy_systems_name_key', 'union_energy_systems_name_full_key'])
    op.create_unique_constraint('uq_refdata_ues_ver_name', 'union_energy_systems', ['database_version_id', 'name'], schema='refdata')
    op.create_unique_constraint('uq_refdata_ues_ver_name_full', 'union_energy_systems', ['database_version_id', 'name_full'], schema='refdata')


def downgrade():
    # union_energy_systems
    op.drop_constraint('uq_refdata_ues_ver_name', 'union_energy_systems', type_='unique', schema='refdata')
    op.drop_constraint('uq_refdata_ues_ver_name_full', 'union_energy_systems', type_='unique', schema='refdata')
    op.create_unique_constraint('union_energy_systems_name_key', 'union_energy_systems', ['name'], schema='refdata')
    op.create_unique_constraint('union_energy_systems_name_full_key', 'union_energy_systems', ['name_full'], schema='refdata')

    # energy_zones
    op.drop_constraint('uq_refdata_energy_zones_ver_number', 'energy_zones', type_='unique', schema='refdata')
    op.drop_constraint('uq_refdata_energy_zones_ver_name', 'energy_zones', type_='unique', schema='refdata')
    op.create_unique_constraint('energy_zones_number_key', 'energy_zones', ['number'], schema='refdata')
    op.create_unique_constraint('energy_zones_name_key', 'energy_zones', ['name'], schema='refdata')

    # energy_areas
    op.drop_constraint('uq_refdata_energy_areas_ver_name', 'energy_areas', type_='unique', schema='refdata')
    op.create_unique_constraint('energy_areas_name_key', 'energy_areas', ['name'], schema='refdata')

    # energy_units
    op.drop_constraint('uq_refdata_energy_units_ver_name', 'energy_units', type_='unique', schema='refdata')
    op.create_unique_constraint('energy_units_name_key', 'energy_units', ['name'], schema='refdata')


