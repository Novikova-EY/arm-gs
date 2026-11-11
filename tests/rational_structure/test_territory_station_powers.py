from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from test_calculation_pages import calculation_database
from test_territory_equipment_perimeter import ees_reference
from test_territory_data import database, http_client, posted_table, territory_client, territory_database
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import TerritoryInput
from app.rational_structure.services import territory_equipment_services as services
from app.rational_structure.services.territory_input_services import (
    build_territory_input_context, save_territory_inputs, territory_station_power_row_keys,
)
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType


@pytest.fixture
def station_powers(ees_reference):
    db.session.execute(StationType.__table__.insert(), [
        dict(id=index, name=name, database_version_id=1)
        for index, name in enumerate(('ГЭС', 'ВЭС', 'СЭС', 'ГАЭС', 'СНЭЭ'), 2)
    ])

    def add_station(station_id, station_type, powers, zone=1, version=1):
        db.session.execute(Station.__table__.insert(), dict(
            id=station_id, name=f'Станция {station_id}', external_code=f'station-{station_id}',
            id_station_type=station_type, id_regional_district=zone, database_version_id=version))
        for index, annual in enumerate(powers):
            machine_id = station_id * 10 + index
            db.session.execute(Machine.__table__.insert(), dict(
                id=machine_id, id_station=station_id, machine_number=str(index + 1),
                machine_name=f'Агрегат {machine_id}', external_code=f'machine-{machine_id}',
                database_version_id=version))
            db.session.add_all([
                MachinePower(id_machine=machine_id, year_number=year, p_ust=power, database_version_id=version)
                for year, power in zip((2024, 2025), annual)
            ])

    add_station(10, 2, [(Decimal('24.999999999'), 25), (25, 25)])
    add_station(11, 2, [(30, 30), (30, 30)])
    add_station(12, 2, [(50, Decimal('49.5'))])
    add_station(13, 2, [(None, 0)])
    add_station(14, 2, [(49, 49), (100, 100)])
    add_station(20, 3, [(Decimal('1.123456789'), Decimal('2.5')), (Decimal('3.5'), Decimal('4.75'))])
    add_station(30, 4, [(Decimal('2.123456789'), Decimal('3.5')), (4, 5)])
    add_station(31, 4, [(10, 20)])
    add_station(40, 2, [(100, 120)], zone=2)
    add_station(41, 3, [(11, 12)], zone=2)
    add_station(42, 4, [(13, 14)], zone=2)
    add_station(43, 5, [(500, 500)])
    add_station(44, 6, [(Decimal('2.5'), 3)])
    add_station(50, 2, [(999, 999)], version=2)
    db.session.get(Machine, 141).is_archived = True
    db.session.add(MachinePower(id_machine=100, year_number=2024, p_ust=9999, database_version_id=2))
    db.session.commit()


def test_station_type_order_uses_reference_display_order(station_powers):
    order = {1: 2, 2: 4, 3: 3, 4: 5, 5: 6, 6: 1}
    for type_id, display_order in order.items():
        db.session.execute(StationType.__table__.update().where(StationType.id == type_id).values(
            display_order=display_order))
    db.session.commit()
    assert services.load_territory_station_types(1) == ['СНЭЭ', 'ТЭС', 'ВЭС', 'ГЭС', 'СЭС', 'ГАЭС']
    assert services.load_territory_station_types(2) == []


def test_hydro_threshold_uses_station_total_for_each_year_not_individual_units(station_powers):
    totals = services.load_territory_station_power_totals(1, 1, [2024, 2025, 2026])
    # SQLite суммирует Numeric через float; PostgreSQL сохраняет точную десятичную сумму.
    assert totals['ГЭС до 50 МВт'] == pytest.approx(
        [Decimal('98.999999999'), Decimal('98.5'), 0], rel=0, abs=Decimal('1e-12'))
    assert totals['ГЭС более 50 МВт'] == [110, 110, 0]
    assert sum(totals[label][0] for label in ('ГЭС до 50 МВт', 'ГЭС более 50 МВт')) == pytest.approx(
        Decimal('208.999999999'), rel=0, abs=Decimal('1e-12'))


def test_wind_and_solar_sum_card_power_with_full_precision_and_no_year_fallback(station_powers):
    totals = services.load_territory_station_power_totals(1, 1, [2024, 2025, 2026])
    assert totals['ВЭС'] == pytest.approx(
        [Decimal('4.623456789'), Decimal('7.25'), 0], rel=0, abs=Decimal('1e-12'))
    assert totals['СЭС'] == pytest.approx(
        [Decimal('16.123456789'), Decimal('28.5'), 0], rel=0, abs=Decimal('1e-12'))


