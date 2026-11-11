from copy import deepcopy
from decimal import Decimal
from io import BytesIO
import re
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from test_territory_data import database, http_client, territory_client, territory_database, posted_table
from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import machine_sources
from test_equipment_runtime_planned_events import planned_card
from app.extensions import db
from app.rational_structure.models import TerritoryInput
from app.rational_structure.services import territory_equipment_services as services
from app.rational_structure.services.territory_input_services import (
    build_territory_input_context, save_territory_inputs, territory_thermal_row_keys,
)
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType


def runtime_row(machine, group, fuel='GAZ', zone=1, technology=1, power='150', first=2026, second=2030, part=None):
    return dict(station_id=machine, machine_id=machine, pgu_machine_id=part, energy_zone_id=zone,
                technology_type_id=technology, equipment_group_type_id=group, fuel_code=fuel,
                parent_machine_number=str(machine), parent_machine_name=f'Агрегат {machine}',
                values=dict(G=f'Станция {machine}', H=str(part or machine),
                            L=f'Часть ПГУ {part}' if part else f'Агрегат {machine}',
                            N=Decimal(power), AS=first, BC=second))


@pytest.fixture
def sources():
    groups = [SimpleNamespace(id=1, name='Блоки 150К', id_technology_type=1),
              SimpleNamespace(id=2, name='Блоки 150Т (рек)', id_technology_type=1),
              SimpleNamespace(id=3, name='ПГУ-ТЭЦ', id_technology_type=2)]
    technologies = [SimpleNamespace(id=1, name='ТЭС'), SimpleNamespace(id=2, name='Другая технология')]
    rows = [runtime_row(1, 1), runtime_row(2, 2, 'UGOL', power='100', first=0, second=2028),
            runtime_row(3, 3, 'MAZUT', power='10'),
            runtime_row(4, 3, 'TORF', technology=2, power='20'),
            runtime_row(5, 3, zone=2, power='999'),
            runtime_row(6, 3, 'ISK_GAZ', technology=2, power='1.123456789', first=None, second=None)]
    powers = [(row['machine_id'], row['pgu_machine_id'], year, row['values']['N'])
              for row in rows for year in range(2023, 2032)]
    return rows, groups, technologies, powers, 2024


def series(sources, years, zone=1):
    rows, groups, technologies, powers, base = sources
    return services.equipment_series(rows, groups, technologies, powers, years, base, zone)


def test_grouping_merges_reconstructed_blocks_and_combines_other_fuels(sources):
    data = series(sources, [2025, 2026, 2028, 2030])
    assert [(item['technology'], item['group']) for item in data] == [
        ('ТЭС (газ)', 'Блоки 150К'), ('ТЭС (уголь)', 'Блоки 150К'),
        ('Другая технология', 'ПГУ-ТЭЦ'), ('Без типа технологии', 'Без группы оборудования')]
    assert data[-1]['key'] == (None, 'прочие', None)
    assert data[-1]['series']['total'] == [Decimal(30)] * 4
    assert data[2]['series']['total'] == [Decimal('1.123456789')] * 4
    assert data[-1]['counts']['total'] == [2] * 4


@pytest.mark.parametrize('capacity', [150, 200, 300, 500, 800, 1200])
@pytest.mark.parametrize('has_condensing_group', [True, False])
def test_reconstructed_groups_are_always_reported_as_condensing(sources, capacity, has_condensing_group):
    sources[1][0].name = f'Блоки {capacity}К'
    sources[1][1].name = f'Блоки {capacity}Т (рек)'
    sources[0][:] = [runtime_row(1, 2), runtime_row(2, 2)]
    if has_condensing_group:
        sources[0].append(runtime_row(3, 1))
    else:
        sources[1].pop(0)
    data = series(sources, [2026])
    assert len(data) == 1
    assert data[0]['group'] == f'Блоки {capacity}К'
    assert data[0]['counts']['total'] == [len(sources[0])]
    assert data[0]['counts']['first'] == [len(sources[0])]


