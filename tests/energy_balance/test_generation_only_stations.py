from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask, g
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.orm import aliased, scoped_session
from flask_sqlalchemy.session import Session

import app.economics.models
import app.ecology.models
import app.electrical_intensity.models
import app.energy_consumption.models
import app.power_demand.models
import app.territories.models
import app.rational_structure.models
from app.extensions import db
from app.generation.models.station.station_model import Station
from app.energy_balance.models.station_energy_generation_model import StationEnergyGeneration as Generation
from app.generation.services.station_services.generation_only_visibility import (
    include_generation_only, generation_only_visible,
)
from app.energy_balance.services.station_ee_generation_page_services import build_generation_aggregates


@pytest.fixture
def station_session():
    engine = create_engine('sqlite://', execution_options={
        'schema_translate_map': {table.schema: None for table in db.metadata.tables.values()}
    })
    Station.__table__.create(engine)
    Generation.__table__.create(engine)
    from app.refdata.models.years.year_model import Year
    Year.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(insert(Station.__table__), [
            dict(id=1, name='Normal', external_code='normal', is_generation_only=False, created_as_generation_only=False, database_version_id=7),
            dict(id=2, name='Only generation', external_code='only', is_generation_only=True, created_as_generation_only=True, database_version_id=7),
        ])
        connection.execute(insert(Generation.__table__), [
            dict(id=1, id_station=1, year_number=2026, month_number=0, electricity_generation=10, database_version_id=7),
            dict(id=2, id_station=2, year_number=2026, month_number=0, electricity_generation=25, database_version_id=7),
        ])
        connection.execute(insert(Year.__table__), dict(number=2026, database_version_id=7))
    with Session(db=SimpleNamespace(engines={None: engine})) as session:
        yield session
    engine.dispose()


def test_default_queries_counts_aliases_and_direct_ids_hide_station(station_session):
    s = station_session
    assert s.scalars(select(Station.id)).all() == [1]
    assert s.query(Station).count() == 1
    assert s.get(Station, 2) is None
    alias = aliased(Station)
    assert s.scalars(select(alias.id)).all() == [1]
    assert s.scalars(select(Generation.id_station)).all() == [1]
    assert s.scalar(select(func.sum(Generation.electricity_generation))) == 10
    assert s.query(Generation).filter_by(id_station=2).first() is None


def test_generation_scope_includes_values_and_does_not_leak(station_session):
    s = station_session
    with include_generation_only():
        assert s.scalars(select(Station.id).order_by(Station.id)).all() == [1, 2]
        assert s.scalar(select(func.sum(Generation.electricity_generation))) == 35
    assert not generation_only_visible()
    assert s.scalar(select(func.sum(Generation.electricity_generation))) == 10
    with pytest.raises(RuntimeError):
        with include_generation_only():
            raise RuntimeError()
    assert not generation_only_visible()


def test_cache_keys_are_separated():
    from app.energy_balance.services.energy_balance_cache import make_energy_balance_cache_key
    from app.generation.services.station_services.aggregation_cache import get_sorted_stations_cache_key
    with Flask(__name__).app_context():
        g.current_db_version = 7
        ordinary = (make_energy_balance_cache_key('generation'), get_sorted_stations_cache_key({}))
        with include_generation_only():
            generation = (make_energy_balance_cache_key('generation'), get_sorted_stations_cache_key({}))
        assert ordinary[0] != generation[0]
        assert ordinary[1] != generation[1]


def test_generation_only_contributes_to_all_page_totals():
    stations = [SimpleNamespace(id=1, station_sign=None), SimpleNamespace(id=2, station_sign=None)]
    with patch('app.energy_balance.services.station_ee_generation_page_services._resolve_station_placement',
               return_value=(1, 2, 3, 4, 5)), patch(
        'app.energy_balance.services.station_ee_generation_page_services._resolve_station_synchronous_area_id',
        return_value=6,
    ):
        totals = build_generation_aggregates(stations, {1: {2026: Decimal(10)}, 2: {2026: Decimal(25)}})
    assert totals['total'][2026] == 35
    for level, group_id in [('energy_units', 5), ('regional_districts', 4),
                            ('regional_energy_systems', 3), ('union_energy_systems', 2),
                            ('energy_system_types', 1), ('synchronous_areas', 6)]:
        assert totals[level][group_id][2026] == 35


