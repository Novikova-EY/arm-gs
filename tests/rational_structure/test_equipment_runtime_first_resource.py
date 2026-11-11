import re
from decimal import Decimal
from html import unescape

import pytest
from flask.templating import render_template
from sqlalchemy import delete, select

from test_calculation_pages import calculation_database
from test_equipment_runtime_double_resource import context
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook


@pytest.mark.parametrize('resource,total,commissioning,hours,expected_year,expected', [
    ('220000', 211670, 1983, Decimal('7229.333333'), None, 2025),
    ('220000', 49438, None, Decimal('4599.666667'), None, 2061),
    ('220000', 271341, 1983, 7840, 2025, 0),
    ('1000', 1000, None, 100, 2050, 0),
    ('1000', 750, None, 100, None, 2027),
    ('1000', 950, None, 100, None, 2025),
    ('1000', 851, None, 100, None, 2025),
    ('1000', 849, None, 100, None, 2026),
    ('1000', 750, None, -100, None, 2021),
    ('1000', 0, None, 100, None, 2034),
    ('40', None, 2012, 100, 2099, 2052),
    ('100', None, 2000, 100, None, 2100),
    ('100.5', 50.5, None, 100, None, 2025),
    ('40,5', None, 2012, 100, None, Decimal('2052.5')),
    ('1 000,5', Decimal('750.5'), None, 100, None, 2027),
    ('1000', 1000, None, 0, 2050, 2050),
    ('40', None, 2012, None, 2099, 2099),
    (None, None, None, 0, 2050, 2050),
    ('не задан', None, None, 0, 0, 0),
    ('1000', 900, None, 0, None, None),
    ('40', None, 2012, 0, None, None),
    (None, 100, 2000, 100, 2050, None),
    ('NaN', 100, 2000, 100, 2050, None),
    ('не задан', 100, 2000, 100, 2050, None),
    ('1000', None, 2000, 100, 2050, None),
    ('40', 100, None, 100, 2050, None),
])
def test_first_resource_matches_excel_branches(calculation_database, resource, total, commissioning,
                                              hours, expected_year, expected):
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        standard_service_life=resource, operating_hours_total=total, commissioning_year=commissioning,
        operating_hours_year=hours, expected_service_life_year=expected_year))
    db.session.commit()
    rows = context()['rows']
    assert next(row for row in rows if row['values']['C'] == '002')['values']['AQ'] == expected
    assert next(row for row in rows if row['values']['C'] == '003')['values']['AQ'] is None


def test_first_resource_uses_page_average_year_version_and_code_without_workbook(calculation_database):
    for code, kind, report_year, version, resource, total, commissioning, hours, expected in [
        ('002', 'steam', 2022, 1, None, None, None, 100, None),
        ('002', 'steam', 2023, 1, None, None, None, 200, None),
        ('002', 'steam', 2024, 1, '1000', 500, None, 0, 2099),
        ('002', 'gas', 2025, 1, '40', None, 2012, 100, None),
        ('002', 'gas', 2028, 1, None, None, None, 0, 2060),
        ('002', 'steam', 2024, 2, '2000', 100, None, 100, 2070),
        ('003', 'steam', 2024, 1, '1000', 900, None, 0, 2080),
        ('002', 'boiler_energy', 2024, 1, '1000', 900, None, 100, 2075),
    ]:
        db.session.add(EquipmentTechnicalCharacteristic(
            equipment_code=code, equipment_type=kind, report_year=report_year, database_version_id=version,
            standard_service_life=resource, operating_hours_total=total, commissioning_year=commissioning,
            operating_hours_year=hours, expected_service_life_year=expected))
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    for year, expected in ((2024, 2027), (2025, 2052), (2028, 2060)):
        result = context(year, column_AQ=str(expected))
        assert result['workbook'] is None
        assert result['total'] == 1
        assert result['rows'][0]['values']['C'] == '002'
        assert result['rows'][0]['values']['AQ'] == expected
        restored = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
        assert restored['calculation']['rows'][0]['values']['AQ'] == expected
    assert all(row['values']['AQ'] is None for row in context(2029)['rows'])


def test_first_resource_replaces_saved_formula_and_ignores_display_rounding(calculation_database):
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], AQ='#VALUE!'),
             formulas=dict(row['formulas'], AQ='=1/0'), errors=[*row['errors'], 'AQ'])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='gas', report_year=2024, database_version_id=1,
        standard_service_life='101', operating_hours_total='99.96', operating_hours_year='0.41'))
    db.session.commit()
    for digits in ('0', '-1', '2', '6'):
        rows = context(rounding_digits=digits)['rows']
        assert next(row for row in rows if row['values']['C'] == '002')['values']['AQ'] == 2027
        for row in rows:
            assert 'AQ' not in row['formulas']
            assert 'AQ' not in row['errors']


def test_first_resource_does_not_choose_ambiguous_characteristic(calculation_database):
    for kind in ('steam', 'gas'):
        db.session.add(EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type=kind, report_year=2024, database_version_id=1,
            operating_hours_year=0, expected_service_life_year=2050))
    db.session.commit()
    assert next(row for row in context()['rows'] if row['values']['C'] == '002')['values']['AQ'] is None


@pytest.mark.parametrize('year,expected', [(2024, '2025'), (2025, '2052'), (2028, '2060'), (2029, '–')])
def test_first_resource_page_and_formatted_help(calculation_database, http_client, monkeypatch, year, expected):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    db.session.add_all([
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
            standard_service_life='220000', operating_hours_total=211670, operating_hours_year=7229),
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type='steam', report_year=2025, database_version_id=1,
            standard_service_life='40', commissioning_year=2012),
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type='steam', report_year=2028, database_version_id=1,
            expected_service_life_year=2060),
    ])
    db.session.commit()
    client, _ = http_client
    response = client.get(f'/rational_structure/equipment_runtime?year={year}&column_C=002')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    button = re.search(r'<button\b[^>]*aria-label="Формула: Год достижения первого нормативного ресурса"[^>]*>', headers).group()
    assert 'data-bs-html="true"' in button
    assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in button
    content = unescape(re.search(r'\btitle="([^"]*)"', button).group(1))
    assert content.count('<p>') >= 4
    assert '<strong>' in content
    assert 'Если «Среднегодовая наработка за три года, ч» = 0' in content
    assert f'{year} + ОКРУГЛ((«Нормативный срок службы (парковый ресурс), лет (ч)» − «Наработка с начала эксплуатации, ч») / «Среднегодовая наработка за три года, ч»; 0)' in content
    assert '«Год ввода оборудования в эксплуатацию» + «Нормативный срок службы (парковый ресурс), лет (ч)»' in content
    assert 'Иначе – 0' in content
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    index = [key for key, _ in RUNTIME_COLUMNS].index('AQ')
    assert re.sub(r'\s+', '', cells[index]) == expected
