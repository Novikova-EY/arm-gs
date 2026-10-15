# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки hour_info."""
from app.api.services import hour_info_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_hour_info_stub_row()
    assert list(row.keys()) == [
        "Год",
        "Зона для часа",
        "Месяц для часа",
        "День для часа",
        "Час",
        "Часовое потребление мощности",
        "external_code",
    ]
    assert row["Год"] == 0
    assert row["Зона для часа"] == ""
    assert row["Месяц для часа"] == 0
    assert row["День для часа"] == 0
    assert row["Час"] == 0
    assert row["Часовое потребление мощности"] == 0
    assert row["external_code"] == ""


def test_load_hour_info_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_hour_info_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "hour_info"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert payload["comment"] == svc.HOUR_INFO_COMMENT
    assert "2027" in payload["comment"]
    assert "Все поля передаются нулями." in payload["comment"]
    assert "Месяц: (1 - 12)." in payload["comment"]
    assert payload["rows"] == [svc.build_hour_info_stub_row()]
