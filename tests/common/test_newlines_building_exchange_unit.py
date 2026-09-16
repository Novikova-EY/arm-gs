# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки newlines_building."""
from app.api.services import newlines_building_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_newlines_building_stub_row()
    assert list(row.keys()) == [
        "Наименование титула",
        "Субъект документа",
        "Км по титулу, км",
        "МВА по титулу, МВА",
        "Год ввода по титулу",
        "external_code",
    ]
    assert row["Наименование титула"] == ""
    assert row["Субъект документа"] == ""
    assert row["Км по титулу, км"] == 0
    assert row["МВА по титулу, МВА"] == 0
    assert row["Год ввода по титулу"] == 0
    assert row["external_code"] == ""


def test_load_newlines_building_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_newlines_building_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "newlines_building"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "нет в АРМ" in payload["comment"]
    assert "заполняются вручную" in payload["comment"]
    assert payload["rows"] == [svc.build_newlines_building_stub_row()]
