# -*- coding: utf-8 -*-
"""Юнит-тесты general_info."""
from types import SimpleNamespace

from app.api.services import general_info_exchange_services as svc


def test_build_general_info_row_sipr(monkeypatch):
    monkeypatch.setattr(
        svc,
        "get_current_year_info",
        lambda version_id: {"current_year": 2025, "sipr_start": 2026, "sipr_end": 2031},
    )
    monkeypatch.setattr(
        svc.db,
        "session",
        SimpleNamespace(get=lambda model, pk: SimpleNamespace(version_number="СиПР 2026-2031")),
    )
    row = svc.build_general_info_row(37)
    assert row == {
        "Текущий год": 2025,
        "Начало периода": 2026,
        "Конец периода": 2031,
    }


def test_build_general_info_row_gs(monkeypatch):
    monkeypatch.setattr(
        svc,
        "get_current_year_info",
        lambda version_id: {"current_year": 2025, "sipr_start": 2026, "sipr_end": 2031},
    )
    monkeypatch.setattr(
        svc.db,
        "session",
        SimpleNamespace(get=lambda model, pk: SimpleNamespace(version_number="ГС 2023-2042")),
    )
    monkeypatch.setattr(svc.Config, "END_YEAR_GENERAL_SCHEME", 2042, raising=False)
    row = svc.build_general_info_row(46)
    assert row == {
        "Текущий год": 2025,
        "Начало периода": 2026,
        "Конец периода": 2042,
    }


def test_load_general_info_envelope(monkeypatch):
    monkeypatch.setattr(svc, "resolve_database_version", lambda version_id: (46, "ГС-2026"))
    monkeypatch.setattr(
        svc,
        "build_general_info_row",
        lambda version_id: {
            "Текущий год": 2025,
            "Начало периода": 2026,
            "Конец периода": 2042,
        },
    )
    payload = svc.load_general_info_dataset(version_id=46)
    assert payload["dataset"] == "general_info"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["Конец периода"] == 2042


def test_planning_meta_scheme(monkeypatch):
    monkeypatch.setattr(
        svc,
        "build_general_info_row",
        lambda version_id: {
            "Текущий год": 2025,
            "Начало периода": 2026,
            "Конец периода": 2031,
        },
    )
    meta = svc.planning_meta_for_version(10, "СиПР 2026-2031")
    assert meta["planning_scheme"] == "sipr"
    assert meta["period_start"] == 2026
    assert meta["period_end"] == 2031
    meta_gs = svc.planning_meta_for_version(11, "ГС 2023-2042")
    assert meta_gs["planning_scheme"] == "gs"
