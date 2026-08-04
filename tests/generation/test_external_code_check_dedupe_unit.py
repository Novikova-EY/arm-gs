# -*- coding: utf-8 -*-
"""Дедупликация станций на странице external_code_check."""

from types import SimpleNamespace

from app.generation.services.station_services import external_code_check_services as svc


def test_company_sets_compatible_empty_and_overlap():
    assert svc._company_sets_compatible(set(), {"a"}) is True
    assert svc._company_sets_compatible({"a"}, {"a", "b"}) is True
    assert svc._company_sets_compatible({"a"}, {"b"}) is False


def test_should_apply_company_split_only_in_preferred_version():
    assert svc._should_apply_company_split(1, 1, preferred_version_id=1) is True
    assert svc._should_apply_company_split(1, 2, preferred_version_id=1) is False
    assert svc._should_apply_company_split(2, 2, preferred_version_id=1) is False
    assert svc._should_apply_company_split(2, 2, preferred_version_id=None) is True


def test_dedupe_keeps_same_name_stations_with_disjoint_gen_companies(monkeypatch):
    """Две ТЭС-2 с разными генкомпаниями в одной (текущей) версии не схлопываются."""
    rows = [
        # id, external_code, version_id, rd, res
        (101, "code-shared", 1, 7, 49),
        (202, "code-shared", 1, 7, 49),
    ]

    monkeypatch.setattr(
        svc,
        "_station_company_keys_batch",
        lambda station_ids: {
            101: {"company-alpha"},
            202: {"company-beta"},
        },
    )

    station_a = SimpleNamespace(id=101, external_code="code-shared", name="ТЭС-2")
    station_b = SimpleNamespace(id=202, external_code="code-shared", name="ТЭС-2")

    monkeypatch.setattr(
        svc,
        "_station_families_for_dedupe_batch",
        lambda station_ids, company_keys_by_station=None: {
            101: [station_a, station_b],
            202: [station_a, station_b],
        },
    )

    result = svc.dedupe_station_ids_from_rows(
        rows,
        preferred_version_id=1,
        machine_counts={101: 2, 202: 3},
    )
    assert sorted(result) == [101, 202]


def test_dedupe_collapses_same_code_same_company_across_versions(monkeypatch):
    rows = [
        (101, "code-a", 1, 7, 49),
        (102, "code-a", 2, 7, 49),
    ]

    monkeypatch.setattr(
        svc,
        "_station_company_keys_batch",
        lambda station_ids: {
            101: {"company-alpha"},
            102: {"company-alpha"},
        },
    )
    monkeypatch.setattr(
        svc,
        "_station_families_for_dedupe_batch",
        lambda station_ids, company_keys_by_station=None: {
            sid: [SimpleNamespace(id=sid, external_code="code-a")] for sid in station_ids
        },
    )

    result = svc.dedupe_station_ids_from_rows(rows, preferred_version_id=1)
    assert result == [101]


def test_dedupe_collapses_same_code_company_change_across_versions(monkeypatch):
    """Смена генкомпании между версиями у того же external_code — одна строка."""
    rows = [
        (451, "code-efrem", 7, 77, 70),
        (37167, "code-efrem", 47, 3231, 2907),
    ]

    monkeypatch.setattr(
        svc,
        "_station_company_keys_batch",
        lambda station_ids: {
            451: {"company-kvadra"},
            37167: {"company-rir"},
        },
    )
    monkeypatch.setattr(
        svc,
        "_station_families_for_dedupe_batch",
        lambda station_ids, company_keys_by_station=None: {
            sid: [SimpleNamespace(id=sid, external_code="code-efrem")] for sid in station_ids
        },
    )

    result = svc.dedupe_station_ids_from_rows(rows, preferred_version_id=47)
    assert result == [37167]


def test_dedupe_keeps_same_name_different_codes_disjoint_companies(monkeypatch):
    rows = [
        (101, "code-a", 1, 7, 49),
        (202, "code-b", 1, 7, 49),
    ]

    monkeypatch.setattr(
        svc,
        "_station_company_keys_batch",
        lambda station_ids: {
            101: {"company-alpha"},
            202: {"company-beta"},
        },
    )

    station_a = SimpleNamespace(id=101, external_code="code-a", name="ТЭС-2")
    station_b = SimpleNamespace(id=202, external_code="code-b", name="ТЭС-2")
    monkeypatch.setattr(
        svc,
        "_station_families_for_dedupe_batch",
        lambda station_ids, company_keys_by_station=None: {
            101: [station_a, station_b],
            202: [station_a, station_b],
        },
    )

    result = svc.dedupe_station_ids_from_rows(rows, preferred_version_id=1)
    assert sorted(result) == [101, 202]


def test_filter_stations_by_company_compatibility():
    anchor = SimpleNamespace(id=1, external_code="code-a")
    other_same = SimpleNamespace(id=2, external_code="code-other")
    other_diff = SimpleNamespace(id=3, external_code="code-other-2")
    other_same_code = SimpleNamespace(id=4, external_code="code-a")
    company_map = {
        1: {"alpha"},
        2: {"alpha"},
        3: {"beta"},
        4: {"beta"},
    }
    filtered = svc._filter_stations_by_company_compatibility(
        anchor,
        [anchor, other_same, other_diff, other_same_code],
        company_map,
    )
    assert [item.id for item in filtered] == [1, 2, 4]
