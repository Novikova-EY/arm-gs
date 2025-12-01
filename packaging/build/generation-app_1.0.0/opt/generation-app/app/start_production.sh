#!/bin/bash
# -*- coding: utf-8 -*-
"""
Скрипт запуска приложения в production-режиме с Gunicorn
"""

# Активация виртуального окружения
source venv/bin/activate

# Установка production окружения
export FLASK_ENV=production

# Установка переменных окружения для оптимальной работы
export GUNICORN_WORKERS=${GUNICORN_WORKERS:-$(( $(nproc) * 2 + 1 ))}
export GUNICORN_WORKER_CLASS=${GUNICORN_WORKER_CLASS:-gevent}
export GUNICORN_THREADS=${GUNICORN_THREADS:-4}
export GUNICORN_WORKER_CONNECTIONS=${GUNICORN_WORKER_CONNECTIONS:-1000}

# Запуск Gunicorn
echo "============================================================"
echo "Starting application with Gunicorn"
echo "Environment: PRODUCTION"
echo "============================================================"
echo "Workers: $GUNICORN_WORKERS"
echo "Worker class: $GUNICORN_WORKER_CLASS"
echo "Threads per worker: $GUNICORN_THREADS"
echo "============================================================"

gunicorn --config gunicorn_config.py "run:app"

