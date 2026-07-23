# -*- coding: utf-8 -*-
"""Фоновые задания импорта сводки потребления из Excel (долгий проход по всем версиям БД)."""

from __future__ import annotations

import json
import threading
import time
import uuid
from copy import deepcopy
from typing import Any, Callable

from flask import Flask, copy_current_request_context

from app.energy_consumption.services.energy_consumption_summary_import_services import (
    import_energy_consumption_summary_from_xlsx_bytes,
)
from app.generation.services.station_services.aggregation_cache import get_redis_client

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}

_JOB_KEY_PREFIX = "ec_summary_import_job:"
_JOB_TTL_SECONDS = 24 * 60 * 60
_ORPHAN_ERROR = (
    "Импорт прерван: сервер приложения был перезапущен во время обработки. "
    "Запустите импорт повторно."
)

# Callback: (versions_done, versions_total, detail | None)
ProgressCallback = Callable[[int, int, str | None], None]


def _job_redis_key(job_id: str) -> str:
    return f"{_JOB_KEY_PREFIX}{job_id}"


def _read_job(job_id: str) -> dict[str, Any] | None:
    client = get_redis_client()
    if client is not None:
        raw = client.get(_job_redis_key(job_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    with _lock:
        job = _jobs.get(job_id)
        return deepcopy(job) if job is not None else None


def _write_job(job_id: str, job: dict[str, Any]) -> None:
    client = get_redis_client()
    if client is not None:
        client.setex(
            _job_redis_key(job_id),
            _JOB_TTL_SECONDS,
            json.dumps(job, ensure_ascii=False),
        )
        return
    with _lock:
        _jobs[job_id] = deepcopy(job)


def _patch_job(job_id: str, **fields: Any) -> None:
    client = get_redis_client()
    if client is not None:
        key = _job_redis_key(job_id)
        raw = client.get(key)
        if raw is None:
            return
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        job = json.loads(raw)
        job.update(fields)
        client.setex(key, _JOB_TTL_SECONDS, json.dumps(job, ensure_ascii=False))
        return
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.update(fields)


def _progress_updater(job_id: str) -> ProgressCallback:
    def _on_progress(done: int, total: int, detail: str | None = None) -> None:
        fields: dict[str, Any] = {
            "versions_done": int(done),
            "versions_total": int(total),
            "heartbeat_at": time.time(),
        }
        if detail is not None:
            fields["progress_detail"] = detail
        _patch_job(job_id, **fields)

    return _on_progress


def fail_orphaned_energy_consumption_summary_import_jobs() -> int:
    """Помечает «running» задания как ошибку после рестарта процесса (daemon-поток уже мёртв)."""
    marked = 0
    client = get_redis_client()
    if client is not None:
        cursor: int = 0
        while True:
            cursor, keys = client.scan(cursor, match=f"{_JOB_KEY_PREFIX}*", count=100)
            for key in keys:
                raw = client.get(key)
                if raw is None:
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    job = json.loads(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if job.get("status") != "running":
                    continue
                job.update(
                    {
                        "status": "error",
                        "error": _ORPHAN_ERROR,
                        "progress_detail": None,
                        "heartbeat_at": time.time(),
                    }
                )
                client.setex(key, _JOB_TTL_SECONDS, json.dumps(job, ensure_ascii=False))
                marked += 1
            if cursor == 0:
                break
    with _lock:
        for job in _jobs.values():
            if job.get("status") != "running":
                continue
            job.update(
                {
                    "status": "error",
                    "error": _ORPHAN_ERROR,
                    "progress_detail": None,
                    "heartbeat_at": time.time(),
                }
            )
            marked += 1
    return marked


def start_energy_consumption_summary_import_job(
    app: Flask,
    raw: bytes,
    *,
    username: str | None = None,
) -> str:
    """Запускает импорт в фоновом потоке; возвращает идентификатор задания."""
    job_id = str(uuid.uuid4())
    _write_job(
        job_id,
        {
            "status": "running",
            "versions_done": 0,
            "versions_total": 0,
            "progress_detail": "чтение Excel…",
            "heartbeat_at": time.time(),
            "stats": None,
            "error": None,
        },
    )

    @copy_current_request_context
    def _run() -> None:
        with app.app_context():
            try:
                stats = import_energy_consumption_summary_from_xlsx_bytes(
                    raw,
                    user=username,
                    on_version_progress=_progress_updater(job_id),
                )
                job = _read_job(job_id)
                if job is None:
                    return
                versions_processed = stats.get("database_versions_processed") or job.get(
                    "versions_done", 0
                )
                _write_job(
                    job_id,
                    {
                        **job,
                        "status": "done",
                        "stats": stats,
                        "versions_done": versions_processed,
                        "versions_total": versions_processed,
                        "progress_detail": None,
                        "error": None,
                    },
                )
            except ValueError as exc:
                job = _read_job(job_id)
                if job is None:
                    return
                _write_job(
                    job_id,
                    {**job, "status": "error", "error": str(exc), "progress_detail": None},
                )
            except Exception:
                app.logger.exception(
                    "Фоновый импорт сводки потребления из Excel (job_id=%s)", job_id
                )
                job = _read_job(job_id)
                if job is None:
                    return
                _write_job(
                    job_id,
                    {
                        **job,
                        "status": "error",
                        "progress_detail": None,
                        "error": (
                            "Не удалось выполнить импорт (ошибка при обработке файла или записи в БД). "
                            "Подробности — в журнале сервера приложения."
                        ),
                    },
                )

    threading.Thread(
        target=_run,
        name=f"ec-summary-import-{job_id[:8]}",
        daemon=True,
    ).start()
    return job_id


def get_energy_consumption_summary_import_job(job_id: str) -> dict[str, Any] | None:
    return _read_job(job_id)
