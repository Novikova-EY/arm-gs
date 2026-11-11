import re
from html import unescape
from types import SimpleNamespace

import pytest
from flask.templating import render_template
from sqlalchemy import delete, select

from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import context, machine_sources
from test_equipment_runtime_modernization import set_current_year
from test_equipment_runtime_planned_events import planned_card
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_machine_services import (
    _dismantling_without_modernization, _exceeded_double_resources,
)
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook
from app.refdata.models.years.year_service_model import YearService


@pytest.mark.parametrize('modernization,dismantling,total,sipr,expected', [
    (2032, 2032, 2040, 2032, 2040),
    (2033, 2033, 2040, 2032, 0),
    (2032, 2033, 2040, 2032, 2040),
    (2033, 2032, 2040, 2032, 2040),
    (2031, 2032, 2040, 2032, 2040),
    (2032, 2031, 2040, 2032, 2040),
    (2031.5, 2031.5, 2040, 2032, 2040),
    (2038, 2038, 2045, 2038, 2045),
    (2037, 2038, 2045, 2038, 2045),
    (2040, 2037, 2045, 2038, 2045),
    (2038, 2038, None, 2038, None),
    (2039, 2039, None, 2038, 0),
    (None, 2035, 2040, 2032, 2040),
    (0, 2035, 2035, 2032, 2035),
    (0, 2040, 2035, 2032, 2040),
    (0, 2035, 0, 2032, 2035),
    (2040, 0, None, None, 0),
    (2040, -1, None, None, -1),
    (2040, None, 2045, 2038, None),
    (2040, '#N/A', 2045, 2038, None),
    (2040, 2035, 2045, None, None),
    (0, 2035, 2045, None, 2045),
    (None, 2035, None, 2038, None),
])
def test_dismantling_excludes_overlap_before_applying_original_year(
        modernization, dismantling, total, sipr, expected):
    values = {'AS': modernization, 'BA': dismantling, 'AY': total}
    assert _dismantling_without_modernization(values, sipr) == expected


@pytest.mark.parametrize('coal,commissioning,resource,hours,year,expected', [
    (True, 1954, '35', 0, 2024, ('yes', 'yes')),
    (True, 1955, '35', 0, 2024, ('no', 'no')),
    (True, 1955, '35', 0, 2025, ('yes', 'yes')),
    (True, 1954, '200000', 400000, 2024, ('yes', 'no')),
    (False, 1954, '200000', 400000, 2024, ('no', 'yes')),
    (False, 1954, '200000', 399999, 2024, ('no', 'no')),
    (False, 1954, '200000', 400001, 2024, ('no', 'yes')),
    (False, 1984, '20', None, 2024, ('no', 'yes')),
    (False, 1985, '20', None, 2024, ('no', 'no')),
    (False, 1985, '20', None, 2025, ('no', 'yes')),
    (False, 1824, '100', None, 2024, ('no', 'yes')),
    (False, 1824, '100.5', 200, 2024, ('no', 'no')),
    (False, 1824, '100.5', 201, 2024, ('no', 'yes')),
    (False, 1984, '20,5', None, 2024, ('no', 'no')),
    (False, 1984, '20,5', None, 2025, ('no', 'yes')),
    (False, 1980, '0', None, 2024, ('no', 'yes')),
    (True, 1954, None, None, 2024, ('yes', None)),
    (False, None, '200000', 400000, 2024, ('no', 'yes')),
    (True, None, '200000', None, 2024, (None, 'no')),
    (False, None, '20', None, 2024, ('no', None)),
    (False, 1954, '200000', None, 2024, ('no', None)),
    (None, 1954, '200000', 400000, 2024, (None, None)),
    (None, 1954, '35', None, 2024, (None, 'yes')),
    (True, 1954, '#VALUE!', None, 2024, ('yes', None)),
])
def test_double_resource_flags_keep_excel_units_fuel_rules_and_inclusive_boundaries(
        coal, commissioning, resource, hours, year, expected):
    characteristic = SimpleNamespace(
        commissioning_year=commissioning, standard_service_life=resource, operating_hours_total=hours)
    result = _exceeded_double_resources(characteristic, coal, year)
    assert (result['BD'], result['BF']) == expected


@pytest.mark.parametrize('coal,expected', [(True, (None, None)), (False, ('no', None)), (None, (None, None))])
def test_missing_characteristic_does_not_invent_a_resource(coal, expected):
    result = _exceeded_double_resources(None, coal, 2024)
    assert (result['BD'], result['BF']) == expected


