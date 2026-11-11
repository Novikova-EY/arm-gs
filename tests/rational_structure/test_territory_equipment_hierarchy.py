from decimal import Decimal
from io import BytesIO
import re

import pytest
from openpyxl import load_workbook

from test_territory_data import database, http_client, territory_client, territory_database
from test_territory_equipment import sources
from test_territory_nuclear import nuclear_sources
from app.rational_structure.services import territory_equipment_services as services
from app.rational_structure.services.territory_data_export_services import export_territory_inputs
from app.rational_structure.services.territory_equipment_hierarchy_services import build_equipment_verification_rows
from app.rational_structure.services.territory_input_services import (
    build_territory_input_context, territory_calculated_equipment_row_keys,
)


@pytest.fixture
def hierarchy_context(territory_client, sources, nuclear_sources, monkeypatch):
    mixed = (sources[0] + nuclear_sources[0], sources[1] + nuclear_sources[1], sources[2],
             sources[3] + nuclear_sources[3], 2025)
    monkeypatch.setattr(services, 'load_territory_equipment_sources', lambda version: mixed)
    monkeypatch.setattr(services, 'load_territory_station_types',
                        lambda version: ['ТЭС', 'ГАЭС', 'СЭС', 'АЭС', 'СНЭЭ', 'ГЭС', 'ВЭС'])
    values = {'ГЭС до 50 МВт': 49, 'ГЭС более 50 МВт': 1500, 'ВЭС': 10, 'СЭС': 20, 'ГАЭС': 200, 'СНЭЭ': 50}
    monkeypatch.setattr(services, 'load_territory_station_power_totals',
                        lambda version, zone, years: {label: [Decimal(value)] * len(years) for label, value in values.items()})
    context = build_territory_input_context(1, 1, 'equipment')
    context['years'] = [2024, 2025, 2026, 2027, 2028, 2029]
    for row in context['rows']:
        row['cells'] = [''] * len(context['years'])
    services.populate_territory_equipment_rows(context)
    return context


def test_type_and_block_totals_do_not_double_count_technology_or_count_rows(hierarchy_context):
    rows = hierarchy_context['rows']
    totals = [row for row in rows if row.get('equipment_rollup') == 'block']
    assert len(totals) == 4
    assert all(row['number'] == '18' and row['unit'] == 'МВт' and row['readonly'] for row in totals)
    for total in totals:
        categories = [row for row in rows if row.get('equipment_rollup') == 'type'
                      and row['equipment_block'] == total['equipment_block'] and row['unit'] == 'МВт']
        for index, cell in enumerate(total['cells']):
            assert Decimal(cell or '0') == sum(Decimal(row['cells'][index] or '0') for row in categories)
        for category in categories:
            leaves = [row for row in rows if row.get('equipment_group') == category['equipment_group']
                      and not row.get('equipment_rollup') and row['unit'] == 'МВт']
            if leaves:
                for index, cell in enumerate(category['cells']):
                    assert Decimal(cell or '0') == sum(Decimal(row['cells'][index] or '0') for row in leaves)
    assert totals[0]['cells'][1] == '5315.123456789'
    assert Decimal(totals[1]['cells'][2]) == 180
    assert Decimal(totals[2]['cells'][3]) == 1000
    assert Decimal(totals[2]['cells'][-1]) == 3300


def test_thermal_totals_sum_all_fuels_for_power_and_counts_in_each_block(hierarchy_context):
    rows = hierarchy_context['rows']
    for block_index in range(4):
        block_key = f'equipment_block_{block_index}'
        block = [row for row in rows if row['equipment_block'] == block_key]
        thermal = [row for row in block if row.get('equipment_rollup') == 'thermal']
        assert [row['unit'] for row in thermal] == ['шт', 'МВт']
        for total in thermal:
            assert total['label'] == 'ТЭС'
            assert total['readonly'] and total['virtual'] and total['subsection']
            assert total['equipment_parent'] == block_key
            fuels = [row for row in block if row.get('equipment_rollup') == 'type'
                     and row['label'].startswith('ТЭС (') and row['unit'] == total['unit']]
            assert [row['label'] for row in fuels] == ['ТЭС (газ)', 'ТЭС (уголь)', 'ТЭС (прочие)']
            assert block.index(total) < block.index(fuels[0])
            for index, cell in enumerate(total['cells']):
                assert Decimal(cell or '0') == sum(Decimal(row['cells'][index] or '0') for row in fuels)
    initial = [row for row in rows if row.get('equipment_rollup') == 'thermal'
               and row['equipment_block'] == 'equipment_block_0']
    assert initial[0]['cells'] == ['5'] * 6
    assert initial[1]['cells'] == ['281.123456789'] * 6


