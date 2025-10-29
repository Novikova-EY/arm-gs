#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Копирование данных из одной версии в другую"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*70)
print("КОПИРОВАНИЕ ДАННЫХ МЕЖДУ ВЕРСИЯМИ")
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

# Получить список версий
print("\n📋 ДОСТУПНЫЕ ВЕРСИИ:")
print("-" * 70)
cur.execute("""
    SELECT id, version_number, name, is_active 
    FROM generation.database_versions 
    ORDER BY version_number
""")
versions = cur.fetchall()

if not versions:
    print("❌ Нет версий в системе!")
    cur.close()
    conn.close()
    exit(1)

for v in versions:
    active = " ✓ АКТИВНА" if v[3] else ""
    print(f"  [{v[0]}] Версия {v[1]}: {v[2]}{active}")

# Получить статистику по данным
print("\n📊 СТАТИСТИКА ПО ДАННЫМ:")
print("-" * 70)

# Таблицы для копирования (generation схема)
tables = [
    'stations',
    'station_power',
    'station_groups',
    'machines',
    'machine_power',
    'machine_fuels',
    'machine_tes_types',
    'pgu_machines',
    'pgu_machine_power',
    'boilers',
    'documents'
]

stats = {}
for table in tables:
    try:
        # Подсчет по версиям
        cur.execute(f"""
            SELECT 
                COALESCE(database_version_id, -1) as ver_id,
                COUNT(*) as cnt
            FROM generation.{table}
            GROUP BY database_version_id
        """)
        stats[table] = {}
        for row in cur.fetchall():
            ver_id = "NULL" if row[0] == -1 else row[0]
            stats[table][ver_id] = row[1]
    except:
        stats[table] = {"ERROR": 0}

# Вывод статистики
for table in tables:
    if stats[table]:
        total = sum(v for k, v in stats[table].items() if k != "ERROR")
        print(f"  {table:25} - Всего: {total:5}")
        for ver, cnt in sorted(stats[table].items(), key=lambda x: (x[0] == "NULL", x[0])):
            if ver != "ERROR":
                print(f"    {'':25}   Версия {str(ver):4}: {cnt} записей")

# Выбор исходной версии
print("\n" + "="*70)
print("ШАГ 1: Выберите ИСХОДНУЮ версию (откуда копировать данные)")
print("="*70)
print("\nВведите:")
print("  - ID версии (например: 6)")
print("  - 'NULL' - для данных без версии")
print("  - 'ALL' - для копирования всех данных")

source_input = input("\nИсходная версия: ").strip()

if source_input.upper() == 'NULL':
    source_version_id = None
    source_name = "Данные без версии (NULL)"
    where_source = "database_version_id IS NULL"
elif source_input.upper() == 'ALL':
    source_version_id = 'ALL'
    source_name = "Все данные"
    where_source = "1=1"
else:
    try:
        source_version_id = int(source_input)
        # Проверка существования
        cur.execute("SELECT version_number, name FROM generation.database_versions WHERE id = %s", (source_version_id,))
        result = cur.fetchone()
        if not result:
            print(f"\n❌ ОШИБКА: Версия с ID {source_version_id} не найдена!")
            cur.close()
            conn.close()
            exit(1)
        source_name = f"Версия {result[0]}: {result[1]}"
        where_source = f"database_version_id = {source_version_id}"
    except ValueError:
        print("\n❌ ОШИБКА: Неверный формат ID!")
        cur.close()
        conn.close()
        exit(1)

print(f"\n✓ Выбрана исходная версия: {source_name}")

# Выбор целевой версии
print("\n" + "="*70)
print("ШАГ 2: Выберите ЦЕЛЕВУЮ версию (куда копировать данные)")
print("="*70)
print("\nДоступные версии:")
for v in versions:
    print(f"  [{v[0]}] Версия {v[1]}: {v[2]}")

target_input = input("\nЦелевая версия (ID): ").strip()

try:
    target_version_id = int(target_input)
    # Проверка существования
    cur.execute("SELECT version_number, name FROM generation.database_versions WHERE id = %s", (target_version_id,))
    result = cur.fetchone()
    if not result:
        print(f"\n❌ ОШИБКА: Версия с ID {target_version_id} не найдена!")
        cur.close()
        conn.close()
        exit(1)
    target_name = f"Версия {result[0]}: {result[1]}"
except ValueError:
    print("\n❌ ОШИБКА: Неверный формат ID!")
    cur.close()
    conn.close()
    exit(1)

print(f"\n✓ Выбрана целевая версия: {target_name}")

# Подтверждение
print("\n" + "="*70)
print("ПОДТВЕРЖДЕНИЕ ОПЕРАЦИИ")
print("="*70)
print(f"\n⚠️  ВНИМАНИЕ!")
print(f"\nБудут скопированы данные:")
print(f"  ИЗ: {source_name}")
print(f"  В:  {target_name}")
print(f"\nВсе записи будут ПРОДУБЛИРОВАНЫ с новым database_version_id = {target_version_id}")

