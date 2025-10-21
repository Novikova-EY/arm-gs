"""move_id_station_type_from_machine_to_station

Revision ID: de13c9499a00
Revises: add_version_col
Create Date: 2025-10-20 12:04:04.196845

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'de13c9499a00'
down_revision = 'add_version_col'
branch_labels = None
depends_on = None


def upgrade():
    # Шаг 1: Проверяем и добавляем поле id_station_type в таблицу machines (если его нет)
    # Это нужно для безопасного переноса данных
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Проверяем, есть ли колонка id_station_type в machines
    machines_columns = [col['name'] for col in inspector.get_columns('machines', schema='generation')]
    if 'id_station_type' not in machines_columns:
        # Если колонки нет, значит она уже была удалена - добавляем временно
        op.add_column('machines',
                      sa.Column('id_station_type', sa.Integer(), nullable=True),
                      schema='generation')
        
        op.create_index('ix_machine_id_station_type', 'machines', ['id_station_type'],
                        schema='generation')
        
        op.create_foreign_key('machines_id_station_type_fkey', 'machines', 'station_types',
                              ['id_station_type'], ['id'],
                              source_schema='generation', referent_schema='refdata',
                              ondelete='RESTRICT')
    
    # Шаг 2: Добавляем поле id_station_type в таблицу stations
    stations_columns = [col['name'] for col in inspector.get_columns('stations', schema='generation')]
    if 'id_station_type' not in stations_columns:
        op.add_column('stations', 
                      sa.Column('id_station_type', sa.Integer(), nullable=True),
                      schema='generation')
        
        # Создаем индекс для id_station_type в stations
        op.create_index('ix_station_id_station_type', 'stations', ['id_station_type'], 
                        schema='generation')
        
        # Создаем внешний ключ для id_station_type в stations
        op.create_foreign_key('fk_stations_station_type', 'stations', 'station_types',
                              ['id_station_type'], ['id'],
                              source_schema='generation', referent_schema='refdata',
                              ondelete='RESTRICT')
    
    # Шаг 3: Копируем данные из machines в stations
    # Обновляем stations.id_station_type на основе первого агрегата каждой станции
    op.execute("""
        UPDATE generation.stations s
        SET id_station_type = (
            SELECT m.id_station_type
            FROM generation.machines m
            WHERE m.id_station = s.id
            AND m.id_station_type IS NOT NULL
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 
            FROM generation.machines m 
            WHERE m.id_station = s.id 
            AND m.id_station_type IS NOT NULL
        )
    """)
    
    # Шаг 4: Удаляем внешний ключ machines -> station_types
    op.drop_constraint('machines_id_station_type_fkey', 'machines', 
                      schema='generation', type_='foreignkey')
    
    # Шаг 5: Удаляем индекс для id_station_type в machines
    op.drop_index('ix_machine_id_station_type', table_name='machines', schema='generation')
    
    # Шаг 6: Удаляем поле id_station_type из таблицы machines
    op.drop_column('machines', 'id_station_type', schema='generation')


def downgrade():
    # Шаг 1: Проверяем и добавляем поле id_station_type обратно в таблицу machines
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    machines_columns = [col['name'] for col in inspector.get_columns('machines', schema='generation')]
    if 'id_station_type' not in machines_columns:
        op.add_column('machines',
                      sa.Column('id_station_type', sa.Integer(), nullable=True),
                      schema='generation')
        
        # Создаем индекс для id_station_type в machines
        op.create_index('ix_machine_id_station_type', 'machines', ['id_station_type'],
                        schema='generation')
        
        # Создаем внешний ключ для id_station_type в machines
        op.create_foreign_key('machines_id_station_type_fkey', 'machines', 'station_types',
                              ['id_station_type'], ['id'],
                              source_schema='generation', referent_schema='refdata',
                              ondelete='RESTRICT')
    
    # Шаг 2: Копируем данные обратно из stations в machines
    op.execute("""
        UPDATE generation.machines m
        SET id_station_type = s.id_station_type
        FROM generation.stations s
        WHERE m.id_station = s.id
        AND s.id_station_type IS NOT NULL
    """)
    
    # Шаг 3: Проверяем и удаляем поле id_station_type из таблицы stations
    stations_columns = [col['name'] for col in inspector.get_columns('stations', schema='generation')]
    if 'id_station_type' in stations_columns:
        # Удаляем внешний ключ stations -> station_types
        op.drop_constraint('fk_stations_station_type', 'stations',
                          schema='generation', type_='foreignkey')
        
        # Удаляем индекс для id_station_type в stations
        op.drop_index('ix_station_id_station_type', table_name='stations', schema='generation')
        
        # Удаляем поле id_station_type из таблицы stations
        op.drop_column('stations', 'id_station_type', schema='generation')
