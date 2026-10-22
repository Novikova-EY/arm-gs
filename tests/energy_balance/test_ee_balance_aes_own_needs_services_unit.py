from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import app.electrical_intensity.models  # noqa: F401 – связи Year
import app.energy_consumption.models  # noqa: F401 – связи Year
import app.power_demand.models  # noqa: F401 – связи Year
import app.economics.models  # noqa: F401 – связи Year
import app.territories.models  # noqa: F401 – связи Year
import app.ecology.models  # noqa: F401 – связи Year
from app.energy_balance.models.station_energy_generation_model import StationEnergyGeneration
from app.energy_balance.services import ee_balance_aes_own_needs_services as service
from app.energy_balance.routes import ee_balance_routes as routes
from app.extensions import db


@pytest.fixture
def own_needs_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {table.schema: None for table in db.metadata.tables.values()}
        },
    )
    StationEnergyGeneration.__table__.create(engine)
    session = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", session)
    monkeypatch.setattr(service, "_commit_with_retry", session.commit)
    with Flask(__name__).app_context():
        yield session
    session.remove()
    engine.dispose()


def test_save_reload_and_clear_preserve_generation_and_other_periods(own_needs_session):
    session = own_needs_session
    for version, month, generation, own_needs in (
        (7, 0, "100", "5"), (8, 0, "200", "20"), (7, 1, "10", "1")
    ):
        session.add(StationEnergyGeneration(
            id_station=1, year_number=2026, month_number=month,
            database_version_id=version, electricity_generation=Decimal(generation),
            own_needs=Decimal(own_needs),
        ))
    session.commit()
    station = SimpleNamespace(id=1, name="АЭС")

    assert service.save_aes_own_needs(station, 2026, "6,25", 7) == Decimal("6.25")
    session.expire_all()
    rows = {(row.database_version_id, row.month_number): row for row in session.query(StationEnergyGeneration)}
    assert rows[7, 0].own_needs == Decimal("6.25")
    assert rows[7, 0].electricity_generation == Decimal("100")
    assert rows[8, 0].own_needs == Decimal("20")
    assert rows[7, 1].own_needs == Decimal("1")

    service.save_aes_own_needs(station, 2026, "", 7)
    session.expire_all()
    assert rows[7, 0].own_needs is None
    assert rows[7, 0].electricity_generation == Decimal("100")


def test_own_needs_can_be_entered_before_generation(own_needs_session):
    station = SimpleNamespace(id=1, name="АЭС")
    service.save_aes_own_needs(station, 2026, "12,5", 7)
    own_needs_session.expire_all()
    row = own_needs_session.query(StationEnergyGeneration).one()
    assert row.own_needs == Decimal("12.5")
    assert row.electricity_generation is None
    assert row.database_version_id == 7
    assert row.month_number == 0


@pytest.mark.parametrize("kind", ["own_needs", "own_needs_percent"])
@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "не число"])
def test_invalid_own_needs_are_rejected_without_saving(own_needs_session, value, kind):
    with pytest.raises(ValueError):
        service.save_aes_own_needs(SimpleNamespace(id=1, name="АЭС"), 2026, value, 7, kind=kind)
    assert own_needs_session.query(StationEnergyGeneration).count() == 0


@pytest.fixture
def station_query(monkeypatch):
    station = SimpleNamespace(id=1, name="АЭС", station_type=SimpleNamespace(name="АЭС"))
    query = Mock()
    query.options.return_value.get.return_value = station
    monkeypatch.setattr(routes, "Station", SimpleNamespace(
        query=query, station_type=routes.Station.station_type,
    ))
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 7)
    monkeypatch.setattr(routes, "_can_edit_ves_ses_energy", lambda: True)
    return station


def test_api_saves_own_needs_and_returns_display_and_raw_values(own_needs_session, station_query):
    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/", method="PATCH", json={
        "station_id": 1, "kind": "own_needs", "year": 2026,
        "value": "123,4375", "rounding_digits": 1,
    }):
        response = routes.ee_balance_ves_ses_value.__wrapped__()
    assert response.get_json()["display"] == "123,4"
    assert response.get_json()["raw"] == "123,4375"
    own_needs_session.expire_all()
    assert own_needs_session.query(StationEnergyGeneration).one().own_needs == Decimal("123.4375")


@pytest.mark.parametrize("station_type, can_edit, expected_status", [
    ("АЭС", False, 403), ("ГЭС", True, 400), ("ВЭС", True, 400),
])
def test_api_restricts_own_needs_editing(own_needs_session, station_query, monkeypatch,
                                        station_type, can_edit, expected_status):
    station_query.station_type.name = station_type
    monkeypatch.setattr(routes, "_can_edit_ves_ses_energy", lambda: can_edit)
    with Flask(__name__).test_request_context("/", method="PATCH", json={
        "station_id": 1, "kind": "own_needs", "year": 2026, "value": "5",
    }):
        response, status = routes.ee_balance_ves_ses_value.__wrapped__()
    assert status == expected_status
    assert response.get_json()["ok"] is False
    assert own_needs_session.query(StationEnergyGeneration).count() == 0