def test_resources_are_cumulative_without_double_withdrawal_and_independent_of_visible_range(sources):
    data = series(sources, [2025, 2026, 2028, 2030])
    gas, coal = data[:2]
    assert gas['series'] == dict(total=[Decimal(150)] * 4,
                                first=[0, 150, 150, 150], second=[0, 0, 0, 0],
                                remaining=[150, 150, 150, 150])
    assert coal['series']['first'] == [0] * 4
    assert coal['series']['second'] == [0, 0, 100, 100]
    assert series(sources, [2030])[0]['series']['first'] == [150]
    assert series(sources, [2028, 2030])[0]['series']['first'] == [150, 150]
    assert gas['counts'] == dict(total=[1] * 4, first=[0, 1, 1, 1], second=[0, 0, 0, 0],
                                remaining=[1, 1, 1, 1])
    assert coal['counts']['second'] == [0, 0, 1, 1]
    assert series(sources, [2030])[0]['counts']['first'] == [1]


@pytest.mark.parametrize('power', [None, Decimal(0), Decimal(-10)])
def test_only_positive_card_power_counts_and_can_withdraw(sources, power):
    sources[0][:] = [runtime_row(1, 1)]
    sources[3][:] = [(1, None, 2024, power), (1, None, 2026, Decimal(999))]
    data = series(sources, [2024, 2025, 2026, 2030])[0]
    for metric, amount in [('series', 999), ('counts', 1)]:
        for block in ('total', 'first', 'second'):
            assert data[metric][block] == [0] * 4
            assert data['contributors'][metric][block] == [[]] * 4
        assert data[metric]['remaining'] == [0, 0, amount, 0]
        assert data['contributors'][metric]['remaining'][2][0]['power'] == 999


def test_duplicate_inspection_codes_do_not_duplicate_power_and_ees_includes_zones(sources):
    sources[0].append(deepcopy(sources[0][0]))
    assert series(sources, [2026])[0]['series']['first'] == [150]
    assert sum(item['counts']['total'][0] for item in series(sources, [2026])) == 5
    ees = series(sources, [2026], None)
    assert sum(item['series']['total'][0] for item in ees) == Decimal('1280.123456789')
    assert sum(item['counts']['total'][0] for item in ees) == 6


def test_pgu_parts_are_counted_once_each_not_with_parent(sources):
    sources[0][:] = [runtime_row(1, 1, power='60', part=10), runtime_row(1, 1, power='90', part=11)]
    sources[3][:] = [(1, None, 2024, Decimal(150)),
                     (1, 10, 2024, Decimal(60)), (1, 11, 2024, Decimal(90))]
    data = series(sources, [2026])
    assert data[0]['series']['total'] == [150]
    assert data[0]['series']['first'] == [150]
    assert data[0]['counts']['total'] == [2]
    assert data[0]['counts']['first'] == [2]
    total = data[0]['contributors']['series']['total'][0]
    assert [(item['number'], item['name'], item['power']) for item in total] == [
        ('10', 'Часть ПГУ 10', 60), ('11', 'Часть ПГУ 11', 90)]
    for metric in ('series', 'counts'):
        parts = data[0]['contributors'][metric]['first'][0]
        assert [(item['number'], item['name'], item['power']) for item in parts] == [
            ('10', 'Часть ПГУ 10', 60), ('11', 'Часть ПГУ 11', 90)]


def test_composition_reconciles_all_sums_and_remainders_without_duplicate_codes(sources):
    sources[0].append(deepcopy(sources[0][0]))
    sources[3][:] = [(machine, part, year, Decimal(175) if machine == 1 and year == 2026 else power)
                     for machine, part, year, power in sources[3]]
    years = [2025, 2026, 2028, 2030, 2040]
    data = series(sources, years)
    for metric in ('series', 'counts'):
        for block, _ in services.BLOCKS:
            rows = [row for row in services._equipment_rows(data, block, '', metric=metric)
                    if not row['section']]
            for item, row in zip(data, rows):
                for index, components in enumerate(row['cell_details']):
                    actual = sum(component['sign'] * (len(component['aggregates']) if metric == 'counts' else
                                 sum(aggregate['power'] for aggregate in component['aggregates']))
                                 for component in components)
                    assert actual == item[metric][block][index]
                    for component in components:
                        is_initial = block == 'total' or (block == 'remaining' and component['sign'] > 0)
                        for aggregate in component['aggregates']:
                            expected_year = None if is_initial else (2028 if aggregate['station'] == 'Станция 2' else 2026)
                            assert aggregate['year'] == expected_year
                    assert all(aggregate['station'] != 'Станция 5' for component in components
                               for aggregate in component['aggregates'])
    assert data[0]['contributors']['series']['total'][1][0]['power'] == 150
    assert data[0]['contributors']['series']['first'][1][0]['power'] == 150
    assert data[0]['contributors']['series']['total'][-1][0]['power'] == 150
    assert len(data[0]['contributors']['counts']['total'][-1]) == 1


