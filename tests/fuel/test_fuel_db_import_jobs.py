from io import BytesIO
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

from flask import Flask, g, session
from flask.templating import render_template
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from redis.exceptions import LockError, RedisError
import pytest

from app.fuel.routes import fuel_bp
from app.fuel.routes import fuel_db_import_routes as routes
from app.fuel.services.fuel_imports import fuel_db_import_jobs as jobs


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.guard = threading.Lock()

    def get(self, key):
        with self.guard:
            return self.values.get(key)

    def setex(self, key, ttl, value):
        with self.guard:
            self.values[key] = value

    def lock(self, key, **kwargs):
        store = self

        class Lease:
            def acquire(self, *, blocking, token):
                self.token = token
                with store.guard:
                    if key in store.values:
                        return False
                    store.values[key] = token
                    return True

            def reacquire(self):
                if store.get(key) != self.token:
                    raise LockError("lost lease")

            def release(self):
                with store.guard:
                    if store.values.get(key) != self.token:
                        raise LockError("lost lease")
                    del store.values[key]

        return Lease()


@pytest.fixture
def ui(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", LOGIN_DISABLED=True, WTF_CSRF_ENABLED=False, UPLOAD_FOLDER=str(tmp_path))
    login = LoginManager(app)
    login.user_loader(lambda identity: None)
    app.register_blueprint(fuel_bp, url_prefix="/fuel")
    app.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(str(Path(__file__).resolve().parents[2] / "app" / "templates")),
    ])
    fake_redis = FakeRedis()
    user = SimpleNamespace(id="7", username="tester", get_id=lambda: user.id)
    app.context_processor(lambda: {"current_user": user})
    monkeypatch.setattr(routes, "current_user", user)
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 37)
    monkeypatch.setattr(routes, "render_template", render_template)
    monkeypatch.setattr(routes, "log_to_db", Mock())
    monkeypatch.setattr(jobs, "get_redis_client", lambda: fake_redis)
    def launch_worker(app, path, job):
        lock = fake_redis.lock(jobs._ACTIVE_KEY)
        lock.token = job["id"]
        threading.Thread(target=jobs._run_import, args=(app, fake_redis, lock, path, job), daemon=True).start()
    monkeypatch.setattr(jobs, "_launch_worker", launch_worker)
    monkeypatch.setattr(jobs, "clear_station_aggregation_cache", Mock())
    monkeypatch.setattr(jobs.db, "session", SimpleNamespace(rollback=Mock(), remove=Mock()))
    return SimpleNamespace(app=app, client=app.test_client(), redis=fake_redis, user=user, folder=tmp_path)


def upload(ui, *, ajax=True, path="stations_equipment_groups", **fields):
    return ui.client.post(
        f"/fuel/{path}/import_fuel_db",
        data={"file": (BytesIO(b"workbook"), "example.xlsx"), **fields},
        headers={"X-Requested-With": "XMLHttpRequest"} if ajax else {},
    )


