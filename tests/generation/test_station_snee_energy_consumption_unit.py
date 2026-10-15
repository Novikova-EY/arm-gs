# -*- coding: utf-8 -*-
"""Проверки таблицы потребления электроэнергии для СНЭЭ."""
from types import SimpleNamespace

from app.generation.models.station.station_snee_energy_consumption_model import (
    StationSneeEnergyConsumption,
)
from app.generation.services.station_services.station_type_flags import is_snee_station


def _station(type_name):
    return SimpleNamespace(station_type=SimpleNamespace(name=type_name))


def test_snee_station_type_is_detected_exclusively():
    assert is_snee_station(_station("СНЭЭ")) is True
    assert is_snee_station(_station("снээ")) is True
    assert is_snee_station(_station("СНЭЭ (опытная)")) is True
    assert is_snee_station(_station("ГАЭС")) is False
    assert is_snee_station(_station("СЭС")) is False
    assert is_snee_station(_station(None)) is False


def test_snee_consumption_model_uses_versioned_station_year_records():
    model = StationSneeEnergyConsumption
    assert model.__tablename__ == "gs_gen_station_snee_energy_consumptions"
    assert {"id_station", "year_number", "database_version_id"}.issubset(
        model.__table__.columns.keys()
    )
    assert "electricity_consumption" in model.__table__.columns


def test_snee_efficiency_is_versioned_per_station():
    from app.generation.models.station.station_snee_efficiency_model import StationSneeEfficiency

    assert StationSneeEfficiency.__tablename__ == "gs_gen_station_snee_efficiencies"
    assert {"id_station", "database_version_id", "efficiency_percent"}.issubset(
        StationSneeEfficiency.__table__.columns.keys()
    )
    assert any(
        index.name == "uq_station_snee_efficiency_station_ver"
        for index in StationSneeEfficiency.__table__.indexes
    )


def test_snee_plan_generation_uses_efficiency_percent_and_plan_years_only():
    from decimal import Decimal
    from types import SimpleNamespace

    from app.generation.routes.stations.station_details_routes import (
        _attach_snee_plan_generation,
    )

    station = SimpleNamespace(
        station_snee_efficiency_percent=Decimal("75"),
        station_snee_energy_consumption_by_year={
            2025: Decimal("12"),
            2026: Decimal("8"),
        },
    )
    _attach_snee_plan_generation(
        station, 2025, 2026, {2025: "План", 2026: "Факт"}
    )

    assert station.station_energy_plan_calc_by_year == {2025: Decimal("9.00")}


def test_snee_consumption_save_persists_year_values(monkeypatch):
    from types import SimpleNamespace

    import importlib
    import sys
    import types

    station_services = importlib.import_module(
        "app.generation.services.station_services.station_services"
    )
    added_records = []

    class Field:
        def __eq__(self, _other):
            return None

        def __ge__(self, _other):
            return None

        def __le__(self, _other):
            return None

    class Query:
        def filter(self, *_criteria):
            return self

        def all(self):
            return []

        def first(self):
            return None

    class Record:
        id_station = Field()
        year_number = Field()
        database_version_id = Field()
        query = Query()

        def __init__(self, **values):
            self.__dict__.update(values)

    fake_model_module = types.ModuleType(
        "app.generation.models.station.station_snee_energy_consumption_model"
    )
    fake_model_module.StationSneeEnergyConsumption = Record
    fake_efficiency_module = types.ModuleType(
        "app.generation.models.station.station_snee_efficiency_model"
    )

    class EfficiencyRecord:
        id_station = Field()
        query = Query()

        def __init__(self, **values):
            self.__dict__.update(values)

    fake_efficiency_module.StationSneeEfficiency = EfficiencyRecord
    monkeypatch.setitem(
        sys.modules,
        "app.generation.models.station.station_snee_energy_consumption_model",
        fake_model_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "app.generation.models.station.station_snee_efficiency_model",
        fake_efficiency_module,
    )
    version_filter = importlib.import_module("app.common.services.database_version_filter")
    monkeypatch.setattr(version_filter, "filter_by_explicit_db_version", lambda query, *_args: query)
    session = SimpleNamespace(add=added_records.append, rollback=lambda: None)
    monkeypatch.setattr(station_services, "db", SimpleNamespace(session=session))
    monkeypatch.setattr(station_services, "set_db_version_on_create", lambda _record: None)
    monkeypatch.setattr(station_services, "quick_fix_seq", lambda *_args: None)
    monkeypatch.setattr(station_services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(station_services, "log_to_db", lambda *_args, **_kwargs: None)

    station = SimpleNamespace(id=17, name="СНЭЭ", regional_district=None)
    changes = station_services.save_station_snee_energy_consumption_service(
        "tester",
        station,
        3,
        2025,
        2025,
        {
            "st_snee_consumption_2025": "12,5",
            "st_snee_consumption_2025_orig": "",
            "st_snee_efficiency_percent": "75",
            "st_snee_efficiency_percent_orig": "",
        },
    )

    assert changes == [
        "2025 г.: не указано → 12,5",
        "КПД: не указано → 75 %",
    ]
    assert len(added_records) == 2
    assert added_records[0].id_station == 17
    assert added_records[0].year_number == 2025
    assert added_records[0].database_version_id == 3
    assert str(added_records[0].electricity_consumption) == "12.5"
    assert added_records[1].id_station == 17
    assert added_records[1].database_version_id == 3
    assert str(added_records[1].efficiency_percent) == "75"
