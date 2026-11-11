from decimal import Decimal
from io import BytesIO
import re
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from test_calculation_pages import calculation_database
from test_equipment_runtime_modernization import set_current_year
from test_territory_data import database, http_client, posted_table, territory_client, territory_database
from test_territory_equipment import runtime_row
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import TerritoryInput
from app.rational_structure.services import territory_equipment_services as services
from app.rational_structure.services.territory_input_services import (
    build_territory_input_context, save_territory_inputs, territory_nuclear_row_keys,
)
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType


@pytest.fixture
def nuclear_sources():
    groups = [SimpleNamespace(id=10, name='РБМК-1000', id_technology_type=2),
              SimpleNamespace(id=11, name='ВВЭР-1200 (1100)', id_technology_type=2)]
    technologies = [SimpleNamespace(id=2, name='АЭС')]
    rows = [runtime_row(machine, group, fuel='NUCLEAR', technology=2, power=power,
                        first=None, second=second, zone=zone)
            for machine, group, power, second, zone in (
                (100, 10, '1000', 2027, 1), (101, 10, '1000', 2029, 1),
                (102, 11, '1200', 2029, 1), (103, None, '5', None, 1),
                (104, 10, '0', 2026, 1), (105, 10, '999', 2027, 2))]
    powers = [(row['machine_id'], None, year, row['values']['N'])
              for row in rows for year in (2024, 2025)]
    powers = [(machine, part, year, Decimal(950 if machine == 100 else 900)
               if year == 2024 and machine in (100, 101) else power)
              for machine, part, year, power in powers]
    powers.append((100, None, 2027, Decimal(9999)))
    return rows, groups, technologies, powers, 2025


@pytest.fixture
def nuclear_reference_groups():
    return [SimpleNamespace(id=10 + index, name=name, id_technology_type=2)
            for index, name in enumerate(('РБМК-1000, ВВЭР-1000', 'ВВЭР-1200 (1100)',
                                          'ВВЭР-440, 600', 'БН-600, 800', 'прочее'))]


@pytest.mark.parametrize('name,power,explicit,expected', [
    ('ВВЭР-1000 (К-1000-60/1500)', '1000', None, None),
    ('РБМК-1000 (К-500-65/3000 – 2 шт)', '1000', None, None),
    ('ВВЭР – 1200', '1200', None, None),
    ('ВВЭР-1100', '1100', None, None),
    ('ВВЭР-ТОИ', '1255', None, None),
    ('ВВЭР-417 (2×К-220-44/3000)', '417', None, None),
    ('ВВЭР-440 (2×К-220/44)', '440', None, None),
    ('ВВЭР-600', '600', None, None),
    ('БН-600 (К-200-130 – 3 шт)', '600', None, None),
    ('БН-800', '800', None, None),
    ('К-1200-6,8/50', '1200', None, None),
    ('ВВЭР (К-1200-6,8/50)', '1187.634', None, None),
    ('ВВЭР (К-1000-60/1500-2)', '1041.65', None, None),
    ('ВВЭР (К-1100-60/1500-2М)', '1030.269', None, None),
    ('ВВЭР-С/600', '600', None, None),
    ('БН-1200М', '1250', None, None),
    ('К-500-65/3000-2 (2 шт)', '1000', None, None),
    ('К-220-44/3000', '440', None, None),
    ('ТК-35/38-3,4с', '35', None, None),
    ('Неизвестный агрегат', '600', None, None),
    ('ВВЭР-440', '440', 99, 99),
    ('БН-800', '800', 10, 10),
    ('ВВЭР-1000', '1000', 14, 14),
    ('ВВЭР-1000', '1000', 0, None),
    ('ВВЭР-1000', '1000', 999, None),
    ('ВВЭР-1000', '1000', 15, None),
])
def test_nuclear_group_uses_only_explicit_card_field_not_name_or_power(
        nuclear_reference_groups, name, power, explicit, expected):
    row = runtime_row(1, explicit, fuel='NUCLEAR', technology=None, power=power, first=None, second=None)
    row['values']['L'] = name
    groups = [*nuclear_reference_groups, SimpleNamespace(id=99, name='ТЭЦ<90 ата', id_technology_type=1),
              SimpleNamespace(id=0, name='Не указано', id_technology_type=None),
              SimpleNamespace(id=15, name='Без группы оборудования', id_technology_type=2)]
    powers = [(1, None, 2025, Decimal(power)), (1, None, 2026, Decimal(power) + 1)]
    data = services.equipment_series([row, row], groups, [SimpleNamespace(id=2, name='АЭС')],
                                     powers, [2025, 2026], 2025, 1)
    expected_labels = [group.name for group in nuclear_reference_groups]
    if expected is None:
        expected_labels.append('Без группы оборудования')
    elif expected == 99:
        expected_labels.append('ТЭЦ<90 ата')
    assert [item['group'] for item in data] == expected_labels
    populated = next(item for item in data if item['series']['total'][0])
    assert populated['key'] == (None, 'атом', expected)
    assert populated['series']['total'] == [Decimal(power)] * 2
    assert populated['series']['remaining'] == [Decimal(power), Decimal(power) + 1]
    assert populated['counts']['total'] == populated['counts']['remaining'] == [1, 1]
    assert sum(item['series']['total'][0] for item in data) == Decimal(power)


