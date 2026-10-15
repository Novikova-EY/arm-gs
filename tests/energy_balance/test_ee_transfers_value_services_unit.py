# -*- coding: utf-8 -*-
"""Проверка сохранения редактируемых значений перетоков ЭЭ."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.energy_balance.services import ee_transfers_value_services as value_services


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter_by(self, **conditions):
        return _Query(
            [
                row
                for row in self.rows
                if all(getattr(row, key, None) == value for key, value in conditions.items())
            ]
        )

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


@pytest.mark.parametrize("year_number", [2025, 2030])
def test_update_creates_transfer_value_for_fact_and_plan_periods(monkeypatch, year_number):
    existing_pair = SimpleNamespace(
        id_from_regional_energy_system=10,
        id_from_regional_district=None,
        id_to_regional_energy_system=20,
        id_to_foreign_border_country=None,
        id_to_regional_district=None,
        id_to_energy_unit=None,
        id_union_energy_system=7,
        year_number=2030,
        month_number=0,
        source_oes_name="ОЭС Северо-Запада",
        transfer_value=Decimal("1"),
    )

    class _Transfer:
        query = _Query([existing_pair])

        def __init__(self, **fields):
            self.__dict__.update(fields)

    added = []
    monkeypatch.setattr(value_services, "RegionalEnergySystemTransfer", _Transfer)
    monkeypatch.setattr(
        value_services,
        "UnionEnergySystem",
        SimpleNamespace(query=_Query([SimpleNamespace(id=7)])),
    )
    monkeypatch.setattr(value_services, "get_current_db_version_id", lambda: 4)
    monkeypatch.setattr(value_services, "filter_by_db_version", lambda query, model: query)
    monkeypatch.setattr(value_services, "filter_by_explicit_db_version", lambda query, model, version: query)
    monkeypatch.setattr(value_services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(value_services, "clear_energy_balance_cache", lambda: None)
    monkeypatch.setattr(value_services.db.session, "add", added.append, raising=False)
    monkeypatch.setattr(
        value_services,
        "_get_res_territory_maps",
        lambda: {"res_ues_map": {10: 7}, "rd_res_map": {}},
    )
    monkeypatch.setattr(value_services, "get_union_energy_systems_map", lambda: {7: "ОЭС Северо-Запада"})
    monkeypatch.setattr(value_services, "get_union_energy_system_display_order_map", lambda: {7: 1})

    result = value_services.update_ee_transfer_value(
        ues_id=7,
        source_res_id=10,
        source_rd_id="",
        target_res_id=20,
        target_country_id="",
        target_rd_id="",
        target_energy_unit_id="",
        year=year_number,
        month=4,
        raw_value="2,5",
    )

    assert result == {"year": year_number, "month": 4, "value": Decimal("2.5")}
    assert len(added) == 1
    assert added[0].id_union_energy_system == 7
    assert added[0].id_from_regional_energy_system == 10
    assert added[0].id_to_regional_energy_system == 20
    assert added[0].source_oes_name == "ОЭС Северо-Запада"
    assert added[0].database_version_id == 4
