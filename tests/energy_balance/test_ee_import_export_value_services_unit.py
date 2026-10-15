# -*- coding: utf-8 -*-
"""Юнит-тесты сохранения плановых значений по ОЭС и стране."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.energy_balance.services import ee_import_export_value_services as value_services


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class _ValuesModel:
    query = None

    def __init__(self, **fields):
        self.__dict__.update(fields)


def test_update_persists_historical_value_in_oes_country_table(monkeypatch):
    existing = SimpleNamespace(
        id_union_energy_system=7,
        id_foreign_border_country=11,
        year_number=2024,
        transfer_value=Decimal("4"),
    )
    table_rows = _Query([existing])
    _ValuesModel.query = table_rows
    monkeypatch.setattr(value_services, "EeImportExportOesValue", _ValuesModel)
    monkeypatch.setattr(value_services, "get_current_db_version_id", lambda: 3)
    monkeypatch.setattr(value_services, "filter_by_db_version", lambda query, model: query)
    monkeypatch.setattr(value_services, "filter_by_explicit_db_version", lambda query, model, version: query)
    monkeypatch.setattr(value_services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(value_services, "clear_energy_balance_cache", lambda: None)
    monkeypatch.setattr(
        value_services,
        "UnionEnergySystem",
        SimpleNamespace(query=_Query([SimpleNamespace(id=7, name="ОЭС")])),
    )
    monkeypatch.setattr(
        value_services,
        "ForeignBorderCountry",
        SimpleNamespace(query=_Query([SimpleNamespace(id=11, name="Беларусь")])),
    )

    result = value_services.update_ee_import_export_value(
        ues_id=7,
        country_id=11,
        year=2024,
        raw_value="20",
    )

    assert result == {"year": 2024, "value": Decimal("20")}
    assert existing.transfer_value == Decimal("20")
    assert existing.id_union_energy_system == 7
    assert existing.id_foreign_border_country == 11

    cleared = value_services.update_ee_import_export_value(
        ues_id=7,
        country_id=11,
        year=2024,
        raw_value="",
    )
    assert cleared == {"year": 2024, "value": None}
    assert existing.transfer_value is None