def test_reference_order_only_thermal_fuel_split_and_renewable_group(hierarchy_context):
    rows = hierarchy_context['rows']
    for index in range(4):
        block = [row for row in rows if row['equipment_block'] == f'equipment_block_{index}']
        categories = [row for row in block if row.get('equipment_rollup') == 'type' and row['unit'] == 'МВт']
        assert [row['label'] for row in categories] == [
            'ТЭС (газ)', 'ТЭС (уголь)', 'ТЭС (прочие)', 'ГАЭС', 'ВИЭ', 'АЭС', 'СНЭЭ', 'ГЭС']
        renewable = next(row for row in categories if row['label'] == 'ВИЭ')
        children = [row for row in block if row.get('equipment_group') == renewable['equipment_group']
                    and not row.get('equipment_rollup')]
        assert [row['label'] for row in children] == ['СЭС', 'ВЭС']
        assert not any('Другая технология' == row['label'] for row in block)
        for label, power in [('ГАЭС', 200), ('СНЭЭ', 50)]:
            storage = next(row for row in categories if row['label'] == label)
            assert [Decimal(cell or '0') for cell in storage['cells']] == [power if index in (0, 3) else 0] * 6


@pytest.mark.parametrize('years', [[2024, 2025, 2026, 2042], [2026, 2042], [2042]])
@pytest.mark.parametrize('zone', [1, 0])
def test_initial_plan_columns_repeat_sipr_end_for_every_row(
        hierarchy_context, monkeypatch, years, zone):
    values = {'ГЭС до 50 МВт': 49, 'ГЭС более 50 МВт': 1500, 'ВЭС': 10,
              'СЭС': 20, 'ГАЭС': 200, 'СНЭЭ': 0}
    monkeypatch.setattr(services, 'load_territory_station_power_totals',
                        lambda version, zone_id, source_years: {
                            label: [Decimal(value + year - 2025) for year in source_years]
                            for label, value in values.items()})

    monkeypatch.setattr(services, 'get_current_year_info', lambda version: {'sipr_end': 2030})

    def context_for(selected_years):
        context = build_territory_input_context(1, zone, 'equipment')
        context['years'] = selected_years
        context['year_features'] = {year: 'план' for year in selected_years if year >= 2026}
        for row in context['rows']:
            row['cells'] = [''] * len(selected_years)
        services.populate_territory_equipment_rows(context)
        return context

    reference = context_for([2024, 2025, 2026, 2030])
    expected = {row['key']: row['cells'] for row in reference['rows']
                if row['equipment_block'] == 'equipment_block_0'}
    context = context_for(years)
    initial = [row for row in context['rows'] if row['equipment_block'] == 'equipment_block_0']
    assert {row['key'] for row in initial} == set(expected)
    for row in initial:
        assert row['cells'] == [expected[row['key']][[2024, 2025, 2026, 2030].index(min(year, 2030))]
                                for year in years]
    storage = next(row for row in context['rows']
                   if row['equipment_block'] == 'equipment_block_3' and row['label'] == 'ГАЭС')
    assert storage['cells'] == [str(200 + year - 2025) for year in years]

    book = load_workbook(export_territory_inputs(context))
    try:
        for index, row in enumerate(initial, 3):
            exported = [book.active.cell(index, column).value for column in range(4, 4 + len(years))]
            assert exported == [float(value) if value else None for value in row['cells']]
    finally:
        book.close()


def test_resource_detail_years_are_event_years_and_initial_details_have_no_year(hierarchy_context):
    rows = hierarchy_context['rows']
    initial = next(row for row in rows if row['key'] == 'tes_total_1_газ_1')
    assert all(aggregate['year'] is None for details in initial['cell_details']
               for component in details for aggregate in component['aggregates'])
    first = next(row for row in rows if row['key'] == 'tes_first_1_газ_1')
    assert {aggregate['year'] for details in first['cell_details']
            for component in details for aggregate in component['aggregates']} == {2026}
    second = next(row for row in rows if row['key'] == 'aes_second_None_атом_10')
    assert {aggregate['year'] for component in second['cell_details'][-1]
            for aggregate in component['aggregates']} == {2027, 2029}
    remaining = next(row for row in rows if row['key'] == 'tes_remaining_1_газ_1')
    assert [(component['sign'], component['aggregates'][0]['year'])
            for component in remaining['cell_details'][-1]] == [(1, None)]


