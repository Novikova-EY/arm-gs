# -*- coding: utf-8 -*-
"""Проверка синхронизации сохранённых годовых агрегатов по ОЭС."""

from decimal import Decimal
from types import SimpleNamespace

from app.energy_balance.services import ee_import_export_oes_value_services as oes_services


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


def test_recalculate_sums_res_values_by_oes_and_removes_stale_aggregate(monkeypatch):
    transfers = [
        SimpleNamespace(id_union_energy_system=7, id_from_regional_energy_system=10,
                       id_from_regional_district=None, id_to_foreign_border_country=11,
                       transfer_value=Decimal("4")),
        SimpleNamespace(id_union_energy_system=7, id_from_regional_energy_system=20,
                       id_from_regional_district=None, id_to_foreign_border_country=11,
                       transfer_value=Decimal("-1.5")),
        SimpleNamespace(id_union_energy_system=None, id_from_regional_energy_system=30,
                       id_from_regional_district=None, id_to_foreign_border_country=11,
                       transfer_value=Decimal("2")),
    ]
    current = SimpleNamespace(
        id_union_energy_system=7,
        id_foreign_border_country=11,
        transfer_value=Decimal("0"),
    )
    stale = SimpleNamespace(id_union_energy_system=8, id_foreign_border_country=12)
    transfer_model = type(
        "TransferModel",
        (),
        {
            "query": _Query(transfers),
            "year_number": _Column(),
            "month_number": _Column(),
            "id_to_foreign_border_country": _Column(),
        },
    )
    oes_model = type(
        "OesValueModel",
        (),
        {"query": _Query([current, stale])},
    )
    added, deleted = [], []
    monkeypatch.setattr(oes_services, "RegionalEnergySystemTransfer", transfer_model)
    monkeypatch.setattr(oes_services, "EeImportExportOesValue", oes_model)
    monkeypatch.setattr(oes_services, "filter_by_explicit_db_version", lambda query, model, version: query)
    monkeypatch.setattr(
        oes_services,
        "_get_res_territory_maps",
        lambda: {"res_ues_map": {30: 7}, "rd_res_map": {}},
    )
    monkeypatch.setattr(oes_services, "_infer_transfer_ues_id", lambda rec, **kwargs: rec.id_union_energy_system or kwargs["res_ues_map"].get(rec.id_from_regional_energy_system))
    monkeypatch.setattr(oes_services.db.session, "add", added.append, raising=False)
    monkeypatch.setattr(oes_services.db.session, "delete", deleted.append, raising=False)

    oes_services.recalculate_ee_import_export_oes_values(year_number=2030, version_id=4)

    assert current.transfer_value == Decimal("4.5")
    assert len(added) == 0
    assert deleted == [stale]