def wait_for_job(ui, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        with ui.app.app_context():
            job = jobs.get_fuel_db_import_job(job_id, "7")
        if job["status"] != "running":
            return job
        time.sleep(0.01)
    pytest.fail("Background worker did not finish")


def test_upload_returns_before_import_finishes_and_keeps_version_and_file(ui, monkeypatch):
    gate = threading.Event()
    started = threading.Event()
    observed = {}

    def importer(file, username, *, build_report, on_progress):
        observed.update(version=g.current_db_version, user=session["_user_id"], username=username)
        started.set()
        gate.wait(3)
        observed["raw"] = file.read()
        on_progress("Обработка строк", 25, 100)
        return {"message": "Готово", "processed_rows": 100, "report_bytes": None}

    monkeypatch.setattr(jobs, "import_fuel_db_equipment_groups_from_excel", importer)
    response = upload(ui, union_energy_system_filter="311", start_year="2024")
    try:
        assert response.status_code == 202
        job = response.get_json()["job"]
        assert "owner_id" not in job and "username" not in job
        assert "union_energy_system_filter=311" in job["redirect_url"]
        assert "start_year=2024" in job["redirect_url"]
        assert started.wait(1)
        ui.user.id = "8"
        assert ui.client.get(job["status_url"], headers={"Accept": "application/json"}).status_code == 404
        ui.user.id = "7"
        active = ui.client.get("/fuel/stations_equipment_groups/import_fuel_db/active").get_json()["job"]
        assert active["id"] == job["id"]
        status = ui.client.get(job["status_url"], headers={"Accept": "application/json"})
        assert status.status_code == 200 and status.get_json()["job"]["status"] == "running"
        assert "no-store" in status.headers["Cache-Control"]
    finally:
        gate.set()
    done = wait_for_job(ui, job["id"])
    assert done["status"] == "done"
    assert done["result"]["processed_rows"] == 100
    assert observed == {"version": 37, "user": "7", "username": "tester", "raw": b"workbook"}
    jobs.clear_station_aggregation_cache.assert_called_once()
    deadline = time.monotonic() + 2
    while ui.redis.get(jobs._ACTIVE_KEY) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ui.redis.get(jobs._ACTIVE_KEY) is None
    assert not list(ui.folder.rglob("*.xlsx"))


def test_duplicate_launch_reuses_own_job_and_rejects_another_user(ui, monkeypatch):
    gate = threading.Event()
    calls = []

    def importer(*args, **kwargs):
        calls.append(True)
        gate.wait(3)
        return {"message": "Готово"}

    monkeypatch.setattr(jobs, "import_fuel_db_equipment_groups_from_excel", importer)
    first = upload(ui).get_json()["job"]
    try:
        assert upload(ui).get_json()["job"]["id"] == first["id"]
        ui.user.id = "8"
        response = upload(ui)
        assert response.status_code == 409
        assert "Другой импорт" in response.get_json()["error"]
        assert ui.client.get("/fuel/stations_equipment_groups/import_fuel_db/active").get_json()["job"] is None
    finally:
        ui.user.id = "7"
        gate.set()
    assert wait_for_job(ui, first["id"])["status"] == "done"
    assert len(calls) == 1


@pytest.mark.parametrize("exception,expected", [
    (ValueError("Отсутствует колонка id_station"), "Отсутствует колонка"),
    (RuntimeError("secret database credentials"), "Часть данных могла сохраниться"),
])
def test_worker_errors_are_visible_without_exposing_internal_exception(ui, monkeypatch, exception, expected):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(jobs, "import_fuel_db_equipment_groups_from_excel", fail)
    response = upload(ui)
    job = wait_for_job(ui, response.get_json()["job"]["id"])
    assert job["status"] == "error" and expected in job["error"]
    assert "secret database credentials" not in job["error"]
    jobs.db.session.rollback.assert_called()


def test_status_page_supports_regular_form_submission(ui, monkeypatch):
    monkeypatch.setattr(jobs, "import_fuel_db_equipment_groups_from_excel", lambda *a, **k: {"message": "Готово"})
    response = upload(ui, ajax=False, path="stations_turbines", start_year="2024", end_year="2026")
    assert response.status_code == 302
    page = ui.client.get(response.headers["Location"])
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "fuelDbImportWidget" in html and "Импорт данных БД Топливо" in html
    assert "data-initial-job=" in html and "fuel_db_import.js" in html
    job_id = response.headers["Location"].rsplit("/", 1)[-1]
    job = wait_for_job(ui, job_id)
    assert "/stations_turbines?" in job["redirect_url"]
    assert "start_year=2024" in job["redirect_url"]


def test_lost_worker_is_reported_instead_of_waiting_forever(ui):
    job = {"id": "orphan", "owner_id": "7", "status": "running", "filename": "file.xlsx"}
    ui.redis.setex(jobs._JOB_PREFIX + "orphan", 60, json.dumps(job))
    response = ui.client.get("/fuel/stations_equipment_groups/import_fuel_db/status/orphan", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.get_json()["job"]["status"] == "error"
    assert "Импорт прерван" in response.get_json()["job"]["error"]


@pytest.mark.parametrize("case", ["missing", "wrong_extension", "csrf", "version", "redis"])
def test_rejected_upload_does_not_launch_worker(ui, monkeypatch, case):
    worker = Mock()
    monkeypatch.setattr(jobs, "_launch_worker", worker)
    data = {"file": (BytesIO(b"workbook"), "file.xlsx")}
    if case == "missing":
        data = {}
    elif case == "wrong_extension":
        data["file"] = (BytesIO(b"workbook"), "file.txt")
    elif case == "csrf":
        ui.app.config["WTF_CSRF_ENABLED"] = True
    elif case == "version":
        monkeypatch.setattr(routes, "get_current_db_version_id", lambda: None)
    elif case == "redis":
        monkeypatch.setattr(jobs, "get_redis_client", lambda: None)
    response = ui.client.post("/fuel/stations_equipment_groups/import_fuel_db", data=data, headers={"Accept": "application/json"})
    assert response.status_code == (503 if case == "redis" else 400)
    assert response.get_json()["ok"] is False
    worker.assert_not_called()
    assert not list(ui.folder.rglob("*.xlsx"))


def test_anonymous_user_cannot_start_or_read_jobs(ui):
    ui.app.config["LOGIN_DISABLED"] = False
    ui.app.login_manager.user_loader(lambda identity: None)
    assert upload(ui).status_code == 401
    assert ui.client.get("/fuel/stations_equipment_groups/import_fuel_db/active").status_code == 401
    assert ui.client.get("/fuel/stations_equipment_groups/import_fuel_db/status/unknown").status_code == 401



def test_launcher_detaches_worker_and_redirects_output_to_job_log(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.config["REDIS_URL"] = "redis://localhost:6379/9"
    path = tmp_path / "upload.xlsx"
    path.write_bytes(b"workbook")
    process = Mock()
    monkeypatch.setattr(jobs.subprocess, "Popen", process)

    jobs._launch_worker(app, path, {"id": "job-123"})

    args, kwargs = process.call_args
    assert args[0] == [jobs.sys.executable, "-m", "app.fuel.services.fuel_imports.fuel_db_import_worker", "job-123", str(path.resolve())]
    assert kwargs["cwd"] == Path(app.root_path).parent
    assert kwargs["env"]["REDIS_URL"] == app.config["REDIS_URL"]
    assert kwargs["env"]["SKIP_CACHE_WARMUP"] == "true"
    assert kwargs["stdin"] == jobs.subprocess.DEVNULL
    assert kwargs["stderr"] == jobs.subprocess.STDOUT
    assert kwargs["stdout"].name == str(tmp_path / "job-123.log")
    if os.name == "nt":
        assert kwargs["creationflags"] & jobs.subprocess.DETACHED_PROCESS
        assert kwargs["creationflags"] & jobs.subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        assert kwargs["start_new_session"] is True


def test_worker_takes_over_existing_lock_without_acquiring_another(monkeypatch, tmp_path):
    from app.fuel.services.fuel_imports import fuel_db_import_worker as worker

    app = Flask(__name__)
    job = {"id": "job-123", "status": "running", "database_version_id": 37}
    client = Mock()
    lock = client.lock.return_value
    run_import = Mock()
    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(jobs, "_client", lambda: client)
    monkeypatch.setattr(jobs, "_read", lambda client, job_id: job)
    monkeypatch.setattr(jobs, "_run_import", run_import)

    worker.run("job-123", str(tmp_path / "upload.xlsx"))

    assert lock.local.token == b"job-123"
    lock.reacquire.assert_called_once_with()
    lock.acquire.assert_not_called()
    run_import.assert_called_once_with(app, client, lock, tmp_path / "upload.xlsx", job)


@pytest.mark.parametrize("job", [None, {"status": "done"}, {"status": "error"}])
def test_worker_does_not_restart_finished_or_missing_job(monkeypatch, tmp_path, job):
    from app.fuel.services.fuel_imports import fuel_db_import_worker as worker

    app = Flask(__name__)
    client = Mock()
    run_import = Mock()
    monkeypatch.setattr(worker, "create_app", lambda: app)
    monkeypatch.setattr(jobs, "_client", lambda: client)
    monkeypatch.setattr(jobs, "_read", lambda client, job_id: job)
    monkeypatch.setattr(jobs, "_run_import", run_import)
    worker.run("job-123", str(tmp_path / "upload.xlsx"))
    client.lock.assert_not_called()
    run_import.assert_not_called()
