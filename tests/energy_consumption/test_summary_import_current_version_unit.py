from types import SimpleNamespace

import pytest
from flask import Flask, g

from app.energy_consumption.services import energy_consumption_summary_import_jobs as jobs
from app.energy_consumption.services import energy_consumption_summary_import_services as importer


def _forbid_all_versions():
    raise AssertionError("Import must not enumerate database versions")


@pytest.mark.parametrize("version_id", [1, 7, 99])
def test_import_only_passes_current_version_to_processing(monkeypatch, version_id):
    monkeypatch.setattr(importer, "get_current_version", lambda: version_id)
    monkeypatch.setattr(importer, "_database_version_ids_ordered", _forbid_all_versions)
    calls = []

    def process(raw, *, version_ids, import_user, on_version_progress):
        calls.append((raw, version_ids, import_user))
        return {"database_versions_processed": len(version_ids)}

    monkeypatch.setattr(importer, "_import_energy_consumption_summary_from_xlsx_bytes_impl", process)
    result = importer.import_energy_consumption_summary_from_xlsx_bytes(b"xlsx", user="tester")
    assert calls == [(b"xlsx", [version_id], "tester")]
    assert result["database_versions_processed"] == 1


@pytest.mark.parametrize("version_id", [None, 0, -1])
def test_import_without_selected_version_does_not_process_file(monkeypatch, version_id):
    monkeypatch.setattr(importer, "get_current_version", lambda: version_id)
    monkeypatch.setattr(importer, "_database_version_ids_ordered", _forbid_all_versions)
    monkeypatch.setattr(importer, "_import_energy_consumption_summary_from_xlsx_bytes_impl",
                        lambda *args, **kwargs: pytest.fail("No version selected: import must not run"))
    with pytest.raises(ValueError, match="выберите текущую версию"):
        importer.import_energy_consumption_summary_from_xlsx_bytes(b"xlsx", user="tester")


@pytest.mark.parametrize("version_id", [7, None])
def test_background_job_keeps_version_selected_at_start(monkeypatch, version_id):
    app = Flask(__name__)
    app.secret_key = "test"
    pending = []
    processed = []
    monkeypatch.setattr(jobs, "get_redis_client", lambda: None)
    monkeypatch.setattr(jobs, "_jobs", {})
    monkeypatch.setattr(jobs, "get_current_version", lambda: g.current_db_version)
    monkeypatch.setattr(importer, "get_current_version", lambda: g.current_db_version)
    monkeypatch.setattr(importer, "_database_version_ids_ordered", _forbid_all_versions)
    monkeypatch.setattr(jobs.threading, "Thread", lambda *, target, **kwargs: SimpleNamespace(
        start=lambda: pending.append(target)
    ))

    def process(raw, *, version_ids, **kwargs):
        assert g.current_db_version == version_id
        processed.append(version_ids)
        return {"database_versions_processed": len(version_ids)}

    monkeypatch.setattr(importer, "_import_energy_consumption_summary_from_xlsx_bytes_impl", process)
    with app.test_request_context("/import", method="POST"):
        g.current_db_version = version_id
        job_id = jobs.start_energy_consumption_summary_import_job(app, b"xlsx", username="tester")
        g.current_db_version = 99
        assert len(pending) == 1
        pending[0]()
        assert g.current_db_version == 99

    job = jobs.get_energy_consumption_summary_import_job(job_id)
    assert job["database_version_id"] == version_id
    if version_id is None:
        assert processed == []
        assert job["status"] == "error"
        assert "выберите текущую версию" in job["error"]
    else:
        assert processed == [[version_id]]
        assert job["status"] == "done"
        assert job["versions_done"] == job["versions_total"] == 1


def test_explicit_all_versions_recalculation_is_separate_from_import(monkeypatch):
    monkeypatch.setattr(importer, "_database_version_ids_ordered", lambda: [1, 7, 99])
    monkeypatch.setattr(importer, "_database_version_ids_for_energy_consumption_import",
                        lambda: pytest.fail("Explicit all-version operation must not use import scope"))
    monkeypatch.setattr(importer, "_year_numbers_for_version", lambda version: {2024})
    calls = []

    def persist(*, database_version_id, **kwargs):
        calls.append(database_version_id)
        return 1

    monkeypatch.setattr(importer, "persist_all_energy_consumption_summary_computed_rows", persist)
    result = importer.persist_all_energy_consumption_summary_computed_rows_for_all_versions()
    assert calls == [1, 7, 99]
    assert result["database_version_ids"] == calls