def test_live_checks_replace_saved_values_and_follow_selected_year_and_reference_version(machine_sources):
    set_current_year(2030)
    db.session.add_all([
        YearService(database_version_id=1, year_sipr_end=2038),
        YearService(database_version_id=2, year_sipr_end=2099),
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='steam', report_year=2024,
                                         commissioning_year=2000, standard_service_life='100', database_version_id=2),
    ])
    machine = db.session.get(Machine, 1)
    machine.date_modernization_power_change_expected = 2040
    characteristics = {row.report_year: row for row in db.session.scalars(select(
        EquipmentTechnicalCharacteristic).where(EquipmentTechnicalCharacteristic.database_version_id == 1))}
    characteristics[2024].commissioning_year = 1954
    characteristics[2024].standard_service_life = '35'
    characteristics[2025].commissioning_year = 1985
    characteristics[2025].standard_service_life = '20'
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    keys = ('BC', 'BD', 'BF')
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], BA=2039, **dict.fromkeys(keys, '#VALUE!')),
             formulas=dict(row['formulas'], **dict.fromkeys(keys, '=1/0')), errors=[*row['errors'], *keys])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()
    result = context(column_BC='2039', column_BD='yes', column_BF='yes')
    assert result['total'] == 1
    row = result['rows'][0]
    assert row['values']['C'] == '002'
    assert row['values']['AY'] == 2039
    assert not set(keys) & set(row['errors'])
    assert not set(keys) & set(row['formulas'])
    exported = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert tuple(exported['calculation']['rows'][0]['values'][key] for key in keys) == (2039, 'yes', 'yes')
    service = db.session.scalar(select(YearService).where(YearService.database_version_id == 1))
    service.year_sipr_end = 2042
    db.session.commit()
    assert context(column_BC='2043')['total'] == 1
    assert context(2025, column_BD='no', column_BF='yes')['total'] == 1
    assert context(version=2)['rows'] == []
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    row = next(row for row in context()['rows'] if row['values']['C'] == '002')
    assert tuple(row['values'][key] for key in keys) == (2043, 'yes', 'yes')


def test_component_characteristic_is_used_instead_of_parent(planned_card):
    parent, card = planned_card
    card.date_modernization_power_change_expected = 2039
    parent.relabing_outcome = 'окончательный вывод'
    card.date_decompressing_expected = 2040
    db.session.add_all([
        YearService(database_version_id=1, year_sipr_end=2038),
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='gas', report_year=2024,
                                         commissioning_year=1984, standard_service_life='20', database_version_id=1),
    ])
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], BA=2040)) for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()
    row = next(row for row in context()['rows'] if row['machine_id'] == parent.id)
    assert row['values']['planned_modernization_year'] == 2039
    assert row['values']['AS'] is None
    assert row['values']['BC'] == 2040
    assert row['values']['BF'] == 'yes'


def test_new_headers_have_formatted_help_and_preserve_zero_and_missing_values(machine_sources, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    db.session.add(YearService(database_version_id=1, year_sipr_end=2038))
    db.session.commit()
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime?year=2025&column_C=002')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    for key, terms in (
            ('BC', ('2039 − 1', '«Расчетный год модернизации с учетом СиПР»', '«Год демонтажа с учетом СиПР»', '«Базовый год демонтажа»')),
            ('BD', ('«Год ввода оборудования в эксплуатацию» + 70', '2025', '«Основной вид топлива»')),
            ('BF', ('«Наработка с начала эксплуатации, ч» ≥ 2 ×', '«Год ввода оборудования в эксплуатацию» + 2 ×', '2025'))):
        label = dict(RUNTIME_COLUMNS)[key]
        button = re.search(r'<button\b[^>]*aria-label="Формула: ' + re.escape(label) + r'"[^>]*>', headers).group()
        assert 'data-bs-html="true"' in button
        assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in button
        text = unescape(re.search(r'\btitle="([^"]*)"', button).group(1))
        assert text.count('<p>') >= 2 and '<strong>' in text
        assert all(term in text for term in terms)
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    columns = [key for key, _ in RUNTIME_COLUMNS]
    assert cells[columns.index('BC')].strip() == '0'
    assert cells[columns.index('BD')].strip() == 'no'
    assert cells[columns.index('BF')].strip() == '–'
