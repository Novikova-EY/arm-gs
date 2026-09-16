# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки daymonth_info."""
from app.api.services import daymonth_info_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_daymonth_info_stub_row()
    assert list(row.keys()) == [
        "Год",
        "Зона для дня",
        "Месяц для дня",
        "День",
        "Дневное максимальное потребление мощности",
        "Дневное потребление мощности",
        "Дневная среднесуточная температура",
        "external_code",
    ]
    assert row["Год"] == 0
    assert row["Зона для дня"] == ""
    assert row["Месяц для дня"] == 0
    assert row["День"] == 0
    assert row["Дневное максимальное потребление мощности"] == 0
    assert row["Дневное потребление мощности"] == 0
    assert row["Дневная среднесуточная температура"] == 0
    assert row["external_code"] == ""


def test_load_daymonth_info_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_daymonth_info_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "daymonth_info"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "2027" in payload["comment"]
    assert "будет реализован" in payload["comment"]
    assert "Месяц: (1 - 12)" in payload["comment"]
    assert payload["rows"] == [svc.build_daymonth_info_stub_row()]
