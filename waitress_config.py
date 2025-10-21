# -*- coding: utf-8 -*-
"""
Конфигурация Waitress для Windows с поддержкой многопоточности
и параллельной работы множества пользователей.
"""
import os
import multiprocessing

# Host и port для привязки
HOST = os.getenv("WAITRESS_HOST", "0.0.0.0")
PORT = int(os.getenv("WAITRESS_PORT", "8000"))

# Количество потоков
# Рекомендация: (CPU cores * 2) для обработки параллельных запросов
THREADS = int(os.getenv("WAITRESS_THREADS", multiprocessing.cpu_count() * 2))

# Размер очереди соединений
CONNECTION_LIMIT = int(os.getenv("WAITRESS_CONNECTION_LIMIT", 1000))

# Максимальный размер буфера для входящих запросов (в байтах)
RECV_BYTES = int(os.getenv("WAITRESS_RECV_BYTES", 65536))

# Максимальный размер буфера для исходящих ответов (в байтах)
SEND_BYTES = int(os.getenv("WAITRESS_SEND_BYTES", 65536))

# Таймаут канала (секунды)
CHANNEL_TIMEOUT = int(os.getenv("WAITRESS_CHANNEL_TIMEOUT", 120))

# Cleanup interval (секунды)
CLEANUP_INTERVAL = int(os.getenv("WAITRESS_CLEANUP_INTERVAL", 30))

# URL scheme
URL_SCHEME = os.getenv("WAITRESS_URL_SCHEME", "http")

# Expose tracebacks (только для development)
EXPOSE_TRACEBACKS = os.getenv("WAITRESS_EXPOSE_TRACEBACKS", "False").lower() == "true"


def serve_app(app):
    """
    Запуск приложения с Waitress.
    
    Args:
        app: Flask application instance
    """
    from waitress import serve
    
    print(f"Starting Waitress server on {HOST}:{PORT}")
    print(f"Threads: {THREADS}")
    print(f"Connection limit: {CONNECTION_LIMIT}")
    print(f"URL: http://{HOST}:{PORT}")
    
    serve(
        app,
        host=HOST,
        port=PORT,
        threads=THREADS,
        connection_limit=CONNECTION_LIMIT,
        recv_bytes=RECV_BYTES,
        send_bytes=SEND_BYTES,
        channel_timeout=CHANNEL_TIMEOUT,
        cleanup_interval=CLEANUP_INTERVAL,
        url_scheme=URL_SCHEME,
        expose_tracebacks=EXPOSE_TRACEBACKS,
    )

