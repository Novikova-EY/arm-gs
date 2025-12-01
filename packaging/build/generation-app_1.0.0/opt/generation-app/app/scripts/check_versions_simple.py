# -*- coding: utf-8 -*-
"""
Простой скрипт для проверки версий БД напрямую через SQLAlchemy.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Параметры подключения к БД
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

# Создаем подключение
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)


def main():
    """Основная функция."""
    print("=" * 80)
    print("ПРОВЕРКА ВЕРСИЙ БАЗЫ ДАННЫХ")
    print("=" * 80)
    
    with engine.connect() as conn:
        # Получаем все версии
        versions_query = text("""
            SELECT 
                v.id,
                v.version_number,
                v.name,
                v.description,
                v.parent_version_id,
                v.is_active,
                v.created_at,
                p.version_number as parent_version_number,
                p.name as parent_name
            FROM refdata.database_versions v
            LEFT JOIN refdata.database_versions p ON v.parent_version_id = p.id
            ORDER BY v.version_number
        """)
        
        versions = conn.execute(versions_query).fetchall()
        
        if not versions:
            print("\n⚠️  В базе данных нет версий!")
            return
        
        print(f"\nНайдено версий: {len(versions)}")
        print("-" * 80)
        
        # Таблицы для проверки
        tables = [
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
            'documents_kommod'
        ]
        
        issues = []
        
        # Выводим информацию о каждой версии
        for v in versions:
            version_id = v[0]
            version_number = v[1]
            name = v[2]
            parent_version_id = v[4]
            is_active = v[5]
            parent_version_number = v[7]
            parent_name = v[8]
            
            print(f"\n📊 Версия {version_number}: {name}")
            print(f"   ID: {version_id}")
            
            # Информация о родительской версии
            if parent_version_id:
                if parent_version_number:
                    print(f"   Создана на основе: Версия {parent_version_number} - {parent_name}")
                else:
                    print(f"   ⚠️  parent_version_id={parent_version_id}, но родительская версия не найдена!")
                    issues.append(f"Версия {version_number} ({name}): parent_version_id={parent_version_id} не существует")
            else:
                print(f"   Создана на основе: Новая пустая версия")
            
            print(f"   Активная: {'Да' if is_active else 'Нет'}")
            
            # Считаем записи в каждой таблице
            total_records = 0
            table_counts = {}
            
            for table in tables:
                count_query = text(f"""
                    SELECT COUNT(*) 
                    FROM generation.{table}
                    WHERE database_version_id = :version_id
                """)
                
                count = conn.execute(count_query, {"version_id": version_id}).scalar()
                if count > 0:
                    table_counts[table] = count
                    total_records += count
            
            print(f"\n   Всего записей: {total_records}")
            
            if total_records > 0:
                print("   Распределение по таблицам:")
                for table, count in table_counts.items():
                    print(f"      - {table}: {count}")
            else:
                print("   ⚠️  В этой версии нет данных!")
                
                # Если версия создана на основе другой, но данных нет - это проблема
                if parent_version_id and parent_version_number:
                    # Проверяем, есть ли данные у родителя
                    parent_total = 0
                    for table in tables:
                        count_query = text(f"""
                            SELECT COUNT(*) 
                            FROM generation.{table}
                            WHERE database_version_id = :parent_id
                        """)
                        count = conn.execute(count_query, {"parent_id": parent_version_id}).scalar()
                        parent_total += count
                    
                    if parent_total > 0:
                        issues.append(f"Версия {version_number} ({name}): создана на основе версии {parent_version_number}, но данные не скопированы (у родителя {parent_total} записей)")
            
            print("-" * 80)
        
        # Проверяем данные без версии
        print("\n📊 Данные без привязки к версии (database_version_id IS NULL)")
        null_total = 0
        null_counts = {}
        
        for table in tables:
            count_query = text(f"""
                SELECT COUNT(*) 
                FROM generation.{table}
                WHERE database_version_id IS NULL
            """)
            count = conn.execute(count_query).scalar()
            if count > 0:
                null_counts[table] = count
                null_total += count
        
        print(f"   Всего записей: {null_total}")
        
        if null_total > 0:
            print("   Распределение по таблицам:")
            for table, count in null_counts.items():
                print(f"      - {table}: {count}")
        else:
            print("   ✅ Все данные привязаны к версиям!")
        
        print("\n" + "=" * 80)
        
        # Итоговый отчет о проблемах
        if issues:
            print("\n⚠️  ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
            print("-" * 80)
            for issue in issues:
                print(f"   • {issue}")
            print("\n" + "=" * 80)
            print("\n💡 РЕКОМЕНДАЦИИ:")
            print("   1. Проверьте логи приложения на предмет ошибок при копировании данных")
            print("   2. Убедитесь, что функция копирования вызывается при создании версии")
            print("   3. Проверьте, что parent_version_id корректно передается в сервис")
            print()
        else:
            print("\n✅ Проблем не обнаружено! Все версии корректно настроены.")
            print()
        
        print("=" * 80)


if __name__ == "__main__":
    main()

