#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Очистка dump-файлов от удаленных версий БД"""

import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# Пути к директориям с бэкапами
BACKUP_DIRS = [
    'backups/versions',
    'backups/auto',
]

def get_existing_versions():
    """Получает список версий из БД"""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        database=os.getenv('DB_NAME')
    )
    
    cur = conn.cursor()
    cur.execute("""
        SELECT id, version_number, name, snapshot_path 
        FROM generation.database_versions 
        ORDER BY version_number
    """)
    versions = cur.fetchall()
    cur.close()
    conn.close()
    
    return versions

def main():
    print("\n" + "="*70)
    print("ОЧИСТКА DUMP-ФАЙЛОВ ОТ УДАЛЕННЫХ ВЕРСИЙ")
    print("="*70)
    
    # Получаем версии из БД
    versions = get_existing_versions()
    
    print(f"\n📋 Версий в БД: {len(versions)}")
    print("-" * 70)
    
    # Собираем все пути к снимкам из БД
    db_snapshot_paths = set()
    for v_id, v_num, v_name, snapshot_path in versions:
        print(f"  [{v_id}] Версия {v_num}: {v_name}")
        if snapshot_path:
            # Нормализуем путь
            if not os.path.isabs(snapshot_path):
                snapshot_path = str(Path.cwd() / snapshot_path)
            db_snapshot_paths.add(os.path.normpath(snapshot_path))
            print(f"       Снимок: {snapshot_path}")
    
    print(f"\n📂 Снимков в БД: {len(db_snapshot_paths)}")
    
    # Сканируем директории с бэкапами
    print("\n" + "="*70)
    print("ПОИСК DUMP-ФАЙЛОВ")
    print("="*70)
    
    all_dumps = []
    total_size = 0
    
    for backup_dir in BACKUP_DIRS:
        backup_path = Path.cwd() / backup_dir
        if not backup_path.exists():
            print(f"\n⚠️  Директория не найдена: {backup_dir}")
            continue
        
        print(f"\n📁 Сканирую: {backup_dir}")
        print("-" * 70)
        
        dump_files = list(backup_path.glob('*.dump'))
        for dump_file in dump_files:
            size = dump_file.stat().st_size
            total_size += size
            all_dumps.append((dump_file, size))
            print(f"  {dump_file.name:50} {size / 1024 / 1024:>10.2f} МБ")
        
        print(f"  Найдено файлов: {len(dump_files)}")
    
    print(f"\n📊 ВСЕГО dump-файлов: {len(all_dumps)}")
    print(f"   Общий размер: {total_size / 1024 / 1024:.2f} МБ ({total_size / 1024 / 1024 / 1024:.2f} ГБ)")
    
    # Ищем осиротевшие файлы
    print("\n" + "="*70)
    print("ПОИСК ОСИРОТЕВШИХ DUMP-ФАЙЛОВ")
    print("="*70)
    
    orphaned_dumps = []
    orphaned_size = 0
    
    for dump_file, size in all_dumps:
        normalized_path = os.path.normpath(str(dump_file))
        if normalized_path not in db_snapshot_paths:
            orphaned_dumps.append((dump_file, size))
            orphaned_size += size
            print(f"\n❌ Осиротевший: {dump_file.name}")
            print(f"   Путь: {dump_file}")
            print(f"   Размер: {size / 1024 / 1024:.2f} МБ")
    
    if not orphaned_dumps:
        print("\n✅ Осиротевших dump-файлов не найдено!")
        print("   Все файлы привязаны к версиям в БД.")
        return
    
    print("\n" + "="*70)
    print(f"⚠️  НАЙДЕНО ОСИРОТЕВШИХ ФАЙЛОВ: {len(orphaned_dumps)}")
    print(f"   Освободится места: {orphaned_size / 1024 / 1024:.2f} МБ ({orphaned_size / 1024 / 1024 / 1024:.2f} ГБ)")
    print("="*70)
    
    # Запрос на удаление
    response = input("\nУдалить осиротевшие dump-файлы? (да/нет): ").strip().lower()
    
    if response in ['да', 'yes', 'y', 'д']:
        print("\n🗑️  Удаление файлов...")
        print("-" * 70)
        
        deleted_count = 0
        deleted_size = 0
        
        for dump_file, size in orphaned_dumps:
            try:
                dump_file.unlink()
                deleted_count += 1
                deleted_size += size
                print(f"✓ Удален: {dump_file.name}")
            except Exception as e:
                print(f"❌ Ошибка при удалении {dump_file.name}: {e}")
        
        print("\n" + "="*70)
        print(f"✅ ОЧИСТКА ЗАВЕРШЕНА")
        print("="*70)
        print(f"   Удалено файлов: {deleted_count}")
        print(f"   Освобождено места: {deleted_size / 1024 / 1024:.2f} МБ ({deleted_size / 1024 / 1024 / 1024:.2f} ГБ)")
    else:
        print("\n❌ Отменено пользователем")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    main()