def test_new_nuclear_aggregate_is_not_grouped_by_first_positive_plan_power(nuclear_reference_groups):
    row = runtime_row(1, None, fuel='NUCLEAR', technology=None, power='0', first=None, second=None)
    row['values']['L'] = 'ВВЭР-оптим'
    powers = [(1, None, 2025, Decimal(0)), (1, None, 2042, Decimal(1200)), (1, None, 2035, Decimal(1200))]
    data = services.equipment_series([row], nuclear_reference_groups, [SimpleNamespace(id=2, name='АЭС')],
                                     powers, [2025, 2035, 2042], 2025, 1)
    group = next(item for item in data if item['key'][2] is None)
    assert group['series']['total'] == [0, 0, 0]
    assert group['series']['remaining'] == [0, 1200, 1200]
    assert group['counts']['remaining'] == [0, 1, 1]
    assert sum(item['series']['remaining'][-1] for item in data) == 1200


def test_nuclear_reference_groups_keep_order_and_zero_rows_without_zone_aggregates(nuclear_reference_groups):
    data = services.equipment_series([], nuclear_reference_groups, [SimpleNamespace(id=2, name='АЭС')],
                                     [], [2025, 2042], 2025, 1)
    assert [item['group'] for item in data] == [group.name for group in nuclear_reference_groups]
    assert all(values == [0, 0] for item in data for metric in ('series', 'counts')
               for values in item[metric].values())


def test_nuclear_uses_card_groups_base_power_and_only_expected_dismantling(nuclear_sources):
    rows, groups, technologies, powers, base = nuclear_sources
    data = services.equipment_series(rows + [rows[0]], groups, technologies, powers,
                                     [2024, 2026, 2027, 2029], base, 1)
    assert [item['technology'] for item in data] == ['АЭС'] * 3
    assert [item['group'] for item in data] == ['РБМК-1000', 'ВВЭР-1200 (1100)', 'Без группы оборудования']
    rbmk = data[0]
    assert rbmk['series']['total'] == [1850, 2000, 2000, 2000]
    assert rbmk['series']['first'] == [0, 0, 0, 0]
    assert rbmk['series']['second'] == [0, 0, 1000, 2000]
    assert rbmk['series']['remaining'] == [1850, 0, 9999, 0]
    assert rbmk['counts']['total'] == [2, 2, 2, 2]
    assert rbmk['counts']['first'] == [0, 0, 0, 0]
    assert rbmk['counts']['second'] == [0, 0, 1, 2]
    assert rbmk['counts']['remaining'] == [2, 0, 1, 0]
    assert rbmk['contributors']['series']['first'] == [[], [], [], []]
    assert len(rbmk['contributors']['series']['second'][-1]) == 2
    national = services.equipment_series(rows, groups, technologies, powers, [2027], base, None)
    assert national[0]['series']['second'] == [1999]
    assert national[0]['series']['remaining'] == [9999]


def test_nuclear_without_group_does_not_merge_with_thermal_other_fuels(nuclear_sources):
    rows, groups, technologies, powers, base = nuclear_sources
    rows.append(runtime_row(200, None, 'MAZUT', technology=None, power='10', first=None, second=None))
    powers.append((200, None, 2025, Decimal(10)))
    rows.append(runtime_row(201, None, 'GAZ', technology=None, power='20', first=None, second=None))
    powers.append((201, None, 2025, Decimal(20)))
    data = services.equipment_series(rows, groups, technologies, powers, [2026], base, 1)
    nuclear = next(item for item in data if item['key'][1:] == ('атом', None))
    assert nuclear['technology'] == 'АЭС'
    assert nuclear['series']['total'] == [5]
    assert next(item for item in data if item['key'][1] == 'прочие')['series']['total'] == [10]


