# -*- coding: utf-8 -*-
"""Юнит-тесты general_info."""
from types import SimpleNamespace

import pytest

from app.api.services import general_info_exchange_services as svc

STUB_FIELDS = {
    "Дата утверждения Постановления Правительства РФ": "",
    "Номер Постановления Правительства РФ": "",
    "Наименование Постановления Правительства РФ": "",
    "external_code": "",
}


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
        **STUB_FIELDS,
    }


@pytest.mark.parametrize(
    ("current_year", "expected_end"),
    [(2025, 2042), (2027, 2042), (2029, 2042), (2030, 2048), (2033, 2048),
     (2036, 2054), (2023, 0), (0, 0)],
)
def test_build_general_info_row_gs(monkeypatch, current_year, expected_end):
    monkeypatch.setattr(
        svc.db,
        "session",
        SimpleNamespace(get=lambda model, pk: SimpleNamespace(version_number="ГС 2023-2042")),
    )
    monkeypatch.setattr(
        svc,
        "get_current_year_info",
        lambda version_id: {
            "current_year": current_year,
            "sipr_start": current_year + 1,
            "sipr_end": current_year + 6,
        },
    )
    row = svc.build_general_info_row(46)
    assert row == {
        "Текущий год": current_year,
        "Начало периода": current_year + 1,
        "Конец периода": expected_end,
        **STUB_FIELDS,
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
            **STUB_FIELDS,
        },
    )
    payload = svc.load_general_info_dataset(version_id=46)
    assert payload["dataset"] == "general_info"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["Конец периода"] == 2042
    assert payload["rows"][0]["external_code"] == ""
    assert "пока пустые" in payload["comment"]
    assert "в АРМ нет" in payload["comment"]


def test_planning_meta_scheme(monkeypatch):
    monkeypatch.setattr(
        svc,
        "build_general_info_row",
        lambda version_id: {
            "Текущий год": 2025,
            "Начало периода": 2026,
            "Конец периода": 2031,
            **STUB_FIELDS,
        },
    )
    meta = svc.planning_meta_for_version(10, "СиПР 2026-2031")
    assert meta["planning_scheme"] == "sipr"
    assert meta["period_start"] == 2026
    assert meta["period_end"] == 2031
    meta_gs = svc.planning_meta_for_version(11, "ГС 2023-2042")
    assert meta_gs["planning_scheme"] == "gs"