@pytest.fixture
def save_value(station_session, monkeypatch):
    from app.energy_balance.services import generation_only_value_services as service
    monkeypatch.setattr(db, 'session', scoped_session(lambda: station_session))
    monkeypatch.setattr(service, '_commit_with_retry', station_session.commit)
    monkeypatch.setattr(service, 'clear_energy_balance_cache', lambda: None)
    monkeypatch.setattr(service, 'log_to_db', lambda *a, **kw: None)
    with Flask(__name__).app_context():
        g.current_db_version = 7
        yield service.update_generation_only_value


def test_save_reload_months_year_and_clear(save_value, station_session):
    def save(period, value, mode='years'):
        return save_value(2, period, value, period_mode=mode, selected_year=2026, user='test')
    assert save(2026, '12,5') == Decimal('12.5')
    assert save(1, '3,25', 'months') == Decimal('3.25')
    assert save(2, '0', 'months') == Decimal(0)
    station_session.expire_all()
    with include_generation_only():
        records = station_session.query(Generation).filter_by(id_station=2).all()
        assert {r.month_number: r.electricity_generation for r in records} == {
            0: Decimal('12.5'), 1: Decimal('3.25'), 2: Decimal(0),
        }
    assert save(2026, '') is None
    with include_generation_only():
        assert station_session.query(Generation).filter_by(id_station=2, month_number=0).first() is None
        assert station_session.query(Generation).filter_by(id_station=2).count() == 2
    assert station_session.scalar(select(func.sum(Generation.electricity_generation))) == 10


@pytest.mark.parametrize('raw', ['-1', 'NaN', 'Infinity', 'abc', '1000000000'])
def test_bad_input_does_not_save(save_value, station_session, raw):
    with pytest.raises(ValueError):
        save_value(2, 2026, raw, period_mode='years', selected_year=None, user='test')
    with include_generation_only():
        assert station_session.query(Generation).filter_by(id_station=2).one().electricity_generation == 25


@pytest.mark.parametrize('station,period,mode,year', [
    (1, 2026, 'years', None), (999, 2026, 'years', None),
    (2, 2027, 'years', None), (2, 13, 'months', 2026),
    (2, 1, 'months', None),
])
def test_wrong_station_or_period_is_rejected(save_value, station, period, mode, year):
    with pytest.raises(ValueError):
        save_value(station, period, '5', period_mode=mode, selected_year=year, user='test')


def test_wrong_version_is_rejected(save_value):
    g.current_db_version = 8
    with pytest.raises(ValueError):
        save_value(2, 2026, '5', period_mode='years', selected_year=None, user='test')


@pytest.mark.parametrize('generation_only,editable', [(True, True), (True, False), (False, True)])
def test_row_renders_input_only_for_generation_only_and_editor(generation_only, editable):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)
    row = dict(station_id=2, station_name='Station', kto_display='-', station_type_name='-',
               station_sign_display='-', tes_types='-', tes_machine_type='-', primary_fuel='-',
               fuel_so='-', is_generation_only=generation_only, periods={2026: '12,5'})
    html = env.get_template('energy_balance/ee_generation/ee_generation_station_sign_group_rows.html').render(
        sign_group={'stations': [row]}, can_edit_energy_balance=editable,
        period_columns=[(2026, '2026')], rounding_digits=1,
        format_generation_input_value=lambda v, d: v, format_generation_cell=lambda v: v,
        request=SimpleNamespace(args={}), url_for=lambda *a, **kw: '/station/2',
    )
    assert ('<input' in html) == (generation_only and editable)
    assert '/station/2' in html
    assert '12,5' in html
    assert ('ee-generation-only-marker' in html) == generation_only
    if generation_only:
        assert html.index('ee-generation-only-marker') > html.index('</a>')
        assert 'не участвует в остальных расчетах' in html
        assert 'data-bs-toggle="tooltip"' in html
        assert 'tabindex="0"' in html


def test_station_card_scope_exposes_only_requested_special_station(station_session):
    s = station_session
    s.execute(insert(Station.__table__), dict(
        id=3, name='Another generation-only station', external_code='another',
        is_generation_only=True, database_version_id=7,
    ))
    s.execute(insert(Generation.__table__), dict(
        id=3, id_station=3, year_number=2026, month_number=0,
        electricity_generation=50, database_version_id=7,
    ))
    with include_generation_only(station_id=2):
        assert not generation_only_visible()
        assert s.scalars(select(Station.id).order_by(Station.id)).all() == [1, 2]
        assert s.scalar(select(func.sum(Generation.electricity_generation))) == 35
        assert s.scalars(select(Generation.id_station).order_by(Generation.id_station)).all() == [1, 2]
    assert s.scalars(select(Station.id)).all() == [1]
    assert s.scalar(select(func.sum(Generation.electricity_generation))) == 10


