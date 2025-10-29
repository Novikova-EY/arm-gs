"""add_database_version_id_to_all_tables

Revision ID: cf626c919b75
Revises: c5845b674713
Create Date: 2025-10-21 06:22:35.967891

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf626c919b75'
down_revision = 'c5845b674713'
branch_labels = None
depends_on = None


def upgrade():
    # Список таблиц в схеме generation
    generation_tables = [
        'stations',
        'station_powers',
        'station_groups',
        'machines',
        'machine_powers',
        'machine_fuels',
        'machine_tes_types',
        'pgu_machines',
        'pgu_machine_powers',
        'boilers',
        'documents_kommod',
    ]
    
    # Список таблиц в схеме refdata
    refdata_tables = [
        'station_types',
        'union_energy_systems',
        'equipment_groups',
        'technology_availabilities',
        'machine_types',
        'technology_types',
        'synchronous_areas',
        'energy_zones',
        'regional_districts',
        'energy_areas',
        'regional_energy_systems',
        'energy_units',
        'energy_system_types',
        'fuel_categories',
        'fuels',
        'fuel_types',
        'gen_companies',
        'condition_types',
        'pgu_tes_machine_types',
        'tes_machine_types',
        'tes_types',
        'federal_districts',
        'year_features',
        'years',
        'regional_district_regional_energy_system',
    ]
    
    # Добавление столбца database_version_id в таблицы схемы generation
    for table_name in generation_tables:
        op.add_column(table_name, 
                      sa.Column('database_version_id', sa.Integer(), nullable=True),
                      schema='generation')
        op.create_foreign_key(
            f'fk_{table_name}_database_version_id',
            table_name, 'database_versions',
            ['database_version_id'], ['id'],
            source_schema='generation',
            referent_schema='generation',
            ondelete='SET NULL'
        )
        op.create_index(
            op.f(f'ix_generation_{table_name}_database_version_id'),
            table_name,
            ['database_version_id'],
            unique=False,
            schema='generation'
        )
    
    # Добавление столбца database_version_id в таблицы схемы refdata
    for table_name in refdata_tables:
        op.add_column(table_name, 
                      sa.Column('database_version_id', sa.Integer(), nullable=True),
                      schema='refdata')
        op.create_foreign_key(
            f'fk_{table_name}_database_version_id',
            table_name, 'database_versions',
            ['database_version_id'], ['id'],
            source_schema='refdata',
            referent_schema='generation',
            ondelete='SET NULL'
        )
        op.create_index(
            op.f(f'ix_refdata_{table_name}_database_version_id'),
            table_name,
            ['database_version_id'],
            unique=False,
            schema='refdata'
        )


def downgrade():
    # Список таблиц в схеме generation
    generation_tables = [
        'stations',
        'station_powers',
        'station_groups',
        'machines',
        'machine_powers',
        'machine_fuels',
        'machine_tes_types',
        'pgu_machines',
        'pgu_machine_powers',
        'boilers',
        'documents_kommod',
    ]
    
    # Список таблиц в схеме refdata
    refdata_tables = [
        'station_types',
        'union_energy_systems',
        'equipment_groups',
        'technology_availabilities',
        'machine_types',
        'technology_types',
        'synchronous_areas',
        'energy_zones',
        'regional_districts',
        'energy_areas',
        'regional_energy_systems',
        'energy_units',
        'energy_system_types',
        'fuel_categories',
        'fuels',
        'fuel_types',
        'gen_companies',
        'condition_types',
        'pgu_tes_machine_types',
        'tes_machine_types',
        'tes_types',
        'federal_districts',
        'year_features',
        'years',
        'regional_district_regional_energy_system',
    ]
    
    # Удаление из таблиц схемы generation
    for table_name in generation_tables:
        op.drop_index(
            op.f(f'ix_generation_{table_name}_database_version_id'),
            table_name=table_name,
            schema='generation'
        )
        op.drop_constraint(
            f'fk_{table_name}_database_version_id',
            table_name,
            type_='foreignkey',
            schema='generation'
        )
        op.drop_column(table_name, 'database_version_id', schema='generation')
    
    # Удаление из таблиц схемы refdata
    for table_name in refdata_tables:
        op.drop_index(
            op.f(f'ix_refdata_{table_name}_database_version_id'),
            table_name=table_name,
            schema='refdata'
        )
        op.drop_constraint(
            f'fk_{table_name}_database_version_id',
            table_name,
            type_='foreignkey',
            schema='refdata'
        )
        op.drop_column(table_name, 'database_version_id', schema='refdata')
