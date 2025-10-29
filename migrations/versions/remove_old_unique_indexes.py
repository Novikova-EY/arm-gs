# -*- coding: utf-8 -*-
"""Remove old unique indexes that block version copying

Revision ID: g1d4b3c6e8f9
Revises: f9c3a1e4b2d7
Create Date: 2025-10-22 07:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1d4b3c6e8f9'
down_revision = 'f9c3a1e4b2d7'
branch_labels = None
depends_on = None


def upgrade():
    """
    Удаление старых уникальных индексов, которые мешают копированию версий.
    Эти индексы были созданы из-за unique=True в моделях, но не включают database_version_id.
    """
    
    # Получаем соединение для проверки существования индексов
    conn = op.get_bind()
    
    # Проверяем и удаляем индексы только если они существуют
    indexes_to_drop = [
        ('ix_generation_documents_kommod_name', 'documents_kommod', 'generation'),
        ('ix_generation_station_groups_name', 'station_groups', 'generation'),
        ('ix_generation_boilers_name', 'boilers', 'generation')
    ]
    
    for index_name, table_name, schema_name in indexes_to_drop:
        # Проверяем существование индекса
        result = conn.execute(sa.text("""
            SELECT 1 FROM pg_indexes 
            WHERE schemaname = :schema 
            AND tablename = :table 
            AND indexname = :index
        """), {"schema": schema_name, "table": table_name, "index": index_name})
        
        if result.fetchone():
            # Индекс существует, удаляем его
            op.drop_index(index_name, table_name=table_name, schema=schema_name)


def downgrade():
    """
    Восстановление старых индексов (НЕ РЕКОМЕНДУЕТСЯ - это сломает версионирование!)
    """
    
    # Восстанавливаем старые уникальные индексы
    op.create_index(
        'ix_generation_boilers_name',
        'boilers',
        ['name'],
        unique=True,
        schema='generation'
    )
    
    op.create_index(
        'ix_generation_station_groups_name',
        'station_groups',
        ['name'],
        unique=True,
        schema='generation'
    )
    
    op.create_index(
        'ix_generation_documents_kommod_name',
        'documents_kommod',
        ['name'],
        unique=True,
        schema='generation'
    )