def test_station_power_zone_version_and_type_isolation(station_powers):
    second_zone = services.load_territory_station_power_totals(1, 2, [2024, 2025])
    assert second_zone == {'ГЭС до 50 МВт': [0, 0], 'ГЭС более 50 МВт': [100, 120],
                           'ВЭС': [11, 12], 'СЭС': [13, 14], 'ГАЭС': [0, 0], 'СНЭЭ': [0, 0]}
    national = services.load_territory_station_power_totals(1, None, [2024, 2025])
    assert national['ГЭС более 50 МВт'] == [210, 230]
    assert national['ГАЭС'] == [500, 500]
    assert national['СНЭЭ'] == [Decimal('2.5'), 3]
    assert national['ВЭС'] == pytest.approx(
        [Decimal('15.623456789'), Decimal('19.25')], rel=0, abs=Decimal('1e-12'))
    assert national['СЭС'] == pytest.approx(
        [Decimal('29.123456789'), Decimal('42.5')], rel=0, abs=Decimal('1e-12'))
    other_version = services.load_territory_station_power_totals(2, None, [2024, 2025])
    # Станция другой версии связана с субъектом/энергозоной версии 1 и в итог не входит.
    assert other_version == {'ГЭС до 50 МВт': [0, 0], 'ГЭС более 50 МВт': [0, 0],
                             'ВЭС': [0, 0], 'СЭС': [0, 0], 'ГАЭС': [0, 0], 'СНЭЭ': [0, 0]}
    assert services.load_territory_station_power_totals(3, None, [2024]) == {
        label: [0] for labels in services.TERRITORY_STATION_POWER_LABELS.values() for label in labels}


def test_initial_and_remaining_station_power_rows_are_recalculated(territory_client, monkeypatch):
    totals = {'ГЭС до 50 МВт': [Decimal('49.5'), 0], 'ГЭС более 50 МВт': [50, 60],
              'ВЭС': [Decimal('1.123456789'), 2], 'СЭС': [3, 4], 'ГАЭС': [0, 0], 'СНЭЭ': [0, 0]}
    monkeypatch.setattr(services, 'load_territory_station_power_totals', lambda *args: totals)
    monkeypatch.setattr(services, 'load_territory_equipment_sources', lambda version: ([], [], [], [], 2025))
    context = build_territory_input_context(1, 1, 'equipment')
    context['years'] = [2025, 2026]
    for row in context['rows']:
        row['cells'] = ['7', '8']
    original = {row['key']: list(row['cells']) for row in context['rows']}
    services.populate_territory_equipment_rows(context)
    keys = territory_station_power_row_keys()
    assert keys == frozenset(('35', '36', '68', '69', '123', '124', '156', '157'))
    for row in context['rows']:
        if row['key'] in keys:
            assert row['cells'] == [str(value) if value else '' for value in totals[row['label']]]
            assert row['readonly'] is True and not row['formula']
        elif row['key'] in original and not row.get('equipment_rollup'):
            assert row['cells'] == original[row['key']]


@pytest.mark.parametrize('zone', [1, 0])
def test_station_power_render_export_and_selected_year(territory_client, monkeypatch, zone):
    values = {'ГЭС до 50 МВт': Decimal('49.123456789'), 'ГЭС более 50 МВт': Decimal(50),
              'ВЭС': Decimal('1.123456789'), 'СЭС': Decimal('2.987654321'),
              'ГАЭС': Decimal(5), 'СНЭЭ': Decimal('1.5')}
    monkeypatch.setattr(services, 'load_territory_station_power_totals',
                        lambda version, zone_id, years: {label: [value] * len(years) for label, value in values.items()})
    client, _ = territory_client
    query = dict(energy_zone_id=zone, sheet='equipment', start_year=2025, end_year=2030,
                 view_year=2026, rounding_digits=3)
    html = client.get('/rational_structure/territory_inputs', query_string=query).get_data(as_text=True)
    assert '49,123' in html and '1,123' in html and '2,988' in html
    assert 'data-year="2026"' in html and 'data-year="2025"' not in html
    for key in territory_station_power_row_keys():
        assert f'name="value_{key}_2026"' not in html
    if zone:
        assert 'name="value_164_2026"' in html
        assert 'name="note_123"' in html
    response = client.get('/rational_structure/territory_inputs/export', query_string=query)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        rows = list(book.active.values)
        for label, value in values.items():
            row = next(row for row in rows if row[1] == label)
            assert row[2] == 'МВт'
            assert Decimal(str(row[3])) == value
    finally:
        book.close()


def test_calculated_station_powers_cannot_be_overwritten_but_notes_and_resources_can(territory_client):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    context = build_territory_input_context(1, 1, 'equipment')
    form = posted_table(context)
    for key in territory_station_power_row_keys():
        form[f'value_{key}_2025'] = '999'
        response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
            database_version_id=1, energy_zone_id=1, sheet='equipment', row_key=key, year=2025,
            field='value', value='999'))
        assert response.status_code == 400 and 'автоматически' in response.json['error']
    save_territory_inputs(context, form, 'tester')
    saved = db.session.scalar(select(TerritoryInput))
    assert all(saved.rows[int(key)]['values'][0] is None for key in territory_station_power_row_keys())
    for row_key, field, value in [('123', 'note', 'Примечание ГЭС'), ('164', 'value', '25')]:
        response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
            database_version_id=1, energy_zone_id=1, sheet='equipment', row_key=row_key, year=2025,
            field=field, value=value))
        assert response.status_code == 200
    db.session.refresh(saved)
    assert saved.rows[123]['note'] == 'Примечание ГЭС'
    assert saved.rows[164]['values'][0] == '25'


@pytest.mark.parametrize('zone', [None, 1, 2])
def test_station_type_totals_and_hydro_threshold_do_not_depend_on_equipment_group(station_powers, zone):
    expected = services.load_territory_station_power_totals(1, zone, [2024, 2025])
    for group_id in (999, None):
        db.session.execute(Machine.__table__.update().where(Machine.database_version_id == 1).values(
            id_equipment_group=group_id))
        db.session.commit()
        assert services.load_territory_station_power_totals(1, zone, [2024, 2025]) == expected
