"""Исполнитель импорта, независимый от времени жизни веб-сервера."""

from pathlib import Path
import sys

from app import create_app
from app.fuel.services.fuel_imports import fuel_db_import_jobs as jobs


def run(job_id, path):
    app = create_app()
    with app.app_context():
        client = jobs._client()
        job = jobs._read(client, job_id)
        if job is None or job["status"] != "running":
            return
        lock = client.lock(jobs._ACTIVE_KEY, timeout=jobs._LEASE_SECONDS, thread_local=False)
        # Блокировку уже захватил HTTP-обработчик; передаем ее токен исполнителю.
        lock.local.token = job_id.encode()
        lock.reacquire()
        app.logger.info("Запущен исполнитель импорта %s", job_id)
        jobs._run_import(app, client, lock, Path(path), job)


if __name__ == "__main__":
    run(*sys.argv[1:])
