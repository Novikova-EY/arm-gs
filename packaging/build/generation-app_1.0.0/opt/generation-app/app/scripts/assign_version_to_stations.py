#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Назначение версии БД существующим данным (станции, агрегаты и т.д.)"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*70)
print("НАЗНАЧЕНИЕ ВЕРСИИ СУЩЕСТВУЮЩИМ ДАННЫМ")
print("="*70)

# Подключение к БД
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    database=os.getenv("DB_NAME")
)

cur = conn.cursor()

# Получить активную версию
cur.execute("""
    SELECT id, version_number, name 
    FROM refdata.database_versions 
    WHERE is_active = TRUE
""")
active_version = cur.fetchone()

if not active_version:
    print("\n❌ ОШИБКА: Нет активной версии!")
    cur.close()
    conn.close()
    exit(1)

version_id, version_number, version_name = active_version
print(f"\n✓ Активная версия: ID={version_id}, Номер={version_number}, Название='{version_name}'")

# Список таблиц для обработки
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

# Подсчет записей без версии в каждой таблице
print("\n📊 Записи без версии:")
print("-" * 70)
total_null_count = 0
table_counts = {}

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM generation.{table} WHERE database_version_id IS NULL")
    null_count = cur.fetchone()[0]
    table_counts[table] = null_count
    total_null_count += null_count
    if null_count > 0:
        print(f"   {table:25} : {null_count:>6} записей")

if total_null_count == 0:
    print("\n✓ Все данные уже имеют версию!")
    cur.close()
    conn.close()
    exit(0)

print(f"\n   {'ИТОГО':25} : {total_null_count:>6} записей")
print("-" * 70)

print("\n" + "="*70)
print("ВАРИАНТЫ ДЕЙСТВИЙ:")
print("="*70)
print(f"\n1. Назначить ВСЕМ {total_null_count} записям версию #{version_number} ('{version_name}')")
print("2. Создать новую версию и назначить ей часть данных")
print("3. Оставить как есть (данные с NULL доступны во всех версиях)")

choice = input("\nВыберите вариант (1/2/3): ").strip()

if choice == "1":
    confirm = input(f"\n⚠️  ВНИМАНИЕ! Это назначит версию {version_number} всем {total_null_count} записям во всех таблицах.\nПродолжить? (да/нет): ").strip().lower()
    
    if confirm in ['да', 'yes', 'y', 'д']:
        try:
            total_updated = 0
            print("\n🔄 Обновление данных...")
            print("-" * 70)
            
            # Обновление каждой таблицы
            for table in tables:
                if table_counts[table] > 0:
                    cur.execute(f"""
                        UPDATE generation.{table}
                        SET database_version_id = %s 
                        WHERE database_version_id IS NULL
                    """, (version_id,))
                    
                    updated_count = cur.rowcount
                    total_updated += updated_count
                    print(f"   {table:25} : обновлено {updated_count:>6} записей")
            
            conn.commit()
            
            print("-" * 70)
            print(f"\n✅ УСПЕШНО! Всего обновлено: {total_updated} записей")
            print(f"   Все данные теперь привязаны к версии {version_number}")
            
            # Проверка для основных таблиц
            print("\n📊 Результат по основным таблицам:")
            for table in ['stations', 'machines', 'documents_kommod']:
                cur.execute(f"""
                    SELECT database_version_id, COUNT(*) 
                    FROM generation.{table}
                    GROUP BY database_version_id 
                    ORDER BY database_version_id NULLS FIRST
                """)
                results = cur.fetchall()
                if results:
                    print(f"\n   {table}:")
                    for row in results:
                        ver = "NULL (все версии)" if row[0] is None else f"Версия {row[0]}"
                        print(f"      {ver}: {row[1]} записей")
            
        except Exception as e:
            conn.rollback()
            print(f"\n❌ ОШИБКА: {e}")
    else:
        print("\n❌ Отменено пользователем")

elif choice == "2":
    print("\n📝 Для создания новой версии:")
    print("   1. Откройте веб-интерфейс: Управление версиями БД")
    print("   2. Нажмите 'Добавить версию'")
    print("   3. Создайте версию (например, 'Версия 8 - Старые данные')")
    print("   4. Запустите этот скрипт снова и выберите вариант 1")
    
elif choice == "3":
    print("\n✓ Оставлено как есть")
    print("   Данные с database_version_id = NULL доступны во всех версиях")
    
else:
    print("\n❌ Неверный выбор")

cur.close()
conn.close()

print("\n" + "="*70)
print("ВАЖНО: Теперь создайте НОВЫЕ данные для теста версионности!")
print("="*70)
print("""
Когда вы создадите новую станцию или агрегат:
1. Они автоматически получат текущую активную версию
2. Переключите версию на другую
3. Новые данные исчезнут из списка
4. Переключите обратно - данные появятся снова

Это и есть версионность в действии! 🎯

ВАЖНО: Теперь при копировании версии будут копироваться:
✓ Станции
✓ Агрегаты (machines)
✓ Мощности агрегатов (machine_powers)
✓ Типы ТЭС (machine_tes_types)
✓ Топливо (machine_fuels)
✓ ПГУ агрегаты (pgu_machines)
✓ ПГУ мощности (pgu_machine_powers)
✓ Мощности станций (station_powers)
✓ Документы (documents_kommod)
""")

