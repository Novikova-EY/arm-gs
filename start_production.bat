@echo off
REM Скрипт запуска приложения в production-режиме с Waitress для Windows

REM Активация виртуального окружения
call venv\Scripts\activate.bat

REM Установка переменных окружения для оптимальной работы
if not defined WAITRESS_HOST set WAITRESS_HOST=0.0.0.0
if not defined WAITRESS_PORT set WAITRESS_PORT=8000
if not defined WAITRESS_THREADS set WAITRESS_THREADS=16
if not defined WAITRESS_CONNECTION_LIMIT set WAITRESS_CONNECTION_LIMIT=1000

REM Запуск Waitress
echo ============================================================
echo Starting application with Waitress (Windows)
echo ============================================================
echo Host: %WAITRESS_HOST%
echo Port: %WAITRESS_PORT%
echo Threads: %WAITRESS_THREADS%
echo Connection limit: %WAITRESS_CONNECTION_LIMIT%
echo ============================================================

python start_waitress.py

