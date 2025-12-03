#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для предоставления прав на переименование таблиц в схеме refdata.

Этот скрипт предоставляет необходимые права текущему пользователю БД
для выполнения миграции переименования таблиц.

Использование:
    python scripts/grant_permissions_for_table_rename.py

Или указать пользователя явно:
    python scripts/grant_permissions_for_table_rename.py --user your_db_user
"""
import os
import sys
import argparse
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Загружаем переменные окружения
load_dotenv()

def grant_permissions(db_user=None, db_host=None, db_port=None, db_name=None, schema='refdata'):
    """
    Предоставить права на переименование таблиц в указанной схеме.
    
    Args:
        db_user: Имя пользователя БД (если None, берется из DB_USER)
        db_host: Хост БД (если None, берется из DB_HOST)
        db_port: Порт БД (если None, берется из DB_PORT)
        db_name: Имя БД (если None, берется из DB_NAME)
        schema: Имя схемы (по умолчанию 'refdata')
    """
    # Получаем параметры подключения
    user = db_user or os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD") or os.getenv("DB_PASS")
    host = db_host or os.getenv("DB_HOST", "localhost")
    port = db_port or os.getenv("DB_PORT", "5432")
    database = db_name or os.getenv("DB_NAME")
    
    if not user:
        print("ОШИБКА: Не указан пользователь БД. Укажите через --user или переменную окружения DB_USER")
        sys.exit(1)
    
    if not database:
        print("ОШИБКА: Не указана база данных. Укажите через переменную окружения DB_NAME")
        sys.exit(1)
    
    if not password:
        print("ОШИБКА: Не указан пароль БД. Укажите через переменную окружения DB_PASSWORD или DB_PASS")
        sys.exit(1)
    
    print(f"Подключение к БД: {host}:{port}/{database} от имени пользователя: {user}")
    
    try:
        # Подключаемся от имени суперпользователя или владельца схемы
        # Для этого можно использовать переменную окружения SUPERUSER или выполнить от postgres
        superuser = os.getenv("DB_SUPERUSER", "postgres")
        superuser_pass = os.getenv("DB_SUPERUSER_PASSWORD", password)
        
        # Пробуем подключиться с текущими учетными данными
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Определяем, есть ли у пользователя права суперпользователя
        cursor.execute("SELECT current_user, usesuper FROM pg_user WHERE usename = current_user;")
        result = cursor.fetchone()
        current_user_name = result[0] if result else user
        is_superuser = result[1] if result else False
        
        print(f"Текущий пользователь: {current_user_name}")
        print(f"Является суперпользователем: {'Да' if is_superuser else 'Нет'}")
        
        if not is_superuser:
            print("\nВНИМАНИЕ: Текущий пользователь не является суперпользователем.")
            print("Попытка предоставить права с текущими привилегиями...")
        
        # Список SQL-команд для выполнения
        commands = [
            # Предоставление прав на существующие таблицы
            f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema} TO {current_user_name};",
            # Предоставление прав на будущие таблицы
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {current_user_name};",
            # Предоставление прав на использование схемы
            f"GRANT USAGE ON SCHEMA {schema} TO {current_user_name};",
            # Предоставление прав на создание объектов в схеме
            f"GRANT CREATE ON SCHEMA {schema} TO {current_user_name};",
            # Предоставление прав на последовательности
            f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema} TO {current_user_name};",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON SEQUENCES TO {current_user_name};",
        ]
        
        print(f"\nПредоставление прав на схему '{schema}'...")
        
        for cmd in commands:
            try:
                print(f"Выполнение: {cmd}")
                cursor.execute(cmd)
                print("  ✓ Успешно")
            except Exception as e:
                error_msg = str(e)
                if "permission denied" in error_msg.lower() or "нет прав" in error_msg.lower():
                    print(f"  ⚠ Предупреждение: {error_msg}")
                    print(f"  Требуются права суперпользователя или владельца схемы.")
                else:
                    print(f"  ✗ Ошибка: {error_msg}")
        
        print("\n✓ Права предоставлены успешно!")
        print("\nТеперь можно выполнить миграцию:")
        print("  flask db upgrade")
        
        cursor.close()
        conn.close()
        
    except psycopg2.OperationalError as e:
        print(f"\n✗ Ошибка подключения к БД: {e}")
        print("\nУбедитесь, что:")
        print("  1. PostgreSQL запущен")
        print("  2. Параметры подключения указаны правильно")
        print("  3. Пользователь имеет права на подключение")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Предоставить права на переименование таблиц в схеме refdata'
    )
    parser.add_argument('--user', help='Имя пользователя БД (по умолчанию из DB_USER)')
    parser.add_argument('--host', help='Хост БД (по умолчанию из DB_HOST)')
    parser.add_argument('--port', help='Порт БД (по умолчанию из DB_PORT)')
    parser.add_argument('--database', help='Имя БД (по умолчанию из DB_NAME)')
    parser.add_argument('--schema', default='refdata', help='Имя схемы (по умолчанию: refdata)')
    
    args = parser.parse_args()
    
    grant_permissions(
        db_user=args.user,
        db_host=args.host,
        db_port=args.port,
        db_name=args.database,
        schema=args.schema
    )

if __name__ == '__main__':
    main()