def test_card_scope_has_separate_cache_and_restores_scope_after_error():
    from app.generation.services.station_services.generation_only_visibility import generation_station_card
    from app.energy_balance.services.energy_balance_cache import make_energy_balance_cache_key
    from app.generation.services.station_services.aggregation_cache import get_sorted_stations_cache_key
    with Flask(__name__).app_context():
        g.current_db_version = 7
        ordinary = (make_energy_balance_cache_key('generation'), get_sorted_stations_cache_key({}))
        card_keys = []

        @generation_station_card
        def card(station_id):
            card_keys.append((make_energy_balance_cache_key('generation'), get_sorted_stations_cache_key({})))
            raise RuntimeError('test')

        with pytest.raises(RuntimeError):
            card(station_id=2)
        with pytest.raises(RuntimeError):
            card(3)
        assert ordinary[0] != card_keys[0][0] != card_keys[1][0]
        assert ordinary[1] != card_keys[0][1] != card_keys[1][1]
        assert ordinary == (make_energy_balance_cache_key('generation'), get_sorted_stations_cache_key({}))


@pytest.fixture
def change_station_mode(station_session, monkeypatch):
    from app.generation.services.station_services import station_services as service
    import app.common.services.clear_all_caches as caches
    monkeypatch.setattr(db, 'session', scoped_session(lambda: station_session))
    monkeypatch.setattr(service, '_commit_with_retry', station_session.commit)
    monkeypatch.setattr(service, 'clear_station_aggregation_cache', lambda *a: None)
    monkeypatch.setattr(service, 'log_to_db', lambda *a, **kw: None)
    monkeypatch.setattr(service, 'current_user', SimpleNamespace(is_authenticated=False))
    cleared = []
    monkeypatch.setattr(caches, 'clear_all_application_caches', lambda: cleared.append(True))

    def change(station_id, value, can_edit=True):
        with include_generation_only(station_id=station_id):
            station = station_session.get(Station, station_id)
            return service.update_station_from_form_service(
                'test', station, SimpleNamespace(), [], can_edit_generation=can_edit,
                can_edit_fuel=False, only_fields={'is_generation_only'}, is_generation_only=value,
            )

    with Flask(__name__).app_context():
        g.current_db_version = 7
        yield change, cleared


def test_converted_station_keeps_origin_and_enters_regular_sums(change_station_mode, station_session):
    change, cleared = change_station_mode
    assert station_session.scalar(select(func.sum(Generation.electricity_generation))) == 10
    assert change(2, False)
    assert cleared == [True]
    station_session.expire_all()
    station = station_session.query(Station).filter_by(id=2).one()
    assert not station.is_generation_only
    assert station.created_as_generation_only
    assert station_session.scalar(select(func.sum(Generation.electricity_generation))) == 35
    assert station_session.scalars(select(Station.id).order_by(Station.id)).all() == [1, 2]
    assert change(2, True)
    assert station_session.scalar(select(func.sum(Generation.electricity_generation))) == 10
    assert cleared == [True, True]


def test_regular_origin_cannot_be_changed_to_generation_only(change_station_mode, station_session):
    change, cleared = change_station_mode
    with pytest.raises(ValueError):
        change(1, True)
    assert cleared == []
    assert not station_session.query(Station).filter_by(id=1).one().is_generation_only


def test_generation_only_mode_requires_generation_edit_permission(change_station_mode):
    change, cleared = change_station_mode
    with pytest.raises(ValueError):
        change(2, False, can_edit=False)
    assert cleared == []


def test_unchanged_mode_does_not_clear_all_caches(change_station_mode):
    change, cleared = change_station_mode
    assert change(2, True) == []
    assert cleared == []


@pytest.fixture
def equipment_session(station_session):
    from app.generation.models.machine.machine_model import Machine
    from app.generation.models.machine.machine_power_model import MachinePower
    from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
    from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
    s = station_session
    for model in [Machine, MachinePower, PGUMachine, PGUMachinePower]:
        model.__table__.create(s.get_bind())
    s.execute(insert(Machine.__table__), [
        dict(id=1, id_station=1, external_code='m1', machine_number='1', machine_name='M1', database_version_id=7),
        dict(id=2, id_station=2, external_code='m2', machine_number='2', machine_name='M2', database_version_id=7),
    ])
    s.execute(insert(MachinePower.__table__), [
        dict(id=1, id_machine=1, p_ust=100, year_number=2026, database_version_id=7),
        dict(id=2, id_machine=2, p_ust=200, year_number=2026, database_version_id=7),
    ])
    s.execute(insert(PGUMachine.__table__), [
        dict(id=1, id_parent_machine=1, external_code='p1', machine_name='P1', database_version_id=7),
        dict(id=2, id_parent_machine=2, external_code='p2', machine_name='P2', database_version_id=7),
    ])
    s.execute(insert(PGUMachinePower.__table__), [
        dict(id=1, id_pgu_machine=1, p_ust=10, year_number=2026, database_version_id=7),
        dict(id=2, id_pgu_machine=2, p_ust=20, year_number=2026, database_version_id=7),
    ])
    s.commit()
    return s


