# -*- coding: utf-8 -*-
"""
Скрипт запуска приложения с Waitress для Windows.
"""
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run import app
from waitress_config import serve_app

if __name__ == "__main__":
    print("="*60)
    print("Starting Flask application with Waitress (Windows)")
    print("="*60)
    serve_app(app)