def test_four_expanded_block_controls_numeric_totals_and_excel_outline(territory_client, hierarchy_context):
    client, _ = territory_client
    query = dict(energy_zone_id=1, sheet='equipment', start_year=2025, end_year=2029)
    html = client.get('/rational_structure/territory_inputs', query_string=query).get_data(as_text=True)
    assert len(re.findall(r'data-transfer-toggle="equipment_block_\d" aria-expanded="true"', html)) == 4
    assert 'data-transfer-parent="equipment_block_0"' in html
    assert html.count('data-equipment-rollup="block"') == 4
    thermal_rows = [content for attributes, content in re.findall(r'<tr([^>]*)>(.*?)</tr>', html, re.S)
                    if 'data-equipment-rollup="thermal"' in attributes]
    assert len(thermal_rows) == 8
    assert all('>ТЭС</th>' in content for content in thermal_rows)
    assert '<td>шт</td>' in thermal_rows[0]
    assert '<td>МВт</td>' in thermal_rows[1] and '281,1' in thermal_rows[1]
    assert 'name="value_' not in ''.join(thermal_rows)
    assert '5 315,1' in html
    text = re.sub(r'<[^>]+>', '', html)
    assert 'Станция 1, 1 – Агрегат 1' in text
    assert '2026: Станция 1, 1 – Агрегат 1' in text
    assert '2029: Станция 1, 1 – Агрегат 1' not in text
    assert '2027: Станция 100, 100 – Агрегат 100' in text
    assert '2029: Станция 100, 100 – Агрегат 100' not in text
    response = client.get('/rational_structure/territory_inputs/export', query_string=query)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        sheet = book.active
        assert sheet.sheet_properties.outlinePr.summaryBelow is False
        root_indices = [index for index in range(3, sheet.max_row + 1) if sheet.cell(index, 1).value == '18']
        assert len(root_indices) == 4
        assert sheet.cell(root_indices[0], 4).value == pytest.approx(5315.123456789)
        thermal_indices = [index for index in range(3, sheet.max_row + 1)
                           if sheet.cell(index, 2).value == 'ТЭС']
        assert len(thermal_indices) == 8
        assert sheet.cell(thermal_indices[0], 3).value == 'шт'
        assert sheet.cell(thermal_indices[0], 4).value == 5
        assert sheet.cell(thermal_indices[1], 3).value == 'МВт'
        assert sheet.cell(thermal_indices[1], 4).value == pytest.approx(281.123456789)
        for index in root_indices:
            assert sheet.row_dimensions[index].outlineLevel == 0
            assert sheet.row_dimensions[index + 1].outlineLevel == 1
            assert not sheet.row_dimensions[index + 1].hidden
    finally:
        book.close()


def test_verification_matches_every_row_with_exact_signed_difference(hierarchy_context):
    context = hierarchy_context
    sources = {row['key']: row for row in context['rows']}
    checks = context['equipment_verification_rows']
    initial = [row for row in context['rows'] if row['equipment_block'] == 'equipment_block_0']
    assert len(checks) == len(initial)
    assert checks[0]['label'] == 'Проверка'
    assert [row['equipment_identity'] for row in checks] == [row['equipment_identity'] for row in initial]
    assert any(any(row['verification_errors']) for row in checks)
    for check in checks:
        assert check['readonly'] and check['virtual'] and not check['cell_details']
        operands = [sources[key] for key in check['verification_sources']]
        assert [row['equipment_block'] for row in operands] == [f'equipment_block_{index}' for index in range(4)]
        assert all(row['equipment_identity'] == check['equipment_identity'] for row in operands)
        for index, cell in enumerate(check['cells']):
            expected = Decimal(operands[0]['cells'][index] or '0') - sum(
                Decimal(row['cells'][index] or '0') for row in operands[1:])
            assert Decimal(cell) == expected
            assert check['verification_errors'][index] == (expected != 0)
    for check in checks:
        before, first, second, after = [sources[key] for key in check['verification_sources']]
        after['cells'] = [str(Decimal(total or '0') - Decimal(one or '0') - Decimal(two or '0'))
                          for total, one, two in zip(before['cells'], first['cells'], second['cells'])]
    balanced = build_equipment_verification_rows(context['rows'], context['years'])
    assert all(Decimal(cell) == 0 for row in balanced for cell in row['cells'])
    assert not any(any(row['verification_errors']) for row in balanced)