confirm = input("\nПродолжить? (да/нет): ").strip().lower()

if confirm not in ['да', 'yes', 'y', 'д']:
    print("\n❌ Отменено пользователем")
    cur.close()
    conn.close()
    exit(0)

# Копирование данных
print("\n" + "="*70)
print("КОПИРОВАНИЕ ДАННЫХ...")
print("="*70)

try:
    total_copied = 0
    
    # Копирование каждой таблицы
    for table in tables:
        try:
            # Получаем структуру таблицы (все колонки кроме id и database_version_id)
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'generation' 
                  AND table_name = '{table}'
                  AND column_name NOT IN ('id', 'database_version_id')
                ORDER BY ordinal_position
            """)
            columns = [row[0] for row in cur.fetchall()]
            
            if not columns:
                print(f"  ⚠️  {table:25} - Нет колонок для копирования")
                continue
            
            columns_str = ", ".join(columns)
            
            # Копирование данных
            copy_query = f"""
                INSERT INTO generation.{table} ({columns_str}, database_version_id)
                SELECT {columns_str}, {target_version_id}
                FROM generation.{table}
                WHERE {where_source}
            """
            
            cur.execute(copy_query)
            copied = cur.rowcount
            total_copied += copied
            
            if copied > 0:
                print(f"  ✓ {table:25} - Скопировано: {copied:5} записей")
            else:
                print(f"  - {table:25} - Нет данных для копирования")
                
        except Exception as e:
            print(f"  ❌ {table:25} - Ошибка: {e}")
    
    # Доп. шаг: перепривязка refdata.fuels.id_fuel_type к целевой версии fuel_types по имени
    try:
        print("\n🔧 Перепривязка refdata.fuels.id_fuel_type к fuel_types целевой версии по имени...")
        cur.execute(
            f"""
            WITH map AS (
                SELECT f.id AS fuel_id, ft_new.id AS new_ft_id
                FROM refdata.fuels f
                JOIN refdata.fuel_types ft_old ON ft_old.id = f.id_fuel_type
                JOIN refdata.fuel_types ft_new
                  ON ft_new.name = ft_old.name
                 AND ft_new.database_version_id = f.database_version_id
                WHERE f.database_version_id = %s
            )
            UPDATE refdata.fuels f
            SET id_fuel_type = m.new_ft_id
            FROM map m
            WHERE f.id = m.fuel_id
              AND f.id_fuel_type IS DISTINCT FROM m.new_ft_id;
            """,
            (target_version_id,)
        )
        fixed_rows = cur.rowcount
        print(f"  ✓ Обновлено связей: {fixed_rows}")

        # Контрольная проверка непривязанных записей
        cur.execute(
            """
            SELECT COUNT(*)
            FROM refdata.fuels f
            LEFT JOIN refdata.fuel_types ft
              ON ft.id = f.id_fuel_type
             AND ft.database_version_id = f.database_version_id
            WHERE f.database_version_id = %s
              AND ft.id IS NULL;
            """,
            (target_version_id,)
        )
        not_mapped_cnt = cur.fetchone()[0]
        if not_mapped_cnt > 0:
            print(f"  ⚠️ Осталось непривязанных строк в refdata.fuels: {not_mapped_cnt}")
        else:
            print("  ✓ Все строки refdata.fuels корректно привязаны к fuel_types целевой версии")
    except Exception as e:
        print(f"  ❌ Ошибка перепривязки fuels.id_fuel_type: {e}")

    # Коммит изменений
    conn.commit()
    
    print("\n" + "="*70)
    print(f"✅ УСПЕШНО! Всего скопировано: {total_copied} записей")
    print("="*70)
    
    # Проверка результата
    print("\n📊 РЕЗУЛЬТАТ:")
    print("-" * 70)
    cur.execute(f"""
        SELECT 
            COALESCE(database_version_id::text, 'NULL') as ver,
            COUNT(*) as cnt
        FROM generation.stations
        GROUP BY database_version_id
        ORDER BY database_version_id NULLS FIRST
    """)
    print("Станции по версиям:")
    for row in cur.fetchall():
        print(f"  Версия {row[0]:4}: {row[1]} станций")
    
    print("\n💡 СЛЕДУЮЩИЕ ШАГИ:")
    print("-" * 70)
    print(f"1. Активируйте целевую версию (ID {target_version_id}) в веб-интерфейсе")
    print("2. Проверьте данные на странице станций")
    print("3. Внесите изменения в данные новой версии")
    print("4. Переключайтесь между версиями для сравнения")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ОШИБКА: {e}")
    print("\nИзменения отменены (rollback)")

cur.close()
conn.close()

print("\n" + "="*70)

