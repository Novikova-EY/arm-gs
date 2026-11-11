"""Фоновый импорт словаря топлива с общим статусом и блокировкой в Redis."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from flask import g, session
from redis.exceptions import LockError, RedisError
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.fuel.services.fuel_imports.import_fuel_db_equipment_groups_services import (
    import_fuel_db_equipment_groups_from_excel,
)
from app.generation.services.station_services.aggregation_cache import get_redis_client
from app.generation.services.station_services.station_services import clear_station_aggregation_cache


_ACTIVE_KEY = "fuel_db_import:active"
_JOB_PREFIX = "fuel_db_import:job:"
_JOB_TTL = 86400
_LEASE_SECONDS = 120
_INTERRUPTED = (
    "Импорт прерван: потеряна связь с выполняющим его процессом. "
    "Часть данных могла сохраниться. Проверьте журнал перед повторной загрузкой."
)


def _client():
    client = get_redis_client()
    if client is None:
        raise RedisError("Для фонового импорта необходим Redis.")
    return client


def _read(client, job_id):
    raw = client.get(_JOB_PREFIX + job_id)
    return json.loads(raw) if raw else None


def _write(client, job):
    client.setex(_JOB_PREFIX + job["id"], _JOB_TTL, json.dumps(job, ensure_ascii=False))


def get_fuel_db_import_job(job_id, owner_id):
    client = _client()
    job = _read(client, job_id)
    if job is None or job["owner_id"] != str(owner_id):
        return None
    if job["status"] == "running":
        active = client.get(_ACTIVE_KEY)
        if active not in (job_id, job_id.encode()):
            # Проверяем еще раз: исполнитель мог завершиться между двумя чтениями.
            job = _read(client, job_id)
            if job["status"] == "running":
                job.update(status="error", error=_INTERRUPTED, finished_at=time.time())
                _write(client, job)
    return job


def get_active_fuel_db_import_job(owner_id):
    job_id = _client().get(_ACTIVE_KEY)
    if not job_id:
        return None
    if isinstance(job_id, bytes):
        job_id = job_id.decode()
    return get_fuel_db_import_job(job_id, owner_id)


def start_fuel_db_import_job(app, upload, *, owner_id, username, version_id, redirect_url):
    client = _client()
    job_id = str(uuid.uuid4())
    lock = client.lock(_ACTIVE_KEY, timeout=_LEASE_SECONDS, thread_local=False)
    if not lock.acquire(blocking=False, token=job_id):
        existing = get_active_fuel_db_import_job(owner_id)
        if existing is not None:
            return existing
        raise ValueError("Другой импорт БД Топливо уже выполняется. Дождитесь его завершения.")
    path = None
    try:
        folder = Path(app.config.get("UPLOAD_FOLDER", "uploads")) / "fuel_import_jobs"
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, suffix=Path(upload.filename).suffix, delete=False) as target:
            path = Path(target.name)
            upload.save(target)
        if not path.stat().st_size:
            raise ValueError("Выбран пустой файл.")
        job = {
            "id": job_id, "owner_id": str(owner_id), "username": username,
            "database_version_id": version_id, "filename": upload.filename,
            "redirect_url": redirect_url, "status": "running", "detail": "Файл принят. Подготовка импорта...",
            "current": 0, "total": 0, "started_at": time.time(), "finished_at": None,
            "result": None, "error": None,
        }
        _write(client, job)
        _launch_worker(app, path, job)
        return job
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        lock.release()
        raise


def _launch_worker(app, path, job):
    env = os.environ.copy()
    env.update(
        REDIS_URL=app.config["REDIS_URL"],
        SKIP_CACHE_WARMUP="true",
        PYTHONIOENCODING="utf-8",
        PYTHONUNBUFFERED="1",
    )
    options = (
        {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt" else {"start_new_session": True}
    )
    log_path = path.parent / f"{job['id']}.log"
    with log_path.open("ab") as output:
        subprocess.Popen(
            [sys.executable, "-m", "app.fuel.services.fuel_imports.fuel_db_import_worker", job["id"], str(path.resolve())],
            cwd=Path(app.root_path).parent,
            env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            **options,
        )


def _run_import(app, client, lock, path, job):
    stopped = threading.Event()
    lease_lost = threading.Event()

    def renew_lease():
        while not stopped.wait(20):
            try:
                lock.reacquire()
            except RedisError:
                lease_lost.set()
                app.logger.exception("Потеряна блокировка фонового импорта %s", job["id"])
                return

    def progress(detail, current=0, total=0):
        if lease_lost.is_set():
            raise RuntimeError(_INTERRUPTED)
        job.update(detail=detail, current=current, total=total)
        _write(client, job)

    heartbeat = threading.Thread(target=renew_lease, name=f"fuel-import-lease-{job['id'][:8]}", daemon=True)
    heartbeat.start()
    # Не копируем исходный запрос: его upload-поток закроется сразу после HTTP 202.
    with app.test_request_context():
        g.current_db_version = job["database_version_id"]
        session["_user_id"] = job["owner_id"]
        session["username"] = job["username"]
        try:
            with path.open("rb") as stream:
                upload = FileStorage(stream=stream, filename=job["filename"])
                result = import_fuel_db_equipment_groups_from_excel(
                    upload, job["username"], build_report=False, on_progress=progress,
                )
            clear_station_aggregation_cache("после импорта БД Топливо")
            job.update(status="done", detail="Импорт завершен.", result=result)
        except ValueError as exc:
            db.session.rollback()
            job.update(status="error", error=str(exc), detail="Импорт не завершен.")
            app.logger.warning("Ошибка проверки фонового импорта %s: %s", job["id"], exc)
        except Exception:
            db.session.rollback()
            app.logger.exception("Ошибка фонового импорта БД Топливо %s", job["id"])
            job.update(
                status="error", detail="Импорт не завершен.",
                error="Ошибка обработки Excel или записи в БД. Часть данных могла сохраниться. Подробности в журнале сервера.",
            )
        finally:
            job["finished_at"] = time.time()
            try:
                _write(client, job)
            except RedisError:
                app.logger.exception("Не удалось сохранить статус импорта %s", job["id"])
            finally:
                stopped.set()
                heartbeat.join(timeout=15)
                try:
                    lock.release()
                except LockError:
                    app.logger.warning("Блокировка импорта %s уже недоступна", job["id"])
                except RedisError:
                    app.logger.exception("Не удалось освободить блокировку импорта %s", job["id"])
                path.unlink(missing_ok=True)
                db.session.remove()
