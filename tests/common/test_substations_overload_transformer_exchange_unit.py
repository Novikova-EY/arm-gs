# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки substations_overload_transformer."""
from app.api.services import substations_overload_transformer_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_substations_overload_transformer_stub_row()
    assert list(row.keys()) == [
        "Название подстанции",
        "Название трансформатора",
        "Температура, °С",
        "Значение перегрузки, о.е.",
        "external_code",
    ]
    assert row["Название подстанции"] == ""
    assert row["Название трансформатора"] == ""
    assert row["Температура, °С"] == 0
    assert row["Значение перегрузки, о.е."] == 0
    assert row["external_code"] == ""


def test_load_substations_overload_transformer_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_substations_overload_transformer_dataset(
        version_id=46, year=2025
    )
    assert payload["dataset"] == "substations_overload_transformer"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "нет в АРМ" in payload["comment"]
    assert "заполняются вручную" in payload["comment"]
    assert payload["rows"] == [svc.build_substations_overload_transformer_stub_row()]
