from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


RUN_PATH = Path(__file__).resolve().parents[1] / "run.py"


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("custom_address", [False, True])
def test_direct_start_keeps_debug_without_reloader(monkeypatch, debug, custom_address):
    application = SimpleNamespace(config={"DEBUG": debug}, run=Mock())
    monkeypatch.setattr("app.create_app", lambda: application)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    if custom_address:
        monkeypatch.setenv("FLASK_RUN_HOST", "0.0.0.0")
        monkeypatch.setenv("FLASK_RUN_PORT", "5050")
    else:
        monkeypatch.delenv("FLASK_RUN_HOST", raising=False)
        monkeypatch.delenv("FLASK_RUN_PORT", raising=False)

    runpy.run_path(str(RUN_PATH), run_name="__main__")

    options = application.run.call_args.kwargs
    assert options["use_reloader"] is False
    assert options["debug"] is debug
    assert options["threaded"] is True
    assert options["host"] == ("0.0.0.0" if custom_address else "127.0.0.1")
    assert options["port"] == (5050 if custom_address else 5000)
    application.run.assert_called_once()


def test_wsgi_import_does_not_start_development_server(monkeypatch):
    application = SimpleNamespace(config={"DEBUG": True}, run=Mock())
    monkeypatch.setattr("app.create_app", lambda: application)
    monkeypatch.setenv("FLASK_ENV", "production")

    module = runpy.run_path(str(RUN_PATH), run_name="test_wsgi_entrypoint")

    assert module["app"] is application
    application.run.assert_not_called()
