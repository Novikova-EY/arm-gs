# -*- coding: utf-8 -*-
"""
Конфигурация Gunicorn для production-окружения с поддержкой многопоточности
и параллельной работы множества пользователей.
"""
import multiprocessing
import os

# Bind address
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Worker processes
# Рекомендация: (2 x CPU cores) + 1
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Worker class
# gevent - для асинхронной обработки запросов
# sync - для синхронной обработки (по умолчанию)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gevent")

# Threads per worker (используется только с sync worker class)
threads = int(os.getenv("GUNICORN_THREADS", 4))

# Worker connections (для async workers)
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", 1000))

# Timeout
# Увеличен таймаут для операций экспорта больших объемов данных
timeout = int(os.getenv("GUNICORN_TIMEOUT", 300))

# Keep alive
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# Maximum requests per worker (для предотвращения утечек памяти)
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 10000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 1000))

# Logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # stdout
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")    # stdout
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "fproject_app"

# Graceful timeout
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))

# Pre-fork hook
def pre_fork(server, worker):
    """
    Called just before a worker is forked.
    """
    pass

# Post-fork hook
def post_fork(server, worker):
    """
    Called just after a worker has been forked.
    Здесь можно инициализировать соединения с БД для каждого worker'а.
    """
    server.log.info("Worker spawned (pid: %s)", worker.pid)

# Worker exit hook
def worker_exit(server, worker):
    """
    Called just after a worker has been exited.
    """
    server.log.info("Worker exited (pid: %s)", worker.pid)

# When worker timeout
def worker_abort(worker):
    """
    Called when a worker received the SIGABRT signal.
    """
    worker.log.warning("Worker timeout (pid: %s)", worker.pid)

