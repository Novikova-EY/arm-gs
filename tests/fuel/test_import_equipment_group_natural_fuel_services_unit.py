# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from decimal import Decimal

from app.fuel.services.fuel_imports import import_equipment_group_natural_fuel_services as service


class _NotSetType:
    pass


_NotSet = _NotSetType()


class _FakeExcelFile:
    def __init__(self, df: pd.DataFrame):
        self.sheet_names = ["Лист1"]
        self._df = df

    def parse(self, sheet_name, header=0, **kwargs):
        assert sheet_name == "Лист1"
        return self._df.copy()


class _DummySession:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, obj):
        self.added.append(obj)
        if hasattr(obj.__class__, "query") and getattr(obj.__class__, "query", None) is not None:
            obj.__class__.query.storage.append(obj)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        return None


class _YearQuery:
    def __init__(self, valid_pairs, number=None, version_id=_NotSet):
        self.valid_pairs = set(valid_pairs)
        self.number = number
        self.version_id = version_id

    def filter_by(self, **kwargs):
        number = kwargs.get("number", self.number)
        version_id = kwargs.get("database_version_id", self.version_id)
        return _YearQuery(self.valid_pairs, number=number, version_id=version_id)

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        if self.number is None or self.version_id is _NotSet:
            return None
        return object() if (self.number, self.version_id) in self.valid_pairs else None


class _NaturalFuelQuery:
    def __init__(self, storage, criteria=None):
        self.storage = storage
        self.criteria = criteria or {}

    def filter_by(self, **kwargs):
        next_criteria = dict(self.criteria)
        next_criteria.update(kwargs)
        return _NaturalFuelQuery(self.storage, next_criteria)

    def first(self):
        for item in self.storage:
            if all(getattr(item, key, None) == value for key, value in self.criteria.items()):
                return item
        return None


class _FakeNaturalFuel:
    query = None

    def __init__(self, equipment_group_id, year_number, database_version_id):
        self.equipment_group_id = equipment_group_id
        self.year_number = year_number
        self.database_version_id = database_version_id
        self.name = None
        self.gaz = None


def test_import_natural_fuel_uses_years_from_excel_rows(monkeypatch):
    df = pd.DataFrame(
        [
            {"NUMB1120": 1001, "YEAR": 2024, "gaz": "10.5"},
            {"NUMB1120": 1001, "YEAR": 2025, "gaz": "20.5"},
            {"NUMB1120": 1001, "gaz": "30.5"},
        ]
    )
    storage = [
        SimpleNamespace(
            equipment_group_id=501,
            year_number=2024,
            database_version_id=77,
            gaz=Decimal("1"),
            name=None,
        )
    ]
    session = _DummySession()
    _FakeNaturalFuel.query = _NaturalFuelQuery(storage)

    monkeypatch.setattr(service.pd, "ExcelFile", lambda _: _FakeExcelFile(df))
    monkeypatch.setattr(service, "_resolve_equipment_groups_from_row", lambda row: [(501, 77)])
    monkeypatch.setattr(service, "EquipmentGroupNaturalFuel", _FakeNaturalFuel)
    monkeypatch.setattr(
        service,
        "Year",
        SimpleNamespace(query=_YearQuery({(2024, 77), (2025, 77)}), database_version_id=None),
    )
    monkeypatch.setattr(service.db, "session", session)
    monkeypatch.setattr(service, "log_to_db", lambda *args, **kwargs: None)

    result = service.import_equipment_group_natural_fuel_from_excel(
        SimpleNamespace(filename="natural.xlsx"),
        user="tester",
        year=2099,
    )

    assert result["created"] == 1
    assert result["updated"] == 2
    assert result["skipped"] == 0
    assert result["skipped_no_year"] == 1
    assert session.committed is True
    assert len(storage) == 2
    assert len(session.added) == 1
    assert storage[0].gaz == Decimal("10.5")
    created = session.added[0]
    assert created.equipment_group_id == 501
    assert created.year_number == 2025
    assert created.database_version_id == 77
    assert created.gaz == Decimal("20.5")