def test_power_and_count_composition_use_cards_not_runtime_power(sources):
    sources[0][0]['values']['N'] = None
    data = series(sources, [2026])[0]
    for metric in ('series', 'counts'):
        assert data['contributors'][metric]['first'][0][0]['power'] == 150
        assert data['contributors'][metric]['first'][0][0]['name'] == 'Агрегат 1'


def test_resources_use_baseline_but_remaining_uses_changed_or_missing_plan_powers(sources):
    rows = [runtime_row(1, 1, power='777', first=2026, second=2030),
            runtime_row(2, 2, first=None, second=2028),
            runtime_row(3, 1, power='999', first=2029, second=None)]
    powers = [(1, None, 2024, Decimal(90)), (2, None, 2024, Decimal(0)),
              (1, None, 2025, Decimal(100)), (2, None, 2025, Decimal(50)),
              (3, None, 2025, Decimal(0)), (1, None, 2026, Decimal(500)),
              (2, None, 2026, Decimal(0)), (3, None, 2026, Decimal(999))]
    years = [2024, 2025, 2026, 2027, 2028, 2042]
    data = services.equipment_series(rows, sources[1], sources[2], powers, years, 2025, 1)[0]
    assert data['series'] == dict(total=[90, 150, 150, 150, 150, 150],
                                 first=[0, 0, 100, 100, 100, 100], second=[0, 0, 0, 0, 50, 50],
                                 remaining=[90, 150, 1499, 0, 0, 0])
    assert data['counts'] == dict(total=[1, 2, 2, 2, 2, 2],
                                 first=[0, 0, 1, 1, 1, 1], second=[0, 0, 0, 0, 1, 1],
                                 remaining=[1, 2, 2, 0, 0, 0])
    filtered = services.equipment_series(rows, sources[1], sources[2], powers, [2042], 2025, 1)[0]
    assert filtered['series']['remaining'] == filtered['counts']['remaining'] == [0]


@pytest.mark.parametrize('calculated,planned', [(2032, 2026), (2032, 2040), (2032, None),
                                                (None, 2026), (0, 2026), (-1, 2026)])
def test_first_resource_uses_calculated_sipr_year_never_planned_year(sources, calculated, planned):
    row = runtime_row(1, 1, first=calculated, second=None)
    row['values']['planned_modernization_year'] = planned
    sources[0][:] = [row]
    years = [2025, 2026, 2031, 2032, 2042]
    data = series(sources, years)[0]
    expected = [int(calculated is not None and calculated > 2024 and year >= calculated) for year in years]
    assert data['series']['first'] == [150 * count for count in expected]
    assert data['counts']['first'] == expected
    for details, included in zip(data['contributors']['series']['first'], expected):
        assert len(details) == included
        if details:
            assert details[0]['year'] == calculated


def test_first_resource_reads_runtime_calculated_sipr_value_for_machine_and_pgu(planned_card):
    from test_equipment_runtime_modernization import set_current_year
    from app.rational_structure.models import EquipmentTechnicalCharacteristic
    from app.refdata.models.years.year_service_model import YearService

    TechnologyType.__table__.create(db.engine)
    parent, card = planned_card
    parent.relabing_outcome = 'не указано'
    card.date_exploitation_expected = 0
    card.date_modernization_power_change_expected = 2026
    card.date_modernization_no_power_change_expected = 2027
    db.session.add_all([
        YearService(database_version_id=1, year_sipr_end=2035),
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='steam', report_year=2024,
                                         database_version_id=1, expected_service_life_year=2030),
    ])
    db.session.commit()
    set_current_year(2024)
    rows, groups, technologies, _, base_year = services.load_territory_equipment_sources(1)
    row = next(row for row in rows if row['machine_id'] == 1)
    assert row['values']['planned_modernization_year'] == 2026
    assert row['values']['AR'] == 2030
    assert row['values']['AS'] == 2036
    assert not row['values']['BC']
    powers = [(row['machine_id'], row['pgu_machine_id'], 2024, Decimal(150))]
    data = services.equipment_series([row], groups, technologies, powers, [2026, 2030, 2034, 2035, 2036, 2042],
                                     base_year, 1)[0]
    assert data['series']['first'] == [0, 0, 0, 0, 150, 150]
    assert data['counts']['first'] == [0, 0, 0, 0, 1, 1]
    assert data['contributors']['series']['first'][-1][0]['year'] == 2036


