"""Тесты фоновых заданий импорта сводки потребления."""

from __future__ import annotations

import json

from app.energy_consumption.services import energy_consumption_summary_import_jobs as jobs


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self._store[key] = value

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def scan(self, cursor: int, match: str | None = None, count: int = 100):
        prefix = ""
        if match and match.endswith("*"):
            prefix = match[:-1]
        keys = [k for k in self._store if not prefix or k.startswith(prefix)]
        # Один проход, как у Redis scan с небольшим набором ключей.
        return 0, keys


def test_import_job_visible_across_redis_store(monkeypatch):
    """Статус задания читается из общего Redis (имитация другого воркера Gunicorn)."""
    fake = _FakeRedis()
    monkeypatch.setattr(jobs, "get_redis_client", lambda: fake)

    job_id = "test-job-uuid"
    jobs._write_job(
        job_id,
        {
            "status": "running",
            "versions_done": 2,
            "versions_total": 9,
            "stats": None,
            "error": None,
        },
    )

    loaded = jobs.get_energy_consumption_summary_import_job(job_id)
    assert loaded is not None
    assert loaded["status"] == "running"
    assert loaded["versions_done"] == 2
    assert loaded["versions_total"] == 9

    jobs._patch_job(job_id, versions_done=3)
    again = jobs.get_energy_consumption_summary_import_job(job_id)
    assert again is not None
    assert again["versions_done"] == 3

    raw = fake.get(jobs._job_redis_key(job_id))
    assert raw is not None
    assert json.loads(raw)["versions_done"] == 3


def test_fail_orphaned_import_jobs_marks_running_in_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(jobs, "get_redis_client", lambda: fake)
    jobs._write_job(
        "orphan-1",
        {
            "status": "running",
            "versions_done": 6,
            "versions_total": 9,
            "stats": None,
            "error": None,
        },
    )
    jobs._write_job(
        "done-1",
        {
            "status": "done",
            "versions_done": 9,
            "versions_total": 9,
            "stats": {},
            "error": None,
        },
    )

    marked = jobs.fail_orphaned_energy_consumption_summary_import_jobs()
    assert marked == 1
    orphan = jobs.get_energy_consumption_summary_import_job("orphan-1")
    assert orphan is not None
    assert orphan["status"] == "error"
    assert "перезапущен" in (orphan.get("error") or "")
    done = jobs.get_energy_consumption_summary_import_job("done-1")
    assert done is not None
    assert done["status"] == "done"


def test_import_job_missing_returns_none(monkeypatch):
    monkeypatch.setattr(jobs, "get_redis_client", lambda: _FakeRedis())
    assert jobs.get_energy_consumption_summary_import_job("missing") is None
