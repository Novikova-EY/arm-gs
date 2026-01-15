# -*- coding: utf-8 -*-
"""
Финальный скрипт для удаления всех данных с database_version = NULL.
Удаляет все связанные записи, даже если у них database_version_id != NULL.
"""

import sys
import os
from datetime import datetime

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def main():
    """
    Основная функция скрипта.
    """
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("ФИНАЛЬНЫЙ СКРИПТ ОЧИСТКИ ДАННЫХ С database_version = NULL")
        print("=" * 80)
        print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Проверяем текущее состояние
        print("1. Проверка текущего состояния...")
        
        stations_null = db.session.execute(text("SELECT COUNT(*) FROM gs_gen.stations WHERE database_version_id IS NULL")).scalar()
        machines_null = db.session.execute(text("SELECT COUNT(*) FROM gs_gen.machines WHERE database_version_id IS NULL")).scalar()
        machines_ref_stations_null = db.session.execute(text("""
            SELECT COUNT(*) FROM gs_gen.machines 
            WHERE id_station IN (SELECT id FROM gs_gen.stations WHERE database_version_id IS NULL)
        """)).scalar()
        
        print(f"  - Станций с database_version_id = NULL: {stations_null}")
        print(f"  - Машин с database_version_id = NULL: {machines_null}")
        print(f"  - Машин, ссылающихся на станции с NULL: {machines_ref_stations_null}")
        print()
        
        if stations_null == 0:
            print("✅ Нет станций с database_version_id = NULL. Скрипт завершен.")
            return
        
        # Подтверждение от пользователя
        print("⚠️  ВНИМАНИЕ! Это действие необратимо!")
        print(f"Будет удалено:")
        print(f"  - {stations_null} станций с database_version_id = NULL")
        print(f"  - {machines_ref_stations_null} машин, ссылающихся на эти станции")
        print(f"  - Все связанные записи (мощности, топливо, типы ТЭС и т.д.)")
        print("\nЭтот скрипт удалит ВСЕ связанные записи, даже если у них database_version_id != NULL.")
        response = input("Продолжить? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Операция отменена пользователем.")
            return
        
        # Выполняем удаление
        print("\n2. Выполнение удаления...")
        
        try:
            # Получаем список станций для удаления
            station_ids = db.session.execute(text("""
                SELECT id FROM gs_gen.stations WHERE database_version_id IS NULL
            """)).fetchall()
            station_ids = [row[0] for row in station_ids]
            
            print(f"Найдено {len(station_ids)} станций для удаления")
            
            # Удаляем связанные записи машин
            print("Удаление связанных записей машин...")
            
            # Удаляем machine_fuels
            result = db.session.execute(text("""
                DELETE FROM gs_gen.machine_fuels 
                WHERE id_machine IN (
                    SELECT id FROM gs_gen.machines 
                    WHERE id_station = ANY(:station_ids)
                )
            """), {"station_ids": station_ids})
            print(f"  Удалено machine_fuels: {result.rowcount}")
            
            # Удаляем machine_powers
            result = db.session.execute(text("""
                DELETE FROM gs_gen.machine_powers 
                WHERE id_machine IN (
                    SELECT id FROM gs_gen.machines 
                    WHERE id_station = ANY(:station_ids)
                )
            """), {"station_ids": station_ids})
            print(f"  Удалено machine_powers: {result.rowcount}")
            
            # Удаляем machine_tes_types
            result = db.session.execute(text("""
                DELETE FROM gs_gen.machine_tes_types 
                WHERE id_machine IN (
                    SELECT id FROM gs_gen.machines 
                    WHERE id_station = ANY(:station_ids)
                )
            """), {"station_ids": station_ids})
            print(f"  Удалено machine_tes_types: {result.rowcount}")
            
            # Удаляем машины
            result = db.session.execute(text("""
                DELETE FROM gs_gen.machines 
                WHERE id_station = ANY(:station_ids)
            """), {"station_ids": station_ids})
            print(f"  Удалено машин: {result.rowcount}")
            
            # Удаляем station_powers
            result = db.session.execute(text("""
                DELETE FROM gs_gen.station_powers 
                WHERE id_station = ANY(:station_ids)
            """), {"station_ids": station_ids})
            print(f"  Удалено station_powers: {result.rowcount}")
            
            # Удаляем котлы
            result = db.session.execute(text("""
                DELETE FROM gs_gen.boilers 
                WHERE id_station = ANY(:station_ids)
            """), {"station_ids": station_ids})
            print(f"  Удалено котлов: {result.rowcount}")
            
            # Удаляем документы
            result = db.session.execute(text("""
                DELETE FROM gs_gen.documents_kommod 
                WHERE database_version_id IS NULL
            """))
            print(f"  Удалено документов: {result.rowcount}")
            
            # Удаляем станции
            result = db.session.execute(text("""
                DELETE FROM gs_gen.stations 
                WHERE database_version_id IS NULL
            """))
            print(f"  Удалено станций: {result.rowcount}")
            
            # Удаляем оставшиеся записи из refdata
            print("Удаление оставшихся записей из refdata...")
            
            refdata_tables = [
                'refdata.year_features',
                'refdata.tes_types',
                'refdata.tes_machine_types',
                'refdata.station_types',
                'refdata.pgu_tes_machine_types',
                'refdata.machine_types',
                'refdata.gen_companies',
                'refdata.fuels',
                'refdata.fuel_types',
                'refdata.equipment_groups',
                'refdata.technology_types',
                'refdata.technology_availabilities',
                'refdata.energy_units',
                'refdata.regional_energy_systems',
                'refdata.union_energy_systems',
                'refdata.energy_system_types',
                'refdata.regional_districts',
                'refdata.federal_districts',
                'refdata.synchronous_areas',
                'refdata.energy_zones',
                'refdata.condition_types',
                'refdata.energy_areas',
                'refdata.fuel_categories',
                'refdata.regional_district_regional_energy_system',
                'refdata.years'
            ]
            
            for table in refdata_tables:
                try:
                    result = db.session.execute(text(f"""
                        DELETE FROM {table} 
                        WHERE database_version_id IS NULL
                    """))
                    if result.rowcount > 0:
                        print(f"  Удалено из {table}: {result.rowcount}")
                except Exception as e:
                    print(f"  Ошибка при удалении из {table}: {e}")
            
            # Подтверждаем изменения
            db.session.commit()
            print(f"\n✅ Успешно завершено удаление!")
            print("✅ Изменения сохранены в базе данных.")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Ошибка при удалении: {e}")
            print("❌ Изменения отменены.")
            raise
        
        print(f"\nВремя завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

if __name__ == "__main__":
    main()
