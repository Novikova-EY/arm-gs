# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки load_forecast."""
from app.api.services import load_forecast_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_load_forecast_stub_row()
    assert list(row.keys()) == [
        "Год",
        "Тип",
        "Субъект прогноза",
        "Потребление электрической энергии, млн кВт•ч",
        (
            "Потребление электрической энергии без учета ГАЭС в насосном режиме, "
            "млн кВт•ч"
        ),
        "external_code",
    ]
    assert row["Год"] == 0
    assert row["Тип"] == ""
    assert row["Субъект прогноза"] == ""
    assert row["Потребление электрической энергии, млн кВт•ч"] == 0
    assert row[svc.KEY_CONSUMPTION_WITHOUT_GAES] == 0
    assert row["external_code"] == ""


def test_load_load_forecast_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_load_forecast_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "load_forecast"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert payload["comment"] == (
        "Пока не используется, информация есть в gen_types_info.json"
    )
    assert payload["rows"] == [svc.build_load_forecast_stub_row()]