def test_percent_switches_between_manual_and_persisted_calculated_modes(own_needs_session):
    session = own_needs_session
    station = SimpleNamespace(id=1, name="AES")
    service.save_aes_own_needs(station, 2026, "7,25", 7, kind="own_needs_percent")
    session.expire_all()
    row = session.query(StationEnergyGeneration).one()
    assert row.own_needs is None
    assert row.own_needs_percent == Decimal("7.25")

    row.electricity_generation = Decimal("4000")
    session.commit()
    session.expire_all()
    assert row.own_needs_percent == Decimal("7.25")

    service.save_aes_own_needs(station, 2026, "1000", 7)
    session.expire_all()
    assert row.own_needs_percent == Decimal("25")
    with pytest.raises(ValueError):
        service.save_aes_own_needs(station, 2026, "5", 7, kind="own_needs_percent")
    assert row.own_needs_percent == Decimal("25")

    # Any ORM generation edit, including the station card, must refresh the stored percent.
    row.electricity_generation = Decimal("8000")
    session.commit()
    session.expire_all()
    assert row.own_needs_percent == Decimal("12.5")

    service.save_aes_own_needs(station, 2026, "", 7)
    session.expire_all()
    assert row.own_needs is None
    assert row.own_needs_percent == Decimal("12.5")
    service.save_aes_own_needs(station, 2026, "8,5", 7, kind="own_needs_percent")
    session.expire_all()
    assert row.own_needs_percent == Decimal("8.5")
    service.save_aes_own_needs(station, 2026, "", 7, kind="own_needs_percent")
    session.expire_all()
    assert row.own_needs_percent is None
    assert row.electricity_generation == Decimal("8000")


def test_zero_own_needs_is_filled_and_blocks_manual_percent(own_needs_session):
    station = SimpleNamespace(id=1, name="AES")
    service.save_aes_own_needs(station, 2026, "0", 7)
    own_needs_session.expire_all()
    row = own_needs_session.query(StationEnergyGeneration).one()
    assert row.own_needs == 0
    assert row.own_needs_percent is None
    row.electricity_generation = Decimal("100")
    own_needs_session.commit()
    own_needs_session.expire_all()
    assert row.own_needs_percent == 0
    with pytest.raises(ValueError):
        service.save_aes_own_needs(station, 2026, "5", 7, kind="own_needs_percent")


def test_calculated_percent_handles_missing_and_zero_generation(own_needs_session):
    station = SimpleNamespace(id=1, name="AES")
    service.save_aes_own_needs(station, 2026, "5", 7)
    row = own_needs_session.query(StationEnergyGeneration).one()
    assert row.own_needs_percent is None
    row.electricity_generation = Decimal("0")
    own_needs_session.commit()
    own_needs_session.expire_all()
    assert row.own_needs_percent is None
    row.electricity_generation = Decimal("100")
    own_needs_session.commit()
    own_needs_session.expire_all()
    assert row.own_needs_percent == Decimal("5")
    row.electricity_generation = None
    own_needs_session.commit()
    own_needs_session.expire_all()
    assert row.own_needs_percent is None


def test_manual_percent_is_scoped_to_station_year_and_version(own_needs_session):
    for station_id, year, version, percent in ((1, 2026, 7, "5"), (1, 2026, 8, "6"),
                                               (1, 2027, 7, "7"), (2, 2026, 7, "8")):
        service.save_aes_own_needs(SimpleNamespace(id=station_id, name="AES"), year,
                                  percent, version, kind="own_needs_percent")
    own_needs_session.expire_all()
    saved = {(r.id_station, r.year_number, r.database_version_id): r.own_needs_percent
             for r in own_needs_session.query(StationEnergyGeneration)}
    assert saved == {(1, 2026, 7): Decimal("5"), (1, 2026, 8): Decimal("6"),
                     (1, 2027, 7): Decimal("7"), (2, 2026, 7): Decimal("8")}


def test_api_accepts_manual_percent_only_without_own_needs(own_needs_session, station_query):
    app = Flask(__name__)
    app.secret_key = "test"
    payload = {"station_id": 1, "year": 2026, "kind": "own_needs_percent",
               "value": "5,25", "rounding_digits": 1}
    with app.test_request_context("/", method="PATCH", json=payload):
        response = routes.ee_balance_ves_ses_value.__wrapped__()
    assert response.get_json()["display"] == "5,3"
    assert response.get_json()["raw"] == "5,25"
    assert response.get_json()["own_needs_percent"]["calculated"] is False
    service.save_aes_own_needs(station_query, 2026, "10", 7)
    with app.test_request_context("/", method="PATCH", json=payload):
        response, status = routes.ee_balance_ves_ses_value.__wrapped__()
    assert status == 400
    assert response.get_json()["ok"] is False
    own_needs_session.expire_all()
    assert own_needs_session.query(StationEnergyGeneration).one().own_needs_percent is None
