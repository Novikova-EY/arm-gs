"""SQL aggregation preserves machine/year joins on both territorial paths."""
from decimal import Decimal

import pytest
from flask import g
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

import app.ecology.models  # noqa: F401
import app.economics.models  # noqa: F401
import app.electrical_intensity.models  # noqa: F401
import app.energy_consumption.models  # noqa: F401
import app.power_demand.models  # noqa: F401
import app.territories.models  # noqa: F401
from app.extensions import db
from app.generation.services.station_services.aggregation_station_services import aggregation_rows as service
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
    regional_district_regional_energy_system,
)


@pytest.fixture
def aggregation_db(app, monkeypatch):
    models = (
        service.Station, service.Machine, service.MachinePower,
        service.MachineFuel, service.MachineTesType, service.TesType,
        service.TesMachineType, service.Fuel, service.FuelType,
        service.EnergySystemType, service.UnionEnergySystem,
        service.RegionalEnergySystem, service.RegionalDistrict, service.EnergyUnit,
    )
    engine = create_engine("sqlite://", execution_options={
        "schema_translate_map": {table.schema: None for table in db.metadata.tables.values()}
    })
    for model in models:
        model.__table__.create(engine)
    regional_district_regional_energy_system.create(engine)
    session = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", session)
    monkeypatch.setattr(service, "get_unknown_tes_type_id", lambda: 99)
    with app.app_context():
        yield session, engine
    session.remove()
    engine.dispose()


@pytest.mark.parametrize("direct", [True, False])
@pytest.mark.parametrize("version", [None, 7])
def test_aggregation_matches_machine_year_version_and_territory(aggregation_db, direct, version):
    session, engine = aggregation_db
    g.current_db_version = version

    def insert(model, **values):
        session.execute(model.__table__.insert().values(**values))

    insert(service.EnergySystemType, id=1, name="EES")
    insert(service.UnionEnergySystem, id=1, name="OES", id_energy_system_type=1)
    insert(service.RegionalEnergySystem, id=1, name="RES", name_full="RES", name_rp="RES",
           id_union_energy_system=1)
    insert(service.RegionalDistrict, id=1, name="District", name_full="District",
           name_rp="District", name_dp="District")
    session.execute(regional_district_regional_energy_system.insert().values(
        regional_district_id=1, regional_energy_system_id=1))
    insert(service.Station, id=1, external_code="station", name="Station",
           id_regional_district=1, id_regional_energy_system=1 if direct else None,
           id_station_type=1, database_version_id=version)
    for machine_id in (1, 2, 3):
        insert(service.Machine, id=machine_id, external_code=f"machine-{machine_id}",
               machine_name=f"Machine {machine_id}", machine_number=str(machine_id),
               id_station=1, database_version_id=version, is_archived=machine_id == 3)
    for value in (1, 2):
        insert(service.TesType, id=value, name=f"TES {value}", database_version_id=version)
        insert(service.FuelType, id=value, name=f"Fuel type {value}", database_version_id=version)
        insert(service.Fuel, id=value, name=f"Fuel {value}", id_fuel_type=value,
               database_version_id=version)
    for machine_id in (1, 2, 3):
        for year in (2025, 2026, 2027):
            # Machine 2 has no fuel/type: it must survive the outer joins.
            insert(service.MachinePower, id_machine=machine_id, year_number=year,
                   p_ust=machine_id * 10, p_ogr=1, p_rasp=machine_id * 10 - 1,
                   database_version_id=version)
            if machine_id != 2:
                value = 1 if year == 2026 else 2
                insert(service.MachineTesType, id_machine=machine_id, year_number=year,
                       id_tes_type=value, database_version_id=version)
                insert(service.MachineFuel, id_machine=machine_id, year_number=year,
                       id_fuel=value, database_version_id=version)
    # Legacy powers are included, but powers belonging to a different version are not.
    if version is not None:
        insert(service.MachinePower, id_machine=1, year_number=2026, p_ust=5,
               p_ogr=0, p_rasp=5, database_version_id=None)
    insert(service.MachinePower, id_machine=1, year_number=2026, p_ust=1000,
           database_version_id=8)
    session.commit()

    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    rows = service.get_full_aggregation_rows.__wrapped__(2026, 2027, [1])
    actual = {(r.year, r.tes_type_id, r.fuel_type_id): r.p_ust for r in rows}
    assert actual == {
        (2026, 1, 1): Decimal(15 if version is not None else 10),
        (2027, 2, 2): Decimal(10),
        (2026, 99, None): Decimal(20),
        (2027, 99, None): Decimal(20),
    }
    assert all(r.regional_energy_system_id == 1 and r.regional_district_id == 1 for r in rows)
    # The SQL shape matters: joining via Machine.id caused a 70-second nested loop.
    aggregation_sql = [sql for sql in statements if "sum(" in sql.lower()]
    assert len(aggregation_sql) == 2
    for sql in aggregation_sql:
        for table in ("gs_gen_machine_tes_types", "gs_gen_machine_fuels"):
            assert f"{table}.id_machine = main.gs_gen_machine_powers.id_machine" in sql

    filtered = service.get_full_aggregation_rows.__wrapped__(
        2026, 2027, [1], {"fuel_type_filter": [1], "tes_type_filter": [1]})
    assert len(filtered) == 1
    assert filtered[0].p_ust == actual[(2026, 1, 1)]
    assert service.get_full_aggregation_rows.__wrapped__(2026, 2027, []) == []