def test_nuclear_sources_use_station_type_and_expected_card_year_not_modernization(calculation_database):
    TechnologyType.__table__.create(db.engine)
    db.session.execute(TechnologyType.__table__.insert(), dict(id=2, name='АЭС', database_version_id=1))
    db.session.execute(StationType.__table__.insert(), dict(id=2, name='АЭС', database_version_id=1))
    db.session.execute(EquipmentGroupType.__table__.insert(), dict(
        id=10, name='РБМК-1000', id_technology_type=2, database_version_id=1))
    for station_id, region, version in ((10, 1, 1), (20, 2, 1), (30, 1, 2)):
        db.session.execute(Station.__table__.insert(), dict(
            id=station_id, name=f'АЭС {station_id}', external_code=f'aes-{station_id}',
            id_station_type=2, id_regional_district=region, database_version_id=version))
        db.session.execute(Machine.__table__.insert(), dict(
            id=station_id * 10, id_station=station_id, machine_number='1',
            machine_name='Реактор', external_code=f'reactor-{station_id}', id_equipment_group=10,
            date_modernization_power_change_expected=2026, date_modernization_no_power_change_expected=2028,
            date_decompressing_expected=2027, relabing_outcome='замена', database_version_id=version))
        db.session.add(MachinePower(id_machine=station_id * 10, year_number=2025,
                                    p_ust=1000, database_version_id=version))
    set_current_year(2025)
    db.session.commit()
    rows, groups, technologies, powers, base = services.load_territory_equipment_sources(1)
    nuclear = [row for row in rows if row['fuel_code'] == 'NUCLEAR']
    assert base == 2025
    assert [row['machine_id'] for row in nuclear] == [100, 200]
    assert [row['station_id'] for row in nuclear] == [10, 20]
    assert [row['energy_zone_id'] for row in nuclear] == [1, 2]
    assert all(row['equipment_group_type_id'] == 10 for row in nuclear)
    assert all(row['values']['AS'] is None and row['values']['BC'] == 2027 for row in nuclear)
    data = services.equipment_series(rows, groups, technologies, powers, [2026, 2027, 2042], base, 1)
    reactor = next(item for item in data if item['key'][1] == 'атом')
    assert reactor['series']['first'] == [0, 0, 0]
    assert reactor['series']['second'] == [0, 1000, 1000]
    assert reactor['series']['remaining'] == [0, 0, 0]


@pytest.mark.parametrize('zone', [1, 0])
def test_nuclear_render_paired_rows_details_resources_and_export(territory_client, nuclear_sources, monkeypatch, zone):
    monkeypatch.setattr(services, 'load_territory_equipment_sources', lambda version: nuclear_sources)
    client, _ = territory_client
    query = dict(energy_zone_id=zone, sheet='equipment', start_year=2025, end_year=2029)
    html = client.get('/rational_structure/territory_inputs', query_string=query).get_data(as_text=True)
    assert 'РБМК-1000, ВВЭР-1000' not in html
    rows = [(attributes, content) for attributes, content in re.findall(r'<tr([^>]*)>(.*?)</tr>', html, re.S)
            if 'data-equipment-verification' not in attributes]
    nuclear_counts = [(index, attributes, content) for index, (attributes, content) in enumerate(rows)
                      if 'data-equipment-count-row' in attributes and 'РБМК-1000' in content]
    assert len(nuclear_counts) == 4
    for index, attributes, content in nuclear_counts:
        assert 'territory-count-hidden' in attributes
        assert '<td>шт</td>' in content and 'bi-info-circle' not in content
        assert 'РБМК-1000' in rows[index + 1][1] and '<td>МВт</td>' in rows[index + 1][1]
        assert 'data-equipment-count-row' not in rows[index + 1][0]
    assert 'aria-label="Состав суммы: РБМК-1000, 2027,' in html
    assert '2027: Станция 100, 100 – Агрегат 100, Руст 1 000 МВт' in re.sub(r'<[^>]+>', '', html)
    assert 'Руст <span title="1 000">1 000</span> МВт' in html
    assert 'name="value_30_' not in html and 'name="note_aes_' not in html
    response = client.get('/rational_structure/territory_inputs/export', query_string=query)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        exported = list(book.active.values)
        first = next(index for index, row in enumerate(exported) if row[1] == 'Первый ресурс')
        second = next(index for index, row in enumerate(exported) if row[1] == 'Второй ресурс')
        assert all(all(value is None for value in row[3:8]) for row in exported[first + 1:second]
                   if row[1] == 'РБМК-1000')
        if zone == 1:
            power = [row[3:8] for row in exported if row[1:3] == ('РБМК-1000', 'МВт')]
            assert power == [(2000, None, 9999, None, None), (None,) * 5, (None, None, 1000, 1000, 2000),
                             (2000, None, 9999, None, None)]
            counts = [row[3:8] for row in exported if row[1:3] == ('РБМК-1000', 'шт')]
            assert counts[-1] == (2, None, 1, None, None)
    finally:
        book.close()
    html = client.get('/rational_structure/territory_inputs', query_string=dict(query, view_year=2027)).get_data(as_text=True)
    assert 'data-year="2027"' in html and 'data-year="2026"' not in html