def test_equipment_power_sums_follow_station_mode(change_station_mode, equipment_session):
    from app.generation.models.machine.machine_power_model import MachinePower
    from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
    s = equipment_session
    assert s.scalar(select(func.sum(MachinePower.p_ust))) == 100
    assert s.scalar(select(func.sum(PGUMachinePower.p_ust))) == 10
    change, _ = change_station_mode
    change(2, False)
    assert s.scalar(select(func.sum(MachinePower.p_ust))) == 300
    assert s.scalar(select(func.sum(PGUMachinePower.p_ust))) == 30
    change(2, True)
    assert s.scalar(select(func.sum(MachinePower.p_ust))) == 100
    assert s.scalar(select(func.sum(PGUMachinePower.p_ust))) == 10


@pytest.fixture
def linked_equipment_session(equipment_session):
    from app.generation.models.machine.machine_tes_type_model import MachineTesType
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
    s = equipment_session
    for model in [MachineTesType, MachineFuelParam]:
        model.__table__.create(s.get_bind())
    s.execute(insert(MachineTesType.__table__), [
        dict(id=1, id_machine=1, year_number=2026, database_version_id=7),
        dict(id=2, id_machine=2, year_number=2026, database_version_id=7),
    ])
    s.execute(insert(MachineFuelParam.__table__), [
        dict(id=1, machine_id=1, database_version_id=7),
        dict(id=2, machine_id=2, database_version_id=7),
    ])
    s.commit()
    return s


@pytest.mark.parametrize('loader', ['joined', 'selectin', 'lazy'])
def test_machine_related_records_load_with_correct_aliases(linked_equipment_session, loader):
    from sqlalchemy.orm import joinedload, selectinload, lazyload
    from app.generation.models.machine.machine_model import Machine
    load = {'joined': joinedload, 'selectin': selectinload, 'lazy': lazyload}[loader]
    s = linked_equipment_session
    machines = s.scalars(select(Machine).options(
        lazyload('*'), load(Machine.machine_tes_types), load(Machine.machine_fuel_param),
        load(Machine.machine_powers),
    ).order_by(Machine.id)).unique().all()
    assert [m.id for m in machines] == [1]
    assert [r.id for r in machines[0].machine_tes_types] == [1]
    assert machines[0].machine_fuel_param.id == 1
    assert [r.id for r in machines[0].machine_powers] == [1]


@pytest.mark.parametrize('model_name', ['tes_type', 'fuel_param', 'power', 'pgu_power'])
def test_owned_record_aliases_hide_generation_only_equipment(linked_equipment_session, model_name):
    from app.generation.models.machine.machine_tes_type_model import MachineTesType
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
    from app.generation.models.machine.machine_power_model import MachinePower
    from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
    model = {'tes_type': MachineTesType, 'fuel_param': MachineFuelParam,
             'power': MachinePower, 'pgu_power': PGUMachinePower}[model_name]
    alias = aliased(model)
    assert linked_equipment_session.scalars(select(alias.id)).all() == [1]


def test_joined_loading_keeps_machine_without_optional_records(linked_equipment_session):
    from sqlalchemy.orm import joinedload, lazyload
    from app.generation.models.machine.machine_model import Machine
    s = linked_equipment_session
    s.execute(insert(Machine.__table__), dict(
        id=3, id_station=1, external_code='m3', machine_number='3',
        machine_name='No optional records', database_version_id=7,
    ))
    s.commit()
    machine = s.scalars(select(Machine).where(Machine.id == 3).options(
        lazyload('*'), joinedload(Machine.machine_tes_types), joinedload(Machine.machine_fuel_param),
    )).unique().one()
    assert machine.machine_tes_types == []
    assert machine.machine_fuel_param is None


