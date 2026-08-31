# -*- coding: utf-8 -*-
"""Юнит-тесты API версий БД и JSON-наборов."""
from types import SimpleNamespace

import pytest

from app.api.services import database_versions_api_services as versions_svc
from app.api.services import exchange_api_services as datasets_svc


def test_list_exchange_datasets_known_names():
    names = datasets_svc.list_exchange_datasets()["datasets"]
    assert "general_info" in names
    assert "gentypes_info" in names
    assert "generation_objects" in names
    assert "generation_machines" in names
    assert "equipment_group_params" not in names


def test_load_all_exchange_datasets_by_version_id(monkeypatch):
    calls = []

    def fake_general(**kwargs):
        calls.append(("general_info", kwargs))
        return {"dataset": "general_info", "database_version": 7, "rows": []}

    def fake_gentypes(**kwargs):
        calls.append(("gentypes_info", kwargs))
        return {"dataset": "gentypes_info", "database_version": 7, "rows": [0]}

    def fake_objects(**kwargs):
        calls.append(("generation_objects", kwargs))
        return {"dataset": "generation_objects", "database_version": 7, "rows": [1]}

    def fake_machines(**kwargs):
        calls.append(("generation_machines", kwargs))
        return {"dataset": "generation_machines", "database_version": 7, "rows": [2]}

    monkeypatch.setitem(datasets_svc.DATASET_LOADERS, "general_info", fake_general)
    monkeypatch.setitem(datasets_svc.DATASET_LOADERS, "gentypes_info", fake_gentypes)
    monkeypatch.setitem(
        datasets_svc.DATASET_LOADERS, "generation_objects", fake_objects
    )
    monkeypatch.setitem(
        datasets_svc.DATASET_LOADERS, "generation_machines", fake_machines
    )
    monkeypatch.setattr(
        "app.api.services.database_versions_api_services.ensure_database_version_exists",
        lambda version_id: int(version_id),
    )

    payload = datasets_svc.load_all_exchange_datasets(
        version_id=7, year=2032, start_year=None, end_year=None
    )
    assert payload["database_version"] == 7
    assert payload["version"] == 7
    assert len(payload["datasets"]) == 4
    assert payload["datasets"][0]["dataset"] == "general_info"
    assert all(
        c[1]
        == {
            "version_id": 7,
            "year": 2032,
            "start_year": None,
            "end_year": None,
        }
        for c in calls
    )


def test_list_database_versions_shape(monkeypatch):
    rows = [
        SimpleNamespace(
            id=7, version_number="ГС-2026", description="desc", is_active=True
        ),
        SimpleNamespace(
            id=3, version_number="ГС-2024", description=None, is_active=False
        ),
    ]

    class _Q:
        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return rows

    class _Session:
        def query(self, model):
            return _Q()

    monkeypatch.setattr(versions_svc.db, "session", _Session())
    monkeypatch.setattr(
        "app.api.services.general_info_exchange_services.planning_meta_for_version",
        lambda version_id, version_number: {
            "planning_scheme": "gs",
            "current_year": 2024,
            "period_start": 2024,
            "period_end": 2042,
        },
    )
    payload = versions_svc.list_database_versions()
    assert payload["rows"][0]["database_version"] == 7
    assert payload["rows"][0]["version_number"] == "ГС-2026"
    assert payload["rows"][0]["planning_scheme"] == "gs"
    assert payload["rows"][0]["period_end"] == 2042
    assert "is_active" not in payload["rows"][0]
    assert payload["rows"][1]["description"] == ""
    assert payload["rows"][1]["database_version"] == 3


def test_get_database_version_ok_and_missing(monkeypatch):
    row = SimpleNamespace(
        id=7, version_number="ГС-2026", description="x", is_active=True
    )

    class _Session:
        def get(self, model, pk):
            return row if int(pk) == 7 else None

    monkeypatch.setattr(versions_svc.db, "session", _Session())
    monkeypatch.setattr(
        "app.api.services.general_info_exchange_services.planning_meta_for_version",
        lambda version_id, version_number: {
            "planning_scheme": "gs",
            "current_year": 2024,
            "period_start": 2024,
            "period_end": 2042,
        },
    )
    assert versions_svc.get_database_version(7)["database_version"] == 7
    with pytest.raises(versions_svc.UnknownDatabaseVersionError):
        versions_svc.get_database_version(99)
