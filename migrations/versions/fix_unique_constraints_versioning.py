# -*- coding: utf-8 -*-
"""Fix unique constraints to include database_version_id

Revision ID: f9c3a1e4b2d7
Revises: 
Create Date: 2025-10-21 14:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9c3a1e4b2d7'
down_revision = 'a6082bbb93e5'
branch_labels = None
depends_on = None


def upgrade():
    """
    Исправление ограничений уникальности для поддержки версионирования.
    Добавляет database_version_id во все UNIQUE constraints.
    """
    
    # ============================================================
    # ТАБЛИЦА: stations
    # ============================================================
    
    # 1. uq_station_name_district
    op.drop_constraint('uq_station_name_district', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'uq_station_name_district_version',
        'stations',
        ['name', 'id_regional_district', 'database_version_id'],
        schema='generation'
    )
    
    # 2. stations_kto_key
    op.drop_constraint('stations_kto_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_kto_version_key',
        'stations',
        ['kto', 'database_version_id'],
        schema='generation'
    )
    
    # 3. stations_location_key
    op.drop_constraint('stations_location_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_location_version_key',
        'stations',
        ['location', 'database_version_id'],
        schema='generation'
    )
    
    # 4. stations_name_archive_key
    op.drop_constraint('stations_name_archive_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_name_archive_version_key',
        'stations',
        ['name_archive', 'database_version_id'],
        schema='generation'
    )
    
    # 5. stations_name_combined_key
    op.drop_constraint('stations_name_combined_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_name_combined_version_key',
        'stations',
        ['name_combined', 'database_version_id'],
        schema='generation'
    )
    
    # 6. stations_name_so_key
    op.drop_constraint('stations_name_so_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_name_so_version_key',
        'stations',
        ['name_so', 'database_version_id'],
        schema='generation'
    )
    
    # ============================================================
    # ТАБЛИЦА: documents_kommod
    # ============================================================
    
    # documents_kommod_name_key
    op.drop_constraint('documents_kommod_name_key', 'documents_kommod', schema='generation', type_='unique')
    op.create_unique_constraint(
        'documents_kommod_name_version_key',
        'documents_kommod',
        ['name', 'database_version_id'],
        schema='generation'
    )


def downgrade():
    """
    Откат изменений - возврат к старым ограничениям уникальности.
    ВНИМАНИЕ: Откат может привести к потере данных, если в разных версиях есть дубликаты!
    """
    
    # ============================================================
    # ТАБЛИЦА: documents_kommod
    # ============================================================
    
    op.drop_constraint('documents_kommod_name_version_key', 'documents_kommod', schema='generation', type_='unique')
    op.create_unique_constraint(
        'documents_kommod_name_key',
        'documents_kommod',
        ['name'],
        schema='generation'
    )
    
    # ============================================================
    # ТАБЛИЦА: stations
    # ============================================================
    
    op.drop_constraint('stations_name_so_version_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_name_so_key',
        'stations',
        ['name_so'],
        schema='generation'
    )
    
    op.drop_constraint('stations_name_combined_version_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_name_combined_key',
        'stations',
        ['name_combined'],
        schema='generation'
    )
    
    op.drop_constraint('stations_name_archive_version_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_name_archive_key',
        'stations',
        ['name_archive'],
        schema='generation'
    )
    
    op.drop_constraint('stations_location_version_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_location_key',
        'stations',
        ['location'],
        schema='generation'
    )
    
    op.drop_constraint('stations_kto_version_key', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'stations_kto_key',
        'stations',
        ['kto'],
        schema='generation'
    )
    
    op.drop_constraint('uq_station_name_district_version', 'stations', schema='generation', type_='unique')
    op.create_unique_constraint(
        'uq_station_name_district',
        'stations',
        ['name', 'id_regional_district'],
        schema='generation'
    )

