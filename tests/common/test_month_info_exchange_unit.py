# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки month_info."""
from app.api.services import month_info_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_month_info_stub_row()
    assert list(row.keys()) == [
        "Год",
        "Зона для месяца",
        "Месяц",
        "Месячное максимальное потребление мощности",
        "Месячное потребление мощности",
        "Месячная среднесуточная температура",
        "external_code",
    ]
    assert row["Год"] == 0
    assert row["Зона для месяца"] == ""
    assert row["Месяц"] == 0
    assert row["Месячное максимальное потребление мощности"] == 0
    assert row["Месячное потребление мощности"] == 0
    assert row["Месячная среднесуточная температура"] == 0
    assert row["external_code"] == ""


def test_load_month_info_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_month_info_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "month_info"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "2027" in payload["comment"]
    assert "будет разработано" in payload["comment"].casefold()
    assert "Месяц: (1 - 12)" in payload["comment"]
    assert payload["rows"] == [svc.build_month_info_stub_row()]
