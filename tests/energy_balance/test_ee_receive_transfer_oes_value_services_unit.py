# -*- coding: utf-8 -*-
"""Проверка пересчета агрегатов перетоков между ОЭС."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.energy_balance.services import ee_receive_transfer_oes_value_services as value_services


class _Column:
    def __eq__(self, other):
        return (self, "eq", other)

    def isnot(self, other):
        return (self, "isnot", other)


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        return self

    def filter_by(self, **kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


def test_recalculate_sums_res_transfers_by_oes_pair_and_deletes_stale(monkeypatch):
    transfers = [
        SimpleNamespace(id_union_energy_system=7, id_from_regional_energy_system=10,
                       id_from_regional_district=None, id_to_regional_energy_system=20,
                       transfer_value=Decimal("4")),
        SimpleNamespace(id_union_energy_system=7, id_from_regional_energy_system=11,
                       id_from_regional_district=None, id_to_regional_energy_system=21,
                       transfer_value=Decimal("-1.5")),
        SimpleNamespace(id_union_energy_system=7, id_from_regional_energy_system=30,
                       id_from_regional_district=None, id_to_regional_energy_system=22,
                       transfer_value=Decimal("2")),
        SimpleNamespace(id_union_energy_system=7, id_from_regional_energy_system=12,
                       id_from_regional_district=None, id_to_regional_energy_system=23,
                       transfer_value=Decimal("5")),
    ]
    current = SimpleNamespace(
        id_source_union_energy_system=7,
        id_target_union_energy_system=9,
        transfer_value=Decimal("0"),
    )
    stale = SimpleNamespace(id_source_union_energy_system=8, id_target_union_energy_system=10)
    transfer_model = type(
        "TransferModel",
        (),
        {
            "query": _Query(transfers),
            "year_number": _Column(),
            "month_number": _Column(),
            "id_to_regional_energy_system": _Column(),
        },
    )
    value_model = type(
        "ValueModel",
        (),
        {
            "query": _Query([current, stale]),
            "__init__": lambda self, **fields: self.__dict__.update(fields),
        },
    )
    added, deleted = [], []
    monkeypatch.setattr(value_services, "RegionalEnergySystemTransfer", transfer_model)
    monkeypatch.setattr(value_services, "EeReceiveTransferOesValue", value_model)
    monkeypatch.setattr(value_services, "filter_by_explicit_db_version", lambda query, model, version: query)
    monkeypatch.setattr(
        value_services,
        "_get_res_territory_maps",
        lambda: {"res_ues_map": {20: 9, 21: 9, 22: 10, 23: 7, 30: 7}, "rd_res_map": {}},
    )
    monkeypatch.setattr(
        value_services,
        "_infer_transfer_ues_id",
        lambda rec, **kwargs: rec.id_union_energy_system or kwargs["res_ues_map"].get(rec.id_from_regional_energy_system),
    )
    monkeypatch.setattr(value_services, "get_union_energy_systems_map", lambda: {})
    monkeypatch.setattr(value_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(value_services.db.session, "add", added.append, raising=False)
    monkeypatch.setattr(value_services.db.session, "delete", deleted.append, raising=False)

    value_services.recalculate_ee_receive_transfer_oes_values(year_number=2030, version_id=4)

    assert current.transfer_value == Decimal("2.5")
    assert len(added) == 1
    assert added[0].id_source_union_energy_system == 7
    assert added[0].id_target_union_energy_system == 10
    assert added[0].transfer_value == Decimal("2")
    assert deleted == [stale]


def test_recalculate_maps_subject_and_energy_area_destinations_to_oes(monkeypatch):
    transfers = [
        SimpleNamespace(
            id_union_energy_system=7,
            id_from_regional_energy_system=10,
            id_from_regional_district=None,
            id_to_regional_energy_system=None,
            id_to_regional_district=50,
            id_to_energy_unit=None,
            transfer_value=Decimal("2"),
        ),
        SimpleNamespace(
            id_union_energy_system=7,
            id_from_regional_energy_system=10,
            id_from_regional_district=None,
            id_to_regional_energy_system=None,
            id_to_regional_district=None,
            id_to_energy_unit=60,
            transfer_value=Decimal("3"),
        ),
    ]
    transfer_model = type(
        "TransferModel",
        (),
        {
            "query": _Query(transfers),
            "year_number": _Column(),
            "month_number": _Column(),
        },
    )
    value_model = type(
        "ValueModel",
        (),
        {
            "query": _Query([]),
            "__init__": lambda self, **fields: self.__dict__.update(fields),
        },
    )
    added = []
    monkeypatch.setattr(value_services, "RegionalEnergySystemTransfer", transfer_model)
    monkeypatch.setattr(value_services, "EeReceiveTransferOesValue", value_model)
    monkeypatch.setattr(value_services, "filter_by_explicit_db_version", lambda query, model, version: query)
    monkeypatch.setattr(
        value_services,
        "_get_res_territory_maps",
        lambda: {
            "res_ues_map": {20: 9},
            "rd_res_map": {50: {20}},
            "eu_res_map": {60: 20},
        },
    )
    monkeypatch.setattr(value_services, "get_union_energy_systems_map", lambda: {9: "ОЭС получателя"})
    monkeypatch.setattr(value_services, "get_union_energy_system_display_order_map", lambda: {})
    monkeypatch.setattr(value_services.db.session, "add", added.append, raising=False)

    value_services.recalculate_ee_receive_transfer_oes_values(year_number=2030, version_id=4)

    assert len(added) == 1
    assert added[0].id_source_union_energy_system == 7
    assert added[0].id_target_union_energy_system == 9
    assert added[0].transfer_value == Decimal("5")


def test_update_stores_historical_oes_pair_value(monkeypatch):
    class _FindQuery(_Query):
        def filter_by(self, **kwargs):
            return self

    class _StoredValue:
        query = _FindQuery([])

        def __init__(self, **fields):
            self.__dict__.update(fields)

    added = []
    monkeypatch.setattr(value_services, "EeReceiveTransferOesValue", _StoredValue)
    monkeypatch.setattr(value_services, "get_current_db_version_id", lambda: 4)
    monkeypatch.setattr(value_services, "filter_by_db_version", lambda query, model: query)
    monkeypatch.setattr(value_services, "filter_by_explicit_db_version", lambda query, model, version: query)
    monkeypatch.setattr(value_services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(value_services, "clear_energy_balance_cache", lambda: None)
    monkeypatch.setattr(value_services.db.session, "add", added.append, raising=False)
    monkeypatch.setattr(
        value_services,
        "UnionEnergySystem",
        SimpleNamespace(query=_FindQuery([SimpleNamespace(id=7, name="ОЭС")])),
    )

    result = value_services.update_ee_receive_transfer_oes_value(
        source_ues_id=7,
        target_ues_id=9,
        year=2024,
        raw_value="3,5",
    )

    assert result == {"year": 2024, "value": Decimal("3.5")}
    assert len(added) == 1
    assert added[0].id_source_union_energy_system == 7
    assert added[0].id_target_union_energy_system == 9
    assert added[0].database_version_id == 4


def test_internal_oes_value_cannot_be_saved(monkeypatch):
    with pytest.raises(ValueError, match="внутри одной ОЭС"):
        value_services.update_ee_receive_transfer_oes_value(
            source_ues_id=7,
            target_ues_id=7,
            year=2024,
            raw_value="1",
        )
