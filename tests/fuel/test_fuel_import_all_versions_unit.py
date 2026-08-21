# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.fuel.services.fuel_imports.fuel_import_all_versions import (
    lookup_imported_row,
    normalize_import_numb,
    resolve_equipment_group_import_targets,
)


class _CastExpr:
    def __eq__(self, other):
        return SimpleNamespace(kind="numb", value=str(other))


class _Col:
    def in_(self, values):
        return SimpleNamespace(kind="code_in", values=set(values))

    def is_(self, value):
        return SimpleNamespace(kind="is_null", value=value)


class _Query:
    def __init__(self, rows, predicate=None):
        self.rows = list(rows)
        self.predicate = predicate or (lambda _row: True)

    def filter(self, *args, **kwargs):
        expr = args[0] if args else None
        prev = self.predicate
        kind = getattr(expr, "kind", None)

        def pred(row):
            if not prev(row):
                return False
            if kind == "numb":
                return str(getattr(row, "numb", "") or "") == str(expr.value)
            if kind == "code_in":
                return (getattr(row, "external_code", None) or "") in expr.values
            if kind == "is_null":
                return getattr(row, "equipment_group_id", None) is None
            return True

        return _Query(self.rows, pred)

    def filter_by(self, **kwargs):
        prev = self.predicate

        def pred(row):
            if not prev(row):
                return False
            return all(getattr(row, key, None) == value for key, value in kwargs.items())

        return _Query(self.rows, pred)

    def all(self):
        return [row for row in self.rows if self.predicate(row)]

    def first(self):
        rows = self.all()
        return rows[0] if rows else None


class _Model:
    equipment_group_id = _Col()

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    query = None


def test_normalize_import_numb():
    assert normalize_import_numb(1001) == "1001"
    assert normalize_import_numb(1001.0) == "1001"
    assert normalize_import_numb(" 1001 ") == "1001"
    assert normalize_import_numb(None) is None
    assert normalize_import_numb("") is None


def test_resolve_targets_expands_external_code_and_fills_missing_versions(monkeypatch):
    groups = [
        SimpleNamespace(id=1, numb=1001, database_version_id=10, external_code="abc"),
        SimpleNamespace(id=2, numb=None, database_version_id=20, external_code="abc"),
        SimpleNamespace(id=3, numb=2002, database_version_id=10, external_code="other"),
    ]

    class _EG:
        numb = _Col()
        external_code = _Col()
        query = _Query(groups)

    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.EquipmentGroup",
        _EG,
    )
    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.cast",
        lambda *_args, **_kwargs: _CastExpr(),
    )
    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.all_database_version_ids_for_refdata",
        lambda: [10, 20, 30],
    )

    targets = resolve_equipment_group_import_targets(
        1001,
        fill_missing_versions=True,
        require_group_match=True,
    )
    assert (1, 10) in targets
    assert (2, 20) in targets
    assert (None, 30) in targets
    assert (3, 10) not in targets


def test_resolve_targets_without_match_returns_empty(monkeypatch):
    class _EG:
        numb = _Col()
        external_code = _Col()
        query = _Query([])

    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.EquipmentGroup",
        _EG,
    )
    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.cast",
        lambda *_args, **_kwargs: _CastExpr(),
    )
    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.all_database_version_ids_for_refdata",
        lambda: [10, 20],
    )
    assert resolve_equipment_group_import_targets(9999, fill_missing_versions=True) == []


def test_resolve_targets_without_match_can_fill_all_versions(monkeypatch):
    class _EG:
        numb = _Col()
        external_code = _Col()
        query = _Query([])

    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.EquipmentGroup",
        _EG,
    )
    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.cast",
        lambda *_args, **_kwargs: _CastExpr(),
    )
    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.fuel_import_all_versions.all_database_version_ids_for_refdata",
        lambda: [10, 20],
    )
    targets = resolve_equipment_group_import_targets(
        9999,
        fill_missing_versions=True,
        require_group_match=False,
    )
    assert targets == [(None, 10), (None, 20)]


def test_lookup_imported_row_uses_version_when_group_is_missing():
    storage = [
        _Model(equipment_group_id=None, year_number=2024, database_version_id=10),
        _Model(equipment_group_id=None, year_number=2024, database_version_id=20),
        _Model(equipment_group_id=5, year_number=2024, database_version_id=10),
    ]
    _Model.query = _Query(storage)
    found = lookup_imported_row(
        _Model,
        equipment_group_id=None,
        year_number=2024,
        database_version_id=20,
    )
    assert found is storage[1]
    found_eg = lookup_imported_row(
        _Model,
        equipment_group_id=5,
        year_number=2024,
        database_version_id=99,
    )
    assert found_eg is storage[2]
