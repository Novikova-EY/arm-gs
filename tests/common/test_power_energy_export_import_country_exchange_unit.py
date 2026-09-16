# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки power_energy_export_import_country."""
from app.api.services import power_energy_export_import_country_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_power_energy_export_import_country_stub_row()
    assert list(row.keys()) == [
        "Страна/ЕЭС",
        "Год",
        "Энергия, млн кВт•ч",
        "Мощность, МВт",
        "Направление",
        "external_code",
    ]
    assert row["Страна/ЕЭС"] == ""
    assert row["Год"] == 0
    assert row["Энергия, млн кВт•ч"] == 0
    assert row["Мощность, МВт"] == 0
    assert row["Направление"] == ""
    assert row["external_code"] == ""


def test_load_power_energy_export_import_country_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_power_energy_export_import_country_dataset(
        version_id=46, year=2025
    )
    assert payload["dataset"] == "power_energy_export_import_country"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "не реализовано" in payload["comment"]
    assert "2026" in payload["comment"]
    assert payload["rows"] == [svc.build_power_energy_export_import_country_stub_row()]
