# -*- coding: utf-8 -*-
"""Скрипт для получения списка таблиц в схеме gs_gen."""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    query = text("""
        SELECT table_name, 
               (SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = 'gs_gen' 
                  AND columns.table_name = tables.table_name 
                  AND column_name = 'database_version_id') as has_version_column
        FROM information_schema.tables
        WHERE table_schema = 'gs_gen'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    result = conn.execute(query).fetchall()
    
    print("Таблицы в схеме generation:")
    print("=" * 60)
    
    for table_name, has_version in result:
        status = "✅ Есть database_version_id" if has_version else "❌ Нет database_version_id"
        print(f"{table_name:<40} {status}")
    
    print("=" * 60)
    print(f"Всего таблиц: {len(result)}")
    print(f"С версионированием: {sum(1 for _, has_version in result if has_version)}")

