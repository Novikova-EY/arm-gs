# -*- coding: utf-8 -*-
"""
Скрипт запуска приложения с Waitress для Windows.
"""
import sys
import os

# Устанавливаем production окружение
os.environ['FLASK_ENV'] = 'production'

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from waitress_config import serve_app

# Создаем приложение с production конфигом
app = create_app()

if __name__ == "__main__":
    print("="*60)
    print("Starting Flask application with Waitress (Windows)")
    print("Environment: PRODUCTION")
    print("="*60)
    serve_app(app)