@pytest.fixture
def territorial_station_session(station_session, monkeypatch):
    from sqlalchemy import update
    from app.refdata.models.territories.federal_district_model import FederalDistrict
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
    from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
    from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system as links
    from app.generation.models.machine.machine_model import Machine
    from app.generation.services.station_services import station_services as service
    s = station_session
    for model in [FederalDistrict, RegionalDistrict, EnergySystemType, UnionEnergySystem, RegionalEnergySystem, Machine]:
        model.__table__.create(s.get_bind())
    links.create(s.get_bind())
    s.execute(insert(FederalDistrict.__table__), dict(id=270, name='Northwest', database_version_id=7))
    s.execute(insert(RegionalDistrict.__table__), dict(
        id=2272, name='Kaliningrad', name_full='Kaliningrad', name_rp='Kaliningrad', name_dp='Kaliningrad',
        id_federal_district=270, database_version_id=7,
    ))
    s.execute(insert(EnergySystemType.__table__), [
        dict(id=162, name='Type A', database_version_id=7),
        dict(id=163, name='Type B', database_version_id=7),
    ])
    s.execute(insert(UnionEnergySystem.__table__), [
        dict(id=311, name='Union A', id_energy_system_type=162, database_version_id=7),
        dict(id=312, name='Union B', id_energy_system_type=163, database_version_id=7),
    ])
    s.execute(insert(RegionalEnergySystem.__table__), [
        dict(id=2046, name='Region A', name_full='Region A', name_rp='Region A', id_union_energy_system=311, database_version_id=7),
        dict(id=2047, name='Region B', name_full='Region B', name_rp='Region B', id_union_energy_system=312, database_version_id=7),
    ])
    s.execute(insert(links), [
        dict(regional_district_id=2272, regional_energy_system_id=2046),
        dict(regional_district_id=2272, regional_energy_system_id=2047),
    ])
    s.execute(update(Station.__table__).values(id_regional_district=2272))
    s.execute(insert(Machine.__table__), dict(
        id=1, id_station=1, external_code='ordinary-machine', machine_number='1', machine_name='M1', database_version_id=7,
    ))
    s.commit()
    monkeypatch.setattr(db, 'session', scoped_session(lambda: s))
    monkeypatch.setattr(service, 'get_current_year', lambda: 2026)
    monkeypatch.setattr(service, 'get_decentralized_zone_energy_system_type_id', lambda: None)
    with Flask(__name__).app_context():
        g.current_db_version = 7
        yield s


@pytest.mark.parametrize('filters', [
    {'regional_energy_system_filter': [2046]},
    {'union_energy_system_filter': [311]},
    {'energy_system_type_filter': [162]},
    {'regional_energy_system_filter': [2046], 'union_energy_system_filter': [311],
     'energy_system_type_filter': [162], 'federal_district_filter': [270],
     'station_name_filter': '', 'gen_company_filter': ''},
])
def test_generation_only_station_without_direct_res_matches_district_filters(territorial_station_session, filters):
    from app.generation.services.station_services.station_services import get_stations_list
    with include_generation_only():
        result = get_stations_list(return_ids_only=True, start_year=2026, end_year=2026, **filters)
        assert 2 in result.get('station_ids', [])
    result = get_stations_list(return_ids_only=True, start_year=2026, end_year=2026, **filters)
    assert 2 not in result.get('station_ids', [])


def test_explicit_station_res_takes_precedence_over_district_filters(territorial_station_session):
    from sqlalchemy import update
    from app.generation.services.station_services.station_services import get_stations_list
    s = territorial_station_session
    s.execute(update(Station.__table__).where(Station.id == 2).values(id_regional_energy_system=2047))
    s.commit()
    with include_generation_only():
        for key, wrong, correct in [('regional_energy_system_filter', 2046, 2047),
                                    ('union_energy_system_filter', 311, 312),
                                    ('energy_system_type_filter', 162, 163)]:
            assert 2 not in get_stations_list(return_ids_only=True, start_year=2026, end_year=2026, **{key: [wrong]}).get('station_ids', [])
            assert 2 in get_stations_list(return_ids_only=True, start_year=2026, end_year=2026, **{key: [correct]}).get('station_ids', [])


def test_converted_station_territorial_list_and_aggregation_match(territorial_station_session):
    from sqlalchemy import update
    from app.generation.services.station_services.station_services import get_stations_list, get_filtered_station_ids
    s = territorial_station_session
    s.execute(update(Station.__table__).where(Station.id == 2).values(is_generation_only=False))
    s.commit()
    filters = {'regional_energy_system_filter': [2046], 'union_energy_system_filter': [311],
               'energy_system_type_filter': [162], 'federal_district_filter': [270]}
    ids = get_stations_list(return_ids_only=True, start_year=2026, end_year=2026, **filters)['station_ids']
    assert set(ids) == {1, 2}
    assert set(get_filtered_station_ids(filters)) == {1, 2}