@pytest.mark.parametrize('first,second,block', [(2026, 2028, 'first'), (2028, 2026, 'second'),
                                               (2026, 2026, 'first'), (None, 2026, 'second'),
                                               (2026, None, 'first'), (2024, 2026, 'second')])
def test_first_future_event_withdraws_each_aggregate_only_once(sources, first, second, block):
    sources[0][:] = [runtime_row(1, 1, first=first, second=second)]
    data = series(sources, [2025, 2026, 2042])[0]
    other = 'second' if block == 'first' else 'first'
    for metric, amount in [('series', 150), ('counts', 1)]:
        assert data[metric][block] == [0, amount, amount]
        assert data[metric][other] == [0, 0, 0]
        assert data[metric]['remaining'] == [amount, amount, 0]


def test_pgu_parts_use_plan_power_only_in_remaining_not_in_resources(sources):
    sources[0][:] = [runtime_row(1, 1, part=10), runtime_row(1, 1, part=11)]
    sources[3][:] = [(1, None, 2024, Decimal(1000)), (1, 10, 2024, Decimal(60)),
                     (1, 11, 2024, None), (1, 11, 2026, Decimal(90))]
    data = series(sources, [2026, 2042])[0]
    assert data['series']['total'] == data['series']['first'] == [60, 60]
    assert data['counts']['total'] == data['counts']['first'] == [1, 1]
    assert data['series']['remaining'] == [90, 0]
    assert data['counts']['remaining'] == [1, 0]


def test_missing_and_past_events_do_not_create_resources(sources):
    sources[0][:] = [runtime_row(1, 1, first=2024, second=None),
                     runtime_row(2, 2, first=0, second=-1)]
    data = series(sources, [2024, 2026, 2030])
    assert all(item[metric]['first'] == [0, 0, 0] and item[metric]['second'] == [0, 0, 0]
               for item in data for metric in ('series', 'counts'))


