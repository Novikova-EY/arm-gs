#!/usr/bin/env python3
"""
Скрипт для проверки производительности индексов базы данных.
Позволяет оценить эффективность добавленных индексов.
"""

import os
import sys
import time
from sqlalchemy import text

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db

def check_index_performance():
    """Проверка производительности индексов."""
    app = create_app()
    
    with app.app_context():
        print("🔍 Проверка производительности индексов...")
        print("=" * 60)
        
        # Проверяем существование индексов
        check_indexes_exist()
        
        # Тестируем производительность запросов
        test_query_performance()
        
        # Анализируем планы выполнения
        analyze_query_plans()

def check_indexes_exist():
    """Проверка существования индексов."""
    print("\n📋 Проверка существования индексов:")
    
    indexes_to_check = [
        ('ix_machine_powers_station_year', 'generation.machine_powers'),
        ('ix_machine_fuels_machine_year', 'generation.machine_fuels'),
        ('ix_station_powers_station_year', 'generation.station_powers'),
        ('ix_station_regional_district', 'generation.stations'),
        ('ix_machine_id_station', 'generation.machines')
    ]
    
    for index_name, table_name in indexes_to_check:
        query = text("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE indexname = :index_name AND tablename = :table_name
        """)
        
        result = db.session.execute(query, {
            'index_name': index_name,
            'table_name': table_name.split('.')[1]  # Убираем схему
        }).fetchone()
        
        status = "✅" if result else "❌"
        print(f"  {status} {index_name} на {table_name}")

def test_query_performance():
    """Тестирование производительности запросов."""
    print("\n⚡ Тестирование производительности запросов:")
    
    # Тест 1: Запрос мощностей агрегатов по станции и году
    print("\n1. Запрос мощностей агрегатов:")
    start_time = time.time()
    
    query1 = text("""
        SELECT mp.* 
        FROM generation.machine_powers mp
        JOIN generation.machines m ON mp.id_machine = m.id
        WHERE m.id_station = 1 
        AND mp.year_number BETWEEN 2020 AND 2025
        LIMIT 100
    """)
    
    result1 = db.session.execute(query1).fetchall()
    time1 = time.time() - start_time
    print(f"   Время выполнения: {time1:.3f} сек")
    print(f"   Количество записей: {len(result1)}")
    
    # Тест 2: Запрос топлива агрегатов
    print("\n2. Запрос топлива агрегатов:")
    start_time = time.time()
    
    query2 = text("""
        SELECT mf.* 
        FROM generation.machine_fuels mf
        JOIN generation.machines m ON mf.id_machine = m.id
        WHERE m.id_station = 1 
        AND mf.year_number BETWEEN 2020 AND 2025
        LIMIT 100
    """)
    
    result2 = db.session.execute(query2).fetchall()
    time2 = time.time() - start_time
    print(f"   Время выполнения: {time2:.3f} сек")
    print(f"   Количество записей: {len(result2)}")
    
    # Тест 3: Запрос мощностей станции
    print("\n3. Запрос мощностей станции:")
    start_time = time.time()
    
    query3 = text("""
        SELECT sp.* 
        FROM generation.station_powers sp
        WHERE sp.id_station = 1 
        AND sp.year_number BETWEEN 2020 AND 2025
        LIMIT 100
    """)
    
    result3 = db.session.execute(query3).fetchall()
    time3 = time.time() - start_time
    print(f"   Время выполнения: {time3:.3f} сек")
    print(f"   Количество записей: {len(result3)}")

def analyze_query_plans():
    """Анализ планов выполнения запросов."""
    print("\n📊 Анализ планов выполнения:")
    
    queries = [
        ("Запрос мощностей агрегатов", """
            EXPLAIN (ANALYZE, BUFFERS) 
            SELECT mp.* 
            FROM generation.machine_powers mp
            JOIN generation.machines m ON mp.id_machine = m.id
            WHERE m.id_station = 1 
            AND mp.year_number BETWEEN 2020 AND 2025
            LIMIT 100
        """),
        ("Запрос топлива агрегатов", """
            EXPLAIN (ANALYZE, BUFFERS) 
            SELECT mf.* 
            FROM generation.machine_fuels mf
            JOIN generation.machines m ON mf.id_machine = m.id
            WHERE m.id_station = 1 
            AND mf.year_number BETWEEN 2020 AND 2025
            LIMIT 100
        """),
        ("Запрос мощностей станции", """
            EXPLAIN (ANALYZE, BUFFERS) 
            SELECT sp.* 
            FROM generation.station_powers sp
            WHERE sp.id_station = 1 
            AND sp.year_number BETWEEN 2020 AND 2025
            LIMIT 100
        """)
    ]
    
    for query_name, query_sql in queries:
        print(f"\n{query_name}:")
        try:
            result = db.session.execute(text(query_sql)).fetchall()
            for row in result:
                print(f"  {row[0]}")
        except Exception as e:
            print(f"  Ошибка: {e}")

def get_database_stats():
    """Получение статистики базы данных."""
    print("\n📈 Статистика базы данных:")
    
    try:
        # Размер таблиц
        size_query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables 
            WHERE schemaname IN ('generation', 'refdata')
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 10
        """)
        
        result = db.session.execute(size_query).fetchall()
        print("\nТоп-10 таблиц по размеру:")
        for row in result:
            print(f"  {row[1]}: {row[2]}")
    except Exception as e:
        print(f"  Ошибка получения статистики: {e}")

if __name__ == "__main__":
    try:
        check_index_performance()
        get_database_stats()
        print("\n✅ Проверка завершена успешно!")
    except Exception as e:
        print(f"\n❌ Ошибка при проверке: {e}")
        sys.exit(1)
