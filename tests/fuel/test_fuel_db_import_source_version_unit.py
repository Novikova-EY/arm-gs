from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.fuel.services.fuel_imports import import_fuel_db_equipment_groups_services as service


Base = declarative_base()


class ImportStation(Base):
    __tablename__ = "import_stations"
    id = Column(Integer, primary_key=True)
    database_version_id = Column(Integer)
    external_code = Column(String)


class ImportMachine(Base):
    __tablename__ = "import_machines"
    id = Column(Integer, primary_key=True)
    database_version_id = Column(Integer)
    external_code = Column(String)
    id_station = Column(Integer)
    machine_number = Column(String)
    machine_name = Column(String)


@pytest.fixture
def source_db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        monkeypatch.setattr(service.db, "session", session)
        monkeypatch.setattr(service, "Station", ImportStation)
        monkeypatch.setattr(service, "Machine", ImportMachine)
        monkeypatch.setattr(ImportStation, "query", session.query(ImportStation), raising=False)
        monkeypatch.setattr(ImportMachine, "query", session.query(ImportMachine), raising=False)
        session.add_all([
            ImportStation(id=1, database_version_id=20, external_code="station"),
            ImportStation(id=2, database_version_id=37, external_code="station"),
            ImportStation(id=3, database_version_id=46, external_code="station"),
            ImportStation(id=4, database_version_id=37, external_code="other-station"),
            ImportMachine(id=11, database_version_id=20, external_code="machine", id_station=1,
                          machine_number="1", machine_name="Old name"),
            ImportMachine(id=12, database_version_id=37, external_code="machine", id_station=2,
                          machine_number="2", machine_name="Renamed"),
            ImportMachine(id=13, database_version_id=46, external_code="machine", id_station=3,
                          machine_number="3", machine_name="Another name"),
            ImportMachine(id=14, database_version_id=37, external_code="different", id_station=2,
                          machine_number="1", machine_name="Old name"),
            ImportMachine(id=15, database_version_id=37, external_code="machine", id_station=4,
                          machine_number="1", machine_name="Old name"),
        ])
        session.commit()
        yield session
    engine.dispose()


def _versions():
    return [
        SimpleNamespace(id=20, version_number="СиПР 2026-2031 (ТОПЛИВО)"),
        SimpleNamespace(id=37, version_number="Рабочая"),
        SimpleNamespace(id=46, version_number="Утвержденная"),
    ]


@pytest.mark.parametrize("station_id,machine_id", [(1, 11), (2, 12), (3, 13)])
def test_source_ids_resolve_to_fuel_independently_of_selected_version(source_db, station_id, machine_id):
    frame = pd.DataFrame({
        "id_station": [station_id, station_id],
        "id_machine": [machine_id, None],
        "equipment_group": ["ТЭЦ", "ТЭЦ"],
    }, index=[5, 9])
    original = frame.copy()

    result = service._resolve_fuel_source_ids_for_import(frame, _versions())

    assert result["id_station"].tolist() == [1, 1]
    assert result.loc[5, "id_machine"] == 11
    assert pd.isna(result.loc[9, "id_machine"])
    assert result["equipment_group"].tolist() == ["ТЭЦ", "ТЭЦ"]
    assert result.index.tolist() == [5, 9]
    pd.testing.assert_frame_equal(frame, original)


def test_fuel_version_is_selected_by_name_not_fixed_id(source_db):
    versions = [
        SimpleNamespace(id=20, version_number="Архив"),
        SimpleNamespace(id=46, version_number="Другая версия (топливо)"),
    ]
    frame = pd.DataFrame({"id_station": [1], "id_machine": [11]})
    result = service._resolve_fuel_source_ids_for_import(frame, versions)
    assert result.iloc[0].to_dict() == {"id_station": 3, "id_machine": 13}


def test_blank_and_invalid_ids_are_not_filled_from_adjacent_rows(source_db):
    frame = pd.DataFrame({"id_station": [1, "–", "invalid", None], "id_machine": [11, "", None, None]})
    result = service._resolve_fuel_source_ids_for_import(frame, _versions())
    pd.testing.assert_frame_equal(result, frame)


def test_native_export_and_unknown_ids_keep_existing_handling(source_db):
    frame = pd.DataFrame({"id_station": [4, 999, None], "id_machine": [None, 999, None]})
    result = service._resolve_fuel_source_ids_for_import(frame, _versions())
    pd.testing.assert_frame_equal(result, frame)


def test_import_without_fuel_version_keeps_native_ids(source_db):
    frame = pd.DataFrame({"id_station": [2], "id_machine": [12]})
    result = service._resolve_fuel_source_ids_for_import(frame, _versions()[1:])
    pd.testing.assert_frame_equal(result, frame)


def test_ambiguous_fuel_version_fails_before_processing(source_db):
    versions = _versions() + [SimpleNamespace(id=99, version_number="Другая (топливо)")]
    with pytest.raises(ValueError, match="несколько версий БД ТОПЛИВО"):
        service._resolve_fuel_source_ids_for_import(pd.DataFrame({"id_station": [1]}), versions)


def test_standalone_rows_do_not_require_fuel_version():
    frame = pd.DataFrame({"id_station": [None], "equipment_group": ["Котельные"]})
    pd.testing.assert_frame_equal(service._resolve_fuel_source_ids_for_import(frame, []), frame)


def test_machine_external_code_wins_over_signature_in_every_version(source_db, monkeypatch):
    monkeypatch.setattr(service, "_get_station_family_for_import", lambda station: (
        source_db.query(ImportStation).filter_by(external_code=station.external_code).all()
    ))
    monkeypatch.setattr(service, "_get_machine_company_identity_keys_for_import", lambda *a, **kw: set())
    monkeypatch.setattr(service, "_get_station_machine_company_ids_for_import", lambda *a: set())

    machines = service._get_machine_family_for_import(source_db.get(ImportMachine, 11), anchor_station_id=1)

    assert [machine.id for machine in machines] == [11, 12, 13]
    assert [machine.database_version_id for machine in machines] == [20, 37, 46]


def test_legacy_signature_matching_remains_when_external_code_has_no_analog(source_db, monkeypatch):
    source_db.get(ImportMachine, 12).external_code = "changed-legacy-code"
    source_db.get(ImportMachine, 13).external_code = "changed-legacy-code-2"
    source_db.flush()
    monkeypatch.setattr(service, "_get_station_family_for_import", lambda station: (
        source_db.query(ImportStation).filter_by(external_code=station.external_code).all()
    ))
    monkeypatch.setattr(service, "_get_machine_company_identity_keys_for_import", lambda *a, **kw: set())
    monkeypatch.setattr(service, "_get_station_machine_company_ids_for_import", lambda *a: set())

    machines = service._get_machine_family_for_import(source_db.get(ImportMachine, 11), anchor_station_id=1)

    assert [machine.id for machine in machines] == [11, 14, 13]