@pytest.mark.parametrize('zone', [1, 0])
def test_http_four_blocks_with_interleaved_counts_readonly_export_and_year_filter(territory_client, sources, monkeypatch, zone):
    monkeypatch.setattr(services, 'load_territory_equipment_sources', lambda version: sources)
    client, _ = territory_client
    url = f'/rational_structure/territory_inputs?energy_zone_id={zone}&sheet=equipment&start_year=2026&end_year=2030'
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    positions = [html.index(f' {title}</th>') for _, title in services.BLOCKS]
    assert positions == sorted(positions)
    assert all(f'>{title} (шт)</th>' not in html for _, title in services.BLOCKS)
    count_rows = [(attributes, content) for attributes, content in re.findall(r'<tr([^>]*)>(.*?)</tr>', html, re.S)
                  if 'data-equipment-verification' not in attributes]
    for index, (attributes, content) in enumerate(count_rows):
        is_count = 'data-equipment-count-row' in attributes
        assert ('territory-count-hidden' in attributes) == is_count
        if '<td>шт</td>' in content:
            assert is_count
            assert 'bi-info-circle' not in content
            power_attributes, power_content = count_rows[index + 1]
            assert 'data-equipment-count-row' not in power_attributes
            assert '<td>МВт</td>' in power_content
            assert 'bi-info-circle' not in power_content
            assert re.search(r'<th[^>]*>([^<]*)', content).group(1) == re.search(
                r'<th[^>]*>([^<]*)', power_content).group(1)
        if 'equipment-tes_total_' in content:
            assert not is_count
    assert re.search(r'id="territory-equipment-counts"[^>]*aria-pressed="false"[^>]*>\+ шт</button>', html)
    assert html.index('id="territory-empty-rows"') < html.index('id="territory-equipment-counts"')
    for label in ('АЭС', 'ГЭС', 'ВИЭ', 'ТЭС (газ)', 'ТЭС (уголь)'):
        headers = [attributes for attributes, content in count_rows
                   if f'>{label}</th>' in content and 'data-equipment-count-row' not in attributes]
        assert len(headers) == 4
        assert all('territory-subsection' in attributes for attributes in headers)
    for _, title in services.BLOCKS:
        header = next(attributes for attributes, content in count_rows if f' {title}</th>' in content)
        assert 'territory-subsection' not in header
        assert 'data-equipment-count-row' not in header
    for label, child in [('ГЭС', 'ГЭС до 50 МВт'), ('ВИЭ', 'ВЭС')]:
        header_indices = [index for index, (_, content) in enumerate(count_rows) if f'>{label}</th>' in content]
        assert all(f'>{child}' in count_rows[index + 1][1] for index in header_indices)
    assert 'ТЭС (газ)' in html and 'ТЭС (уголь)' in html
    assert 'Блоки 150Т (рек)' not in html
    assert 'name="value_tes_' not in html and 'name="note_tes_' not in html
    assert 'aria-label="Формула: Блоки 150К"' not in ''.join(content for _, content in count_rows)
    indicator_header = re.search(r'<th scope="col" class="territory-label fw-bold">(.*?)</th>', html, re.S).group(1)
    assert indicator_header.startswith('Показатель')
    assert 'aria-label="Фильтр групп оборудования"' in indicator_header
    assert '<th scope="col">Единица<br>измерения</th>' in html
    assert 'ТЭС: фактические годы' not in html
    menu_start = r'Учтенные агрегаты – \d+ год</div>\s*(?:<div class="fw-bold mb-1">[^<]*</div>\s*)?<ul class="territory-equipment-list">'
    assert len(re.findall(menu_start, html)) == html.count('Учтенные агрегаты – ')
    for prefix, value in [('tes_total', '150,0'), ('tes_counts_total', '1')]:
        assert re.search(rf'aria-controls="equipment-{prefix}_1_газ_1-2026".*?>\s*{value}\s*</button>', html, re.S)
    assert '2026: Станция 1, 1 – Агрегат 1, Руст 150 МВт' in re.sub(r'<[^>]+>', '', html)
    assert '+ Всего до проведения мероприятий' not in html
    assert '− Первый ресурс' in html and '− Второй ресурс' in html
    response = client.get(url.replace('territory_inputs?', 'territory_inputs/export?'))
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        exported = list(book.active.values)
        for row in book.active.iter_rows(min_row=3):
            if row[1].value in ('АЭС', 'ГЭС', 'ВИЭ', 'ТЭС (газ)', 'ТЭС (уголь)'):
                assert all(cell.fill.fgColor.rgb[-6:] == 'EFF7FF' for cell in row)
            elif row[1].value in {title for _, title in services.BLOCKS}:
                assert all(cell.fill.fgColor.rgb[-6:] == 'DCE6F1' for cell in row)
        for index, row in enumerate(exported):
            if row[2] == 'шт':
                assert exported[index + 1][1:3] == (row[1], 'МВт')
        assert not any(row[1] == f'{title} (шт)' for row in exported for _, title in services.BLOCKS)
        block = next(i for i, row in enumerate(exported) if row[1] == 'Первый ресурс')
        gas = next(row for row in exported[block + 1:] if row[1:3] == ('Блоки 150К', 'МВт'))
        assert gas[2:8] == ('МВт', 150, 150, 150, 150, 150)
        for (_, title), expected in zip(services.BLOCKS, [(1, 1, 1, 1, 1), (1, 1, 1, 1, 1),
                                                        (None, None, None, None, None),
                                                        (1, 1, 1, 1, 1)]):
            block = next(i for i, row in enumerate(exported) if row[1] == title)
            gas = next(row for row in exported[block + 1:] if row[1:3] == ('Блоки 150К', 'шт'))
            assert gas[2:8] == ('шт', *expected)
        assert not any('Т (рек)' in str(row[1]) for row in exported)
    finally:
        book.close()
    html = client.get(url + '&view_year=2030').get_data(as_text=True)
    assert 'data-year="2026"' not in html and 'data-year="2030"' in html
    assert 'equipment-tes_total_1_газ_1-2026' not in html
    assert 'Станция 1, 1 – Агрегат 1' in re.sub(r'<[^>]+>', '', html)
    assert '2026: Станция 1, 1 – Агрегат 1' in re.sub(r'<[^>]+>', '', html)
    assert '2030: Станция 1, 1 – Агрегат 1' not in re.sub(r'<[^>]+>', '', html)
    assert ('Станция 5' in html) == (zone == 0)
    assert db.session.scalar(select(TerritoryInput)) is None


