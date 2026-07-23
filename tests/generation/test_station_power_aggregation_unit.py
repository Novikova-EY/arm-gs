# -*- coding: utf-8 -*-
"""Unit tests: агрегация мощностей станции из MachinePower."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.generation.services.station_services import station_power_aggregation as agg
from app.generation.services.station_services.station_services import (
    assign_machine_powers_by_year,
    recalculate_station_powers_by_filtered_machines,
)


def test_aggregate_powers_from_year_maps_sums_machines():
    m1 = {
        2024: {"p_ust": Decimal("10.5"), "p_ogr": Decimal("1"), "p_rasp": Decimal("9")},
        2025: {"p_ust": Decimal("11"), "p_ogr": None, "p_rasp": Decimal("10")},
    }
    m2 = {
        2024: {"p_ust": Decimal("2.5"), "p_ogr": Decimal("0.5"), "p_rasp": Decimal("2")},
        2025: {"p_ust": Decimal("3"), "p_ogr": Decimal("0"), "p_rasp": Decimal("2.5")},
    }

    result = agg.aggregate_powers_from_year_maps([m1, m2], start_year=2024, end_year=2025)

    assert result[2024]["p_ust"] == Decimal("13.0")
    assert result[2024]["p_ogr"] == Decimal("1.5")
    assert result[2024]["p_rasp"] == Decimal("11")
    assert result[2025]["p_ust"] == Decimal("14")
    assert result[2025]["p_ogr"] == Decimal("0")
    assert result[2025]["p_rasp"] == Decimal("12.5")


def test_aggregate_powers_from_year_maps_respects_year_window():
    m1 = {
        2023: {"p_ust": Decimal("100"), "p_ogr": Decimal("0"), "p_rasp": Decimal("0")},
        2024: {"p_ust": Decimal("10"), "p_ogr": Decimal("1"), "p_rasp": Decimal("9")},
        2026: {"p_ust": Decimal("50"), "p_ogr": Decimal("0"), "p_rasp": Decimal("0")},
    }

    result = agg.aggregate_powers_from_year_maps([m1], start_year=2024, end_year=2025)

    assert set(result) == {2024}
    assert result[2024]["p_ust"] == Decimal("10")


def test_aggregate_powers_from_year_maps_handles_empty_and_none():
    assert agg.aggregate_powers_from_year_maps([]) == {}
    assert agg.aggregate_powers_from_year_maps([None, {}, {}]) == {}


def test_aggregate_powers_from_machine_power_rows_dedupes_by_max_id():
    rows = [
        SimpleNamespace(id=1, id_machine=10, year_number=2024, p_ust=Decimal("1"), p_ogr=Decimal("0"), p_rasp=Decimal("1")),
        SimpleNamespace(id=5, id_machine=10, year_number=2024, p_ust=Decimal("7"), p_ogr=Decimal("2"), p_rasp=Decimal("6")),
        SimpleNamespace(id=2, id_machine=11, year_number=2024, p_ust=Decimal("3"), p_ogr=Decimal("1"), p_rasp=Decimal("2")),
        SimpleNamespace(id=3, id_machine=11, year_number=2025, p_ust=Decimal("4"), p_ogr=None, p_rasp=Decimal("3")),
    ]

    result = agg.aggregate_powers_from_machine_power_rows(rows, start_year=2024, end_year=2025)

    # machine 10 year 2024: id=5 wins (7), machine 11: 3 → total 10
    assert result[2024]["p_ust"] == Decimal("10")
    assert result[2024]["p_ogr"] == Decimal("3")
    assert result[2024]["p_rasp"] == Decimal("8")
    assert result[2025]["p_ust"] == Decimal("4")
    assert result[2025]["p_ogr"] == Decimal("0")


def test_aggregate_powers_from_machine_power_rows_ignores_out_of_range():
    rows = [
        SimpleNamespace(id=1, id_machine=1, year_number=2020, p_ust=Decimal("9"), p_ogr=0, p_rasp=0),
        SimpleNamespace(id=2, id_machine=1, year_number=2024, p_ust=Decimal("1"), p_ogr=0, p_rasp=0),
    ]
    result = agg.aggregate_powers_from_machine_power_rows(rows, start_year=2024, end_year=2024)
    assert set(result) == {2024}
    assert result[2024]["p_ust"] == Decimal("1")


def test_assign_station_powers_from_filtered_machines_sets_attribute():
    station = SimpleNamespace(
        machines=[
            SimpleNamespace(
                powers_by_year={
                    2024: {"p_ust": Decimal("2"), "p_ogr": Decimal("0"), "p_rasp": Decimal("1")},
                    2025: {"p_ust": Decimal("3"), "p_ogr": Decimal("1"), "p_rasp": Decimal("2")},
                }
            ),
            SimpleNamespace(
                powers_by_year={
                    2024: {"p_ust": Decimal("5"), "p_ogr": Decimal("1"), "p_rasp": Decimal("4")},
                }
            ),
        ]
    )

    agg.assign_station_powers_from_filtered_machines([station], 2024, 2025)

    assert station.powers_by_year[2024]["p_ust"] == Decimal("7")
    assert station.powers_by_year[2024]["p_ogr"] == Decimal("1")
    assert station.powers_by_year[2025]["p_ust"] == Decimal("3")


def test_recalculate_station_powers_by_filtered_machines_wrapper():
    station = SimpleNamespace(
        machines=[
            SimpleNamespace(
                powers_by_year={
                    2030: {"p_ust": Decimal("1.25"), "p_ogr": Decimal("0.25"), "p_rasp": Decimal("1")},
                }
            )
        ]
    )
    recalculate_station_powers_by_filtered_machines([station], 2030, 2030, rounding_digits=2)
    assert station.powers_by_year[2030]["p_ust"] == Decimal("1.25")


def test_assign_machine_powers_by_year_keeps_max_id_duplicate():
    machine = SimpleNamespace(
        machine_powers=[
            SimpleNamespace(id=1, year_number=2024, p_ust=Decimal("1"), p_ogr=Decimal("0"), p_rasp=Decimal("1")),
            SimpleNamespace(id=9, year_number=2024, p_ust=Decimal("8"), p_ogr=Decimal("2"), p_rasp=Decimal("7")),
            SimpleNamespace(id=2, year_number=2025, p_ust=Decimal("3"), p_ogr=None, p_rasp=Decimal("2")),
            SimpleNamespace(id=3, year_number=2010, p_ust=Decimal("100"), p_ogr=0, p_rasp=0),
        ]
    )
    assign_machine_powers_by_year(machine, 2024, 2025, rounding_digits=2)
    assert machine.powers_by_year[2024]["p_ust"] == Decimal("8")
    assert machine.powers_by_year[2025]["p_ust"] == Decimal("3")
    assert 2010 not in machine.powers_by_year


def test_load_station_powers_by_year_builds_sql_sum(monkeypatch):
    captured = {}

    class _Row:
        def __init__(self, year, p_ust, p_ogr, p_rasp):
            self.year_number = year
            self.p_ust = p_ust
            self.p_ogr = p_ogr
            self.p_rasp = p_rasp

    class _Query:
        def join(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def group_by(self, *a, **k):
            return self

        def all(self):
            return [
                _Row(2024, Decimal("12.5"), Decimal("1.5"), Decimal("11")),
                _Row(2025, Decimal("13"), 0, Decimal("12")),
            ]

    def fake_query(*args, **kwargs):
        captured["args"] = args
        return _Query()

    fake_db = MagicMock()
    fake_db.session.query.side_effect = fake_query
    monkeypatch.setattr(agg, "db", fake_db)
    monkeypatch.setattr(agg, "filter_by_db_version", lambda q, model: q)
    monkeypatch.setattr(agg, "filter_by_explicit_db_version", lambda q, model, vid: q)

    result = agg.load_station_powers_by_year(42, 2024, 2025, version_id=None)

    assert result[2024]["p_ust"] == Decimal("12.5")
    assert result[2025]["p_rasp"] == Decimal("12")
    assert captured["args"]  # year_number + 3 sum labels


def test_load_station_powers_by_year_uses_explicit_version_filter(monkeypatch):
    calls = []

    class _Query:
        def join(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def group_by(self, *a, **k):
            return self

        def all(self):
            return []

    fake_db = MagicMock()
    fake_db.session.query.return_value = _Query()
    monkeypatch.setattr(agg, "db", fake_db)
    monkeypatch.setattr(
        agg,
        "filter_by_explicit_db_version",
        lambda q, model, vid: calls.append((model.__name__, vid)) or q,
    )
    monkeypatch.setattr(
        agg,
        "filter_by_db_version",
        lambda q, model: (_ for _ in ()).throw(AssertionError("should not use current version")),
    )

    agg.load_station_powers_by_year(7, 2024, 2024, version_id=99)

    assert ("MachinePower", 99) in calls
    assert ("Machine", 99) in calls


def test_load_stations_powers_by_year_batches(monkeypatch):
    class _Row:
        def __init__(self, station_id, year, p_ust):
            self.id_station = station_id
            self.year_number = year
            self.p_ust = p_ust
            self.p_ogr = 0
            self.p_rasp = 0

    class _Query:
        def join(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def group_by(self, *a, **k):
            return self

        def all(self):
            return [
                _Row(1, 2024, Decimal("10")),
                _Row(1, 2025, Decimal("11")),
                _Row(2, 2024, Decimal("20")),
            ]

    fake_db = MagicMock()
    fake_db.session.query.return_value = _Query()
    monkeypatch.setattr(agg, "db", fake_db)
    monkeypatch.setattr(agg, "filter_by_explicit_db_version", lambda q, model, vid: q)

    result = agg.load_stations_powers_by_year([1, 2], [2024, 2025], version_id=1)

    assert result[1][2024]["p_ust"] == Decimal("10")
    assert result[1][2025]["p_ust"] == Decimal("11")
    assert result[2][2024]["p_ust"] == Decimal("20")
    assert 2025 not in result[2]


def test_load_stations_powers_by_year_empty_inputs():
    assert agg.load_stations_powers_by_year([], [2024]) == {}
    assert agg.load_stations_powers_by_year([1], []) == {}


def test_station_power_model_module_removed():
    with pytest.raises(ModuleNotFoundError):
        __import__("app.generation.models.station.station_power_model")


def test_generation_models_package_no_longer_exports_station_power():
    import app.generation.models as gen_models

    assert not hasattr(gen_models, "StationPower")


def test_no_recalculate_station_power_in_station_services():
    import app.generation.services.station_services.station_services as ss

    assert not hasattr(ss, "recalculate_station_power")


def test_no_update_station_power_in_import_services():
    import app.generation.services.station_services.import_station_services as imp

    assert not hasattr(imp, "update_station_power")