def test_nuclear_groups_load_referenced_technology_from_another_version(calculation_database):
    TechnologyType.__table__.create(db.engine)
    db.session.execute(TechnologyType.__table__.insert(), dict(id=2, name='АЭС', database_version_id=2))
    db.session.execute(EquipmentGroupType.__table__.insert(), [
        dict(id=10, name='РБМК-1000, ВВЭР-1000', id_technology_type=2, database_version_id=1),
        dict(id=11, name='Чужая атомная группа', id_technology_type=2, database_version_id=2),
    ])
    db.session.commit()
    rows, groups, technologies, powers, year = services.load_territory_equipment_sources(1)
    assert 2 in {technology.id for technology in technologies}
    assert 10 in {group.id for group in groups} and 11 not in {group.id for group in groups}
    data = services.equipment_series(rows, groups, technologies, powers, [2025], year, 1)
    nuclear = [item for item in data if item['key'][1] == 'атом']
    assert [item['group'] for item in nuclear] == ['РБМК-1000, ВВЭР-1000']


@pytest.mark.parametrize('zone', [1, 0])
def test_nuclear_reference_groups_render_in_all_blocks_verification_and_export(
        territory_client, nuclear_sources, nuclear_reference_groups, monkeypatch, zone):
    rows, groups, technologies, powers, base = nuclear_sources
    names = {100: 'РБМК-1000', 101: 'ВВЭР-1000', 102: 'ВВЭР-1200',
             103: 'Неизвестный агрегат', 104: 'ВВЭР-440', 105: 'БН-800'}
    for row in rows:
        row['equipment_group_type_id'] = None
        row['values']['L'] = names[row['machine_id']]
    monkeypatch.setattr(services, 'load_territory_equipment_sources',
                        lambda version: (rows, nuclear_reference_groups, technologies, powers, base))
    context = build_territory_input_context(1, zone, 'equipment')
    services.populate_territory_equipment_rows(context)
    for block in ['equipment_block_0', 'equipment_block_1', 'equipment_block_2', 'equipment_block_3', 'equipment_check']:
        block_rows = context['equipment_verification_rows'] if block == 'equipment_check' else context['rows']
        nuclear = [row for row in block_rows if row['equipment_block'] == block and row['unit'] == 'МВт'
                   and row.get('generation_type') == 'АЭС']
        assert [row['label'] for row in nuclear] == [group.name for group in nuclear_reference_groups] + [
            'Без группы оборудования']
        assert all(Decimal(value or 0) == 0 for row in nuclear[:-1] for value in row['cells'])
    client, _ = territory_client
    query = dict(energy_zone_id=zone, sheet='equipment', start_year=2025, end_year=2029)
    response = client.get('/rational_structure/territory_inputs', query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-equipment-row-key="aes_total_None_атом_None"' in html
    for group in nuclear_reference_groups:
        assert group.name in html
    response = client.get('/rational_structure/territory_inputs/export', query_string=dict(query, equipment_check='1'))
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        labels = [row[1] for row in book.active.values if row[2] == 'МВт']
        for group in nuclear_reference_groups:
            assert labels.count(group.name) == 5
        assert labels.count('Без группы оборудования') == 2 * 5
    finally:
        book.close()


def test_nuclear_original_rows_cannot_be_manually_overwritten(territory_client):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    keys = territory_nuclear_row_keys()
    assert keys == frozenset(str(index) for start in (30, 118, 159, 200) for index in range(start, start + 5))
    context = build_territory_input_context(1, 1, 'equipment')
    form = posted_table(context)
    for key in keys:
        form[f'value_{key}_2025'] = '999'
        response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
            database_version_id=1, energy_zone_id=1, sheet='equipment', row_key=key, year=2025,
            field='value', value='999'))
        assert response.status_code == 400 and 'автоматически' in response.json['error']
    save_territory_inputs(context, form, 'tester')
    saved = db.session.scalar(select(TerritoryInput))
    assert all(saved.rows[int(key)]['values'][0] is None for key in keys)