def test_composition_escapes_names_and_shows_card_power_without_introductory_text(territory_client, sources, monkeypatch):
    row = sources[0][0]
    row['values'].update(G='<script>alert(1)</script>', H='1 & 2', L='<img src=x>', N=None)
    row['parent_machine_name'] = '<img src=x>'
    monkeypatch.setattr(services, 'load_territory_equipment_sources', lambda version: sources)
    client, _ = territory_client
    html = client.get('/rational_structure/territory_inputs', query_string=dict(
        energy_zone_id=1, sheet='equipment', view_year=2026)).get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html and '<img src=x>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert '1 &amp; 2 – &lt;img src=x&gt;' in html
    assert 'Руст <span title="150">150</span> МВт' in html
    assert 'Руст взята из карточек агрегатов' not in html
    assert 'В плановых годах выбывает мощность базового' not in html
    assert 'Ниже показаны слагаемые и вычитаемые агрегаты' not in html
    assert 'Агрегаты без указанной мощности также учитываются в количестве' not in html


@pytest.mark.parametrize('has_base_power', [True, False])
def test_missing_power_warning_uses_sipr_end_not_frozen_plan_year(territory_client, sources, monkeypatch,
                                                               has_base_power):
    from app.refdata.models.years.year_model import Year
    from app.refdata.models.years.year_feature_model import YearFeature

    sources[3][:] = [power for power in sources[3] if power[2] == 2031 and has_base_power]
    monkeypatch.setattr(services, 'load_territory_equipment_sources', lambda version: sources)
    monkeypatch.setattr(services, 'get_current_year_info', lambda version: {'sipr_end': 2031})
    feature = YearFeature(name='план', database_version_id=1)
    db.session.add(feature)
    db.session.flush()
    db.session.scalar(select(Year).where(Year.number == 2042, Year.database_version_id == 1)).id_year_feature = feature.id
    db.session.commit()
    client, _ = territory_client
    html = client.get('/rational_structure/territory_inputs', query_string=dict(
        energy_zone_id=1, sheet='equipment', view_year=2042)).get_data(as_text=True)
    warning = 'Для ТЭС и АЭС нет исходных годовых значений мощности за 2031 гг.'
    assert (warning in html) == (not has_base_power)
    assert 'мощности за 2042 гг.' not in html


def test_calculated_thermal_cells_cannot_be_overwritten(territory_client):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
        database_version_id=1, energy_zone_id=1, sheet='equipment', row_key='37', year=2025,
        field='value', value='999'))
    assert response.status_code == 400 and 'автоматически' in response.json['error']
    context = build_territory_input_context(1, 1, 'equipment')
    form = posted_table(context)
    form['value_37_2025'] = '999'
    save_territory_inputs(context, form, 'tester')
    saved = db.session.scalar(select(TerritoryInput))
    assert saved.rows[37]['values'][0] is None
    assert territory_thermal_row_keys() == frozenset(str(i) for start in (37, 125, 166, 207)
                                                    for i in range(start, start + 31))


def test_sources_use_reference_current_year_even_when_runtime_workbook_is_older(calculation_database):
    from test_equipment_runtime_modernization import set_current_year
    from app.generation.models.machine.machine_power_model import MachinePower

    TechnologyType.__table__.create(db.engine)
    set_current_year(2025)
    set_current_year(2030, version=2)
    db.session.add(MachinePower(id_machine=1, year_number=2025, p_ust=123, database_version_id=1))
    db.session.commit()
    rows, groups, technologies, powers, year = services.load_territory_equipment_sources(1)
    assert year == 2025
    assert rows[0]['values']['D'] == 2024
    assert rows[0]['values']['N'] == 0
    data = services.equipment_series(rows, groups, technologies, powers, [2024, 2025, 2026, 2042], year, 1)
    assert data[0]['series']['total'] == [0, 123, 123, 123]
    assert data[0]['counts']['total'] == [0, 1, 1, 1]


