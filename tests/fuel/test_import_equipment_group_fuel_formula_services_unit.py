# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
from sqlalchemy.exc import IntegrityError

from app.fuel.services.fuel_imports import import_equipment_group_fuel_formula_services as service


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
    def __init__(self, flush_error=None):
        self.added = []
        self.committed = False
        self.flush_error = flush_error

    def add(self, obj):
        self.added.append(obj)
        query = getattr(obj.__class__, "query", None)
        if query is not None and hasattr(query, "storage"):
            query.storage.append(obj)

    def flush(self):
        if self.flush_error is not None:
            raise self.flush_error
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        return None

    @contextmanager
    def begin_nested(self):
        yield self


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


class _FormulaQuery:
    def __init__(self, storage, criteria=None):
        self.storage = storage
        self.criteria = criteria or {}

    def filter_by(self, **kwargs):
        next_criteria = dict(self.criteria)
        next_criteria.update(kwargs)
        return _FormulaQuery(self.storage, next_criteria)

    def first(self):
        for item in self.storage:
            if all(getattr(item, key, None) == value for key, value in self.criteria.items()):
                return item
        return None


class _FakeFormula:
    query = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _patch_import_deps(
    monkeypatch, *, groups, storage, years, df, session=None, current_version=20
):
    session = session or _DummySession()
    _FakeFormula.query = _FormulaQuery(storage)
    monkeypatch.setattr(service.pd, "ExcelFile", lambda _: _FakeExcelFile(df))
    monkeypatch.setattr(
        service, "_resolve_equipment_groups_by_numb", lambda numb_str: list(groups)
    )
    monkeypatch.setattr(service, "EquipmentGroupFuelFormula", _FakeFormula)
    monkeypatch.setattr(
        service,
        "Year",
        SimpleNamespace(query=_YearQuery(years), database_version_id=None),
    )
    monkeypatch.setattr(service.db, "session", session)
    monkeypatch.setattr(service, "log_to_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: current_version)
    monkeypatch.setattr(service, "set_db_version_on_create", lambda row: None)
    return session


def test_effective_version_uses_current_when_group_version_is_none(monkeypatch):
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: 20)
    assert service._effective_formula_db_version_id(None) == 20
    assert service._effective_formula_db_version_id(20) == 20
    assert service._effective_formula_db_version_id(7) == 7


def test_import_updates_existing_formula_when_group_version_is_none(monkeypatch):
    """uq включает version; группа без version, формула уже с текущей version=20 — UPDATE, не INSERT."""
    df = pd.DataFrame(
        [
            {
                "NAME": "Архангельская ТЭЦ",
                "year": 2021,
                "formtxt": "maztop=0,38;gaz_prir",
                "numb1120": 1,
                "numb1": 1.0,
                "v": 0,
            }
        ]
    )
    existing = SimpleNamespace(
        equipment_group_id=17068,
        year_number=2021,
        variant_number=0,
        database_version_id=20,
        name="старое",
        formtxt="old",
        numb1120=1,
        numb1=Decimal("2.0"),
    )
    storage = [existing]
    groups = [SimpleNamespace(id=17068, numb=1, database_version_id=None)]

    session = _patch_import_deps(
        monkeypatch,
        groups=groups,
        storage=storage,
        years={(2021, 20)},
        df=df,
        current_version=20,
    )

    result = service.import_equipment_group_fuel_formula_from_excel(
        SimpleNamespace(filename="formulas.xlsx"),
        user="tester",
    )

    assert result["created"] == 0
    assert result["updated"] == 1
    assert session.committed is True
    assert session.added == []
    assert existing.name == "Архангельская ТЭЦ"
    assert existing.formtxt == "maztop=0,38;gaz_prir"
    assert existing.numb1 == Decimal("1.0")


def test_get_or_create_recovers_from_unique_violation(monkeypatch):
    existing = SimpleNamespace(
        equipment_group_id=17068,
        year_number=2021,
        variant_number=0,
        database_version_id=20,
        name="есть",
        formtxt="x",
        numb1120=1,
        numb1=None,
    )

    class _LookupMissThenHit:
        def __init__(self):
            self.calls = 0

        def filter_by(self, **kwargs):
            return self

        def first(self):
            self.calls += 1
            if self.calls == 1:
                return None
            return existing

    _FakeFormula.query = _LookupMissThenHit()
    session = _DummySession(
        flush_error=IntegrityError("INSERT", {}, Exception("UniqueViolation"))
    )
    monkeypatch.setattr(service, "EquipmentGroupFuelFormula", _FakeFormula)
    monkeypatch.setattr(service.db, "session", session)
    monkeypatch.setattr(service, "set_db_version_on_create", lambda row: None)

    row, created = service._get_or_create_equipment_group_fuel_formula_row(
        equipment_group_id=17068,
        year_number=2021,
        variant_number=0,
        database_version_id=20,
        name="Архангельская ТЭЦ",
        numb1120=1,
        numb1=Decimal("1.0"),
        formtxt="maztop=0,38;gaz_prir",
    )

    assert created is False
    assert row is existing
    assert session.added  # INSERT attempted, then UniqueViolation → existing row
