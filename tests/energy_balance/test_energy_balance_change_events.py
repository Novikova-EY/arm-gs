import pytest
from sqlalchemy import Column, Integer, String, create_engine, delete, insert, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base

from app.energy_balance.services import energy_balance_cache as cache
from app.energy_balance.services.energy_balance_change_events import init_energy_balance_change_events


Base = declarative_base()


class BalanceValue(Base):
    __module__ = "app.energy_balance.models.test_source"
    __tablename__ = "balance_value"
    id = Column(Integer, primary_key=True)
    value = Column(Integer)


class ConsumptionValue(Base):
    __module__ = "app.energy_consumption.models.test_source"
    __tablename__ = "consumption_value"
    id = Column(Integer, primary_key=True)
    value = Column(Integer)


class OtherValue(Base):
    __module__ = "app.logs.models.test_source"
    __tablename__ = "log_value"
    id = Column(Integer, primary_key=True)
    value = Column(String)


@pytest.fixture
def source_db(monkeypatch):
    monkeypatch.setattr(cache, "get_redis_client", lambda: None)
    monkeypatch.setattr(cache, "get_current_db_version_id", lambda: 7)
    monkeypatch.setattr(cache, "_cache_generation", 0)
    monkeypatch.setattr(cache, "_data_revision", 0)
    monkeypatch.setattr(cache, "_memory_cache", {})
    init_energy_balance_change_events()
    init_energy_balance_change_events()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_cache_changes_only_after_commit_and_after_every_real_write(source_db):
    session = source_db
    session.add(BalanceValue(id=1, value=10))
    session.flush()
    assert cache.get_energy_balance_cache_generation() == 0
    assert cache.get_energy_balance_data_revision() == 0
    session.commit()
    assert cache.get_energy_balance_cache_generation() == 1
    assert cache.get_energy_balance_data_revision() == 1
    assert cache.cached_load("test", (), lambda: 10) == 10
    row = session.get(BalanceValue, 1)
    row.value = 20
    assert cache.cached_load("test", (), lambda: 20) == 10
    session.commit()
    assert cache.cached_load("test", (), lambda: 20) == 20
    assert row.value == 20
    row.value = 20
    session.commit()
    assert cache.get_energy_balance_cache_generation() == 2
    assert cache.get_energy_balance_data_revision() == 2
    session.delete(row)
    session.commit()
    assert cache.get_energy_balance_cache_generation() == 3
    assert cache.get_energy_balance_data_revision() == 3


def test_consumption_changes_invalidate_balance_but_logs_do_not(source_db):
    source_db.add(OtherValue(value="opened page"))
    source_db.commit()
    assert cache.get_energy_balance_cache_generation() == 0
    source_db.add(ConsumptionValue(value=25))
    source_db.commit()
    assert cache.get_energy_balance_cache_generation() == 1


@pytest.mark.parametrize("module,expected", [
    ("app.generation.models.station.station_model", 1),
    ("app.power_demand.models.energy_systems.demand", 1),
    ("app.energy_consumption.models.test_source", 1),
    ("app.energy_balance.models.regional_energy_system_transfer_model", 1),
    ("app.energy_balance.models.station_energy_generation_model", 1),
    ("app.energy_balance.models.ee_balance_export_value_model", 1),
    ("app.energy_balance.models.ee_import_export_oes_value_model", 1),
    ("app.generation.prospective_places.models.hydro_forecast", 0),
    ("app.electrical_intensity.models.test_source", 0),
    ("app.fuel.models.fue_equipment_group_fuel_param_model", 0),
    ("app.refdata.models.energy_systems.regional_energy_system_model", 0),
    ("app.territories.models.territory", 0),
])
def test_only_selected_source_modules_notify_balances(source_db, monkeypatch, module, expected):
    monkeypatch.setattr(BalanceValue, "__module__", module)
    source_db.add(BalanceValue(value=10))
    source_db.commit()
    assert cache.get_energy_balance_data_revision() == expected
    assert cache.get_energy_balance_cache_generation() == expected


def test_rollback_and_failed_commit_do_not_publish_changes(source_db):
    source_db.add(BalanceValue(id=1, value=10))
    source_db.flush()
    source_db.rollback()
    source_db.commit()
    assert cache.get_energy_balance_cache_generation() == 0
    source_db.add_all([BalanceValue(id=1, value=10), BalanceValue(id=1, value=20)])
    with pytest.raises(IntegrityError):
        source_db.commit()
    source_db.rollback()
    source_db.add(OtherValue(value="failure log"))
    source_db.commit()
    assert cache.get_energy_balance_cache_generation() == 0


def test_orm_bulk_updates_and_deletes_invalidate_cache(source_db):
    source_db.add(BalanceValue(id=1, value=10))
    source_db.commit()
    source_db.execute(update(BalanceValue).values(value=20))
    source_db.commit()
    assert cache.get_energy_balance_cache_generation() == 2
    source_db.execute(delete(BalanceValue))
    source_db.commit()
    assert cache.get_energy_balance_cache_generation() == 3


def test_orm_bulk_insert_invalidates_after_commit(source_db):
    source_db.execute(insert(ConsumptionValue), [{"value": 10}, {"value": 20}])
    assert cache.get_energy_balance_cache_generation() == 0
    source_db.commit()
    assert cache.get_energy_balance_cache_generation() == 1


def test_nested_commit_waits_for_outer_commit(source_db):
    with source_db.begin():
        with source_db.begin_nested():
            source_db.add(BalanceValue(value=10))
        assert cache.get_energy_balance_cache_generation() == 0
    assert cache.get_energy_balance_cache_generation() == 1


def test_nested_rollback_does_not_discard_outer_change(source_db):
    with source_db.begin():
        source_db.add(BalanceValue(id=1, value=10))
        source_db.flush()
        nested = source_db.begin_nested()
        source_db.add(ConsumptionValue(value=20))
        source_db.flush()
        nested.rollback()
        assert cache.get_energy_balance_cache_generation() == 0
    assert cache.get_energy_balance_cache_generation() == 1


def test_only_nested_changes_rolled_back_do_not_invalidate(source_db):
    with source_db.begin():
        nested = source_db.begin_nested()
        source_db.add(BalanceValue(value=10))
        source_db.flush()
        nested.rollback()
    assert cache.get_energy_balance_cache_generation() == 0