@pytest.mark.parametrize('report_year,current_year,fuel,category', [
    (2024, 2025, 'Уголь', 'уголь'), (2025, 2026, 'Газ природный', 'газ'),
])
def test_fuel_matches_runtime_report_year_while_power_uses_current_year(machine_sources, report_year,
                                                                     current_year, fuel, category):
    from sqlalchemy import delete
    from test_equipment_runtime_modernization import set_current_year
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.generation.models.machine.machine_model import Machine
    from app.generation.models.machine.machine_power_model import MachinePower
    from app.rational_structure.models import EquipmentTechnicalCharacteristic
    from app.rational_structure.services.equipment_runtime_services import build_equipment_runtime_context
    from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType

    TechnologyType.__table__.create(db.engine)
    db.session.execute(TechnologyType.__table__.insert(), {'id': 1, 'name': 'ТЭС', 'database_version_id': 1})
    db.session.get(EquipmentGroupType, 1).id_technology_type = 1
    machine = db.session.get(Machine, 1)
    machine.id_technology_type = 1
    machine.date_modernization_power_change_expected = current_year + 1
    db.session.execute(delete(EquipmentTechnicalCharacteristic).where(
        EquipmentTechnicalCharacteristic.database_version_id == 1,
        EquipmentTechnicalCharacteristic.report_year > report_year))
    db.session.execute(delete(EquipmentGroupFuelParam).where(
        EquipmentGroupFuelParam.database_version_id == 1,
        EquipmentGroupFuelParam.year_number > report_year))
    if current_year == 2025:
        db.session.scalar(select(MachinePower).where(
            MachinePower.database_version_id == 1, MachinePower.id_machine == 1,
            MachinePower.year_number == current_year)).p_ust = 123
    else:
        db.session.add(MachinePower(id_machine=1, year_number=current_year, p_ust=123, database_version_id=1))
    db.session.commit()
    set_current_year(current_year)
    runtime = build_equipment_runtime_context(MultiDict({'per_page': 'all'}), 1)
    assert runtime['selected_year'] == report_year
    runtime_row = next(row for row in runtime['calculation_rows'] if row['machine_id'] == 1)
    assert runtime_row['values']['AM'] == fuel
    rows, groups, technologies, powers, base_year = services.load_territory_equipment_sources(1)
    row = next(row for row in rows if row['machine_id'] == 1)
    assert row['fuel_code'] == runtime_row['fuel_code']
    assert row['values']['AM'] == fuel
    assert (row['values']['AS'], row['values']['BC']) == (
        runtime_row['values']['AS'], runtime_row['values']['BC'])
    assert base_year == current_year
    data = services.equipment_series(rows, groups, technologies, powers,
                                     [current_year, current_year + 1, 2042], base_year, 1)
    item = next(item for item in data if item['key'][1] == category)
    assert item['technology'] == 'ТЭС'
    assert item['group'] == 'Тип группы из карточки'
    assert item['series']['total'] == [123, 123, 123]
    assert item['counts']['total'] == [1, 1, 1]
    assert item['series']['remaining'] == [123, 0, 0]
    assert item['counts']['remaining'] == [1, 0, 0]


def test_sources_load_pgu_card_powers_without_counting_parent(calculation_database):
    from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
    from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower

    TechnologyType.__table__.create(db.engine)
    db.session.execute(PGUMachine.__table__.insert(), {
        'id': 10, 'id_parent_machine': 1, 'machine_number': '1ГТ', 'machine_name': 'ГТ-45',
        'date_modernization_power_change_expected': 2026, 'database_version_id': 1})
    db.session.add_all([
        PGUMachinePower(id_pgu_machine=10, year_number=2024, p_ust=45, database_version_id=1),
        PGUMachinePower(id_pgu_machine=10, year_number=2025, p_ust=90, database_version_id=1),
        PGUMachinePower(id_pgu_machine=10, year_number=2024, p_ust=999, database_version_id=2),
    ])
    db.session.commit()
    rows, groups, technologies, powers, year = services.load_territory_equipment_sources(1)
    data = services.equipment_series(rows, groups, technologies, powers, [2024, 2026, 2042], year, 1)[0]
    assert data['series']['total'] == [45, 45, 45]
    assert data['counts']['total'] == [1, 1, 1]
    assert (1, 10, 2024, Decimal(45)) in powers
    assert data['series']['remaining'] == [45, 0, 0]
    detail = data['contributors']['series']['total'][1][0]
    assert detail['name'] == 'ГТ-45'
    assert (detail['station_id'], detail['machine_id'], detail['pgu_machine_id']) == (1, 1, 10)


def test_real_runtime_sources_use_version_and_zone_metadata(calculation_database):
    TechnologyType.__table__.create(db.engine)
    rows, groups, technologies, powers, year = services.load_territory_equipment_sources(1)
    assert year == 2024
    assert [(row['machine_id'], row['energy_zone_id']) for row in rows] == [(1, 1), (2, 2)]
    assert len(powers) == 2
    assert all(row['parent_machine_number'] for row in rows)
    assert all(row['parent_machine_name'] for row in rows)
    assert services.load_territory_equipment_sources(2)[0] == []
