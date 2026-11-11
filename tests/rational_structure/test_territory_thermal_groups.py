from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from test_territory_data import database, http_client, territory_database, territory_client
from test_territory_equipment import runtime_row, sources, series
from app.rational_structure.services import territory_equipment_services as equipment


@pytest.mark.parametrize('label', ['ТЭЦ<90 ата', 'ТЭЦ-130 ата'])
@pytest.mark.parametrize('fuel', ['GAZ', 'UGOL'])
@pytest.mark.parametrize('has_base', [True, False])
@pytest.mark.parametrize('reverse', [True, False])
def test_r_variants_merge_power_counts_resources_and_contributors(sources, label, fuel, has_base, reverse):
    rows, groups, _, powers, _ = sources
    groups[:] = [SimpleNamespace(id=1, name=label if has_base else f'{label} (р)', id_technology_type=1),
                 SimpleNamespace(id=2, name=f'{label} (Р)', id_technology_type=1)]
    if reverse:
        groups.reverse()
    rows[:] = [runtime_row(1, 1, fuel, first=2026, second=None),
               runtime_row(2, 2, fuel, first=None, second=2028)]
    powers[:] = [(machine, None, year, Decimal(machine * 10))
                 for machine in (1, 2) for year in range(2024, 2029)]
    data = series(sources, [2025, 2026, 2028])
    assert len(data) == 1
    item = data[0]
    assert item['group'] == label
    if has_base:
        assert item['key'][2] == 1
    assert item['series'] == dict(total=[30, 30, 30], first=[0, 10, 10], second=[0, 0, 20], remaining=[30, 30, 30])
    assert item['counts'] == dict(total=[2, 2, 2], first=[0, 1, 1], second=[0, 0, 1], remaining=[2, 2, 2])
    assert [row['machine_id'] for row in item['contributors']['series']['total'][0]] == [1, 2]
    assert item['contributors']['series']['first'][-1][0]['machine_id'] == 1
    assert item['contributors']['series']['second'][-1][0]['machine_id'] == 2


def test_missing_groups_merge_across_technologies_and_placeholder_reference_values(sources):
    rows, groups, _, powers, _ = sources
    groups.extend(SimpleNamespace(id=group_id, name=name, id_technology_type=2) for group_id, name in (
        (0, 'не указано'), (8, 'Не указано'), (9, 'Без группы оборудования'), (10, '')))
    rows[:] = [runtime_row(index, group, technology=1 if index % 2 else 2)
               for index, group in enumerate((None, None, 0, 999, 8, 9, 10), 1)]
    powers[:] = [(row['machine_id'], None, year, Decimal(10)) for row in rows for year in (2024, 2025, 2026)]
    data = series(sources, [2025, 2026])
    assert len(data) == 1
    item = data[0]
    assert item['key'] == (1, 'газ', None)
    assert item['group'] == 'Без группы оборудования'
    assert item['series']['total'] == item['series']['remaining'] == [70, 70]
    assert item['counts']['total'] == [7, 7]
    assert len(item['contributors']['series']['total'][0]) == 7


def test_nuclear_card_groups_are_not_merged_by_r_suffix(sources):
    rows, groups, technologies, powers, _ = sources
    technologies[:] = [SimpleNamespace(id=2, name='АЭС')]
    groups[:] = [SimpleNamespace(id=1, name='Реактор', id_technology_type=2),
                 SimpleNamespace(id=2, name='Реактор (Р)', id_technology_type=2)]
    rows[:] = [runtime_row(1, 1, 'NUCLEAR'), runtime_row(2, 2, 'NUCLEAR')]
    powers[:] = [(machine, None, 2024, Decimal(100)) for machine in (1, 2)]
    data = series(sources, [2025])
    assert [item['group'] for item in data] == ['Реактор', 'Реактор (Р)']
    assert [item['series']['total'] for item in data] == [[100], [100]]


def test_r_variants_render_and_export_as_one_group_in_all_blocks(territory_client, sources, monkeypatch):
    rows, groups = sources[:2]
    groups[0].name = 'ТЭЦ<90 ата'
    groups[1].name = 'ТЭЦ<90 ата (Р)'
    rows[:] = rows[:2]
    rows[1]['fuel_code'] = 'GAZ'
    monkeypatch.setattr(equipment, 'load_territory_equipment_sources', lambda version: sources)
    client, _ = territory_client
    query = dict(energy_zone_id=1, sheet='equipment', start_year=2025, end_year=2028)
    response = client.get('/rational_structure/territory_inputs', query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '(Р)' not in html
    assert html.count('>ТЭЦ&lt;90 ата</th>') == 4 * 2
    response = client.get('/rational_structure/territory_inputs/export', query_string=query)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        exported = list(book.active.values)
        assert sum(row[1] == 'ТЭЦ<90 ата' for row in exported) == 4 * 2
        powers = [row for row in exported if row[1:3] == ('ТЭЦ<90 ата', 'МВт')]
        assert powers[0][3:7] == (250, 250, 250, 250)
        assert not any('(Р)' in str(row[1]) for row in exported)
    finally:
        book.close()
