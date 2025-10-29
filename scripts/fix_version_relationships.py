#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для исправления связей между таблицами в существующих версиях БД.

Этот скрипт исправляет проблему, когда при копировании версий
связи между таблицами (например, между станциями и машинами) 
не обновляются корректно.

Использование:
    python scripts/fix_version_relationships.py [version_id]
    
Если version_id не указан, исправляются все версии кроме базовой (NULL).
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import fix_version_relationships
from app.logs.services.logging_service import log_to_db

def main():
    """Основная функция скрипта."""
    app = create_app()
    
    with app.app_context():
        # Получаем ID версии из аргументов командной строки
        version_id = None
        if len(sys.argv) > 1:
            try:
                version_id = int(sys.argv[1])
            except ValueError:
                print(f"Ошибка: '{sys.argv[1]}' не является корректным ID версии")
                return 1
        
        # Создаем системного пользователя для логирования
        system_user = type('User', (), {
            'id': 0,
            'username': 'system_script',
            'email': 'system@script.local'
        })()
        
        if version_id:
            # Исправляем конкретную версию
            try:
                version = db.session.get(DatabaseVersion, version_id)
                if not version:
                    print(f"Версия с ID {version_id} не найдена")
                    return 1
                
                print(f"Исправление связей для версии: {version.name} (v{version.version_number})")
                fix_version_relationships(version_id, system_user)
                print(f"✅ Версия {version.name} успешно исправлена")
                
            except Exception as e:
                print(f"❌ Ошибка исправления версии {version_id}: {e}")
                return 1
        else:
            # Исправляем все версии кроме базовой
            versions = DatabaseVersion.query.filter(
                DatabaseVersion.id.isnot(None),
                DatabaseVersion.id > 0
            ).all()
            
            if not versions:
                print("Версии для исправления не найдены")
                return 0
            
            print(f"Найдено версий для исправления: {len(versions)}")
            
            success_count = 0
            error_count = 0
            
            for version in versions:
                try:
                    print(f"Исправление версии: {version.name} (v{version.version_number})...")
                    fix_version_relationships(version.id, system_user)
                    print(f"✅ Версия {version.name} успешно исправлена")
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ Ошибка исправления версии {version.name}: {e}")
                    error_count += 1
            
            print(f"\nРезультат:")
            print(f"✅ Успешно исправлено: {success_count}")
            print(f"❌ Ошибок: {error_count}")
            
            if error_count > 0:
                return 1
        
        return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
