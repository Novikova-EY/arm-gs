#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки состояния базы данных и версий.
"""

import sys
import os

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.common.services.database_version_services import get_current_version
from app.generation.models.station.station_model import Station
from app.extensions import db

def check_database_state():
    """Проверяет состояние базы данных."""
    app = create_app()
    
    with app.app_context():
        print("🔍 Проверка состояния базы данных...")
        
        # Проверяем текущую версию БД
        current_version = get_current_version()
        print(f"📊 Текущая версия БД: {current_version}")
        
        # Проверяем общее количество станций
        total_stations = Station.query.count()
        print(f"📊 Всего станций в БД: {total_stations}")
        
        # Проверяем станции с текущей версией
        if current_version:
            version_stations = Station.query.filter(Station.database_version_id == current_version).count()
            print(f"📊 Станций с версией {current_version}: {version_stations}")
        else:
            null_version_stations = Station.query.filter(Station.database_version_id.is_(None)).count()
            print(f"📊 Станций без версии (NULL): {null_version_stations}")
        
        # Проверяем все версии БД
        from app.common.models.database_version_model import DatabaseVersion
        versions = DatabaseVersion.query.all()
        print(f"📊 Всего версий БД: {len(versions)}")
        for version in versions:
            status = "АКТИВНАЯ" if version.is_active else "неактивная"
            print(f"   - Версия {version.id}: {version.name} ({status})")

if __name__ == "__main__":
    check_database_state()