@pytest.mark.parametrize('zone', [1, 0])
def test_verification_button_hidden_rows_red_errors_and_opt_in_export(territory_client, hierarchy_context, zone):
    client, _ = territory_client
    query = dict(energy_zone_id=zone, sheet='equipment', start_year=2025, end_year=2029, rounding_digits=1)
    response = client.get('/rational_structure/territory_inputs', query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.index('id="territory-rounding"') < html.index('id="territory-equipment-verification"')
    assert html.index('id="territory-equipment-verification"') < html.index('data-territory-export') < html.index('<thead')
    assert re.search(r'id="territory-equipment-verification"[^>]*btn-outline-info[^>]*aria-pressed="false"', html)
    checks = [(attributes, content) for attributes, content in re.findall(r'<tr([^>]*)>(.*?)</tr>', html, re.S)
              if 'data-equipment-verification' in attributes]
    assert checks and all('territory-verification-hidden' in attributes for attributes, _ in checks)
    assert 'data-transfer-toggle="equipment_check" aria-expanded="true"' in checks[0][1]
    assert 'aria-label="Свернуть: Проверка"' in checks[0][1]
    assert 'data-transfer-parent' not in checks[0][0]
    assert all('data-transfer-parent="equipment_check"' in attributes for attributes, _ in checks[1:])
    assert any('territory-verification-error' in content for _, content in checks)
    assert any('data-raw-value="0" title="0">0,0</td>' in content for _, content in checks)
    assert all('name="value_' not in content and 'name="note_' not in content for _, content in checks)
    assert html.index('data-equipment-verification') > html.rindex('data-equipment-row-key=')
    for enabled in (False, True):
        export_query = dict(query, equipment_check='1' if enabled else '0')
        response = client.get('/rational_structure/territory_inputs/export', query_string=export_query)
        assert response.status_code == 200
        book = load_workbook(BytesIO(response.data))
        try:
            rows = list(book.active.iter_rows(min_row=3))
            roots = [index for index, row in enumerate(rows) if row[1].value == 'Проверка']
            assert bool(roots) == enabled
            if enabled:
                check_cells = [cell for row in rows[roots[0]:] for cell in row[3:-1]]
                assert any(cell.value != 0 and cell.fill.fgColor.rgb == '00F8D7DA' for cell in check_cells)
                assert all(cell.fill.fgColor.rgb != '00F8D7DA' for cell in check_cells if cell.value == 0)
        finally:
            book.close()
    years_html = client.get('/rational_structure/territory_inputs?energy_zone_id=1').get_data(as_text=True)
    assert 'territory-equipment-verification' not in years_html


def test_group_filter_marks_only_equipment_groups_in_all_blocks_and_verification(territory_client, hierarchy_context):
    client, _ = territory_client
    html = client.get('/rational_structure/territory_inputs', query_string=dict(
        energy_zone_id=1, sheet='equipment', start_year=2025, end_year=2029)).get_data(as_text=True)
    assert 'data-equipment-filter-toggle' in html
    attributes = re.findall(r'<tr([^>]*)>', html)
    expected_rows = hierarchy_context['rows'] + hierarchy_context['equipment_verification_rows']
    assert len(attributes) == len(expected_rows) + 1
    for attrs, row in zip(attributes[1:], expected_rows):
        identity = row['equipment_identity']
        is_group = identity[0] in ('tes', 'aes') and identity[3] is not None
        assert ('data-equipment-filter-group=' in attrs) == is_group
        if is_group:
            assert f'data-equipment-filter-group="{identity[3]}"' in attrs
            assert 'data-equipment-filter-label=' in attrs
    years_html = client.get('/rational_structure/territory_inputs?energy_zone_id=1').get_data(as_text=True)
    assert 'data-equipment-filter-toggle' not in years_html


def test_original_block_totals_are_protected_from_manual_values(territory_client):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    assert {'29', '117', '158', '199'} <= territory_calculated_equipment_row_keys()
    for key in ('29', '117', '158', '199'):
        response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
            database_version_id=1, energy_zone_id=1, sheet='equipment', row_key=key,
            field='value', year=2025, value='999'))
        assert response.status_code == 400
