# -*- coding: utf-8 -*-
"""
Скрипт для проверки результатов очистки данных с database_version = NULL.
"""

import sys
import os

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
        print("ПРОВЕРКА РЕЗУЛЬТАТОВ ОЧИСТКИ ДАННЫХ С database_version = NULL")
        print("=" * 80)
        
        # Получаем список всех таблиц с database_version_id
        query = text("""
            SELECT 
                table_schema,
                table_name
            FROM information_schema.columns 
            WHERE column_name = 'database_version_id'
            AND table_schema IN ('generation', 'refdata')
            ORDER BY table_schema, table_name
        """)
        
        result = db.session.execute(query)
        tables = [f"{row[0]}.{row[1]}" for row in result]
        
        print(f"Проверка {len(tables)} таблиц...")
        print()
        
        total_null_records = 0
        tables_with_null = []
        
        for table in tables:
            count_query = text(f"""
                SELECT COUNT(*) 
                FROM {table} 
                WHERE database_version_id IS NULL
            """)
            
            count = db.session.execute(count_query).scalar()
            total_null_records += count
            
            if count > 0:
                tables_with_null.append((table, count))
                print(f"❌ {table}: {count} записей с database_version_id = NULL")
            else:
                print(f"✅ {table}: 0 записей с database_version_id = NULL")
        
        print()
        print("=" * 80)
        
        if total_null_records == 0:
            print("🎉 УСПЕХ! Все данные с database_version_id = NULL успешно удалены!")
            print("✅ База данных очищена от ненужных данных.")
        else:
            print(f"⚠️  ВНИМАНИЕ! Осталось {total_null_records} записей с database_version_id = NULL")
            print("Таблицы с оставшимися записями:")
            for table, count in tables_with_null:
                print(f"  - {table}: {count} записей")
        
        print("=" * 80)

if __name__ == "__main__":
    main()
