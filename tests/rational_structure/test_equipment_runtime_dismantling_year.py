import re
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


@pytest.mark.parametrize('resource,total,commissioning,hours,expected', [
    ('220000', 271341, 1983, 7840, 2046),
    ('270000', 560428, 1932, 3926, 2024),
    ('1000', 1750, None, 100, 2027),
    ('1000', 1950, None, 100, 2025),
    ('1000', 1851, None, 100, 2025),
    ('1000', 1849, None, 100, 2026),
    ('1000', 1750, None, -100, 2021),
    ('1000', 1750, None, 0, 0),
    ('1000', 1750, None, None, 0),
    ('1000', 2000, None, 0, 0),
    ('1000', None, None, 100, 0),
    ('40', None, 2012, 0, 2092),
    ('40', None, 1900, None, 1980),
    ('100', None, 2000, None, 2200),
    ('40,5', None, 2012, None, 2093),
    ('40', None, None, 100, 0),
    (None, 100, 2000, 100, 0),
    ('не задан', 100, 2000, 100, 0),
])
def test_dismantling_year_matches_excel(calculation_database, resource, total, commissioning, hours, expected):
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        standard_service_life=resource, operating_hours_total=total, commissioning_year=commissioning,
        operating_hours_year=hours))
    db.session.commit()
    result = context()
    row = next(row for row in result['rows'] if row['values']['C'] == '002')
    assert row['values']['AP'] == expected
    assert next(row for row in result['rows'] if row['values']['C'] == '003')['values']['AP'] == 0


def test_dismantling_uses_page_average_selected_year_and_version(calculation_database):
    for report_year, hours in ((2022, 7938), (2023, 7905), (2024, 7677), (2025, 7500)):
        db.session.add(EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type='steam', report_year=report_year, database_version_id=1,
            standard_service_life='220000', operating_hours_total=271341, operating_hours_year=hours))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=2,
        standard_service_life='1000', operating_hours_total=100, operating_hours_year=1))
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    for year, average, expected in ((2024, 7840, 2046), (2025, 7694, 2047)):
        result = context(year, column_AP=str(expected))
        assert result['workbook'] is None
        assert result['total'] == 1
        assert result['rows'][0]['values']['C'] == '002'
        assert result['rows'][0]['values']['AN'] == average
        assert result['rows'][0]['values']['AO'] == 168659
        assert result['rows'][0]['values']['AP'] == expected
        restored = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
        assert restored['calculation']['rows'][0]['values']['AP'] == expected
    assert all(row['values']['AP'] == 0 for row in context(2026)['rows'])


def test_dismantling_does_not_use_display_rounding_or_saved_formula(calculation_database):
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], AP='#VALUE!'),
             formulas=dict(row['formulas'], AP='=1/0'), errors=[*row['errors'], 'AP'])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='gas', report_year=2024, database_version_id=1,
        standard_service_life='101', operating_hours_total='200.96', operating_hours_year='0.41'))
    db.session.commit()
    for digits in ('0', '-1', '2', '6'):
        result = context(rounding_digits=digits)
        row = next(row for row in result['rows'] if row['values']['C'] == '002')
        assert row['values']['AP'] == 2027
        assert 'AP' not in row['formulas']
        assert 'AP' not in row['errors']


@pytest.mark.parametrize('year,expected', [(2024, '2046'), (2025, '2092')])
def test_dismantling_page_and_formatted_formula_help(calculation_database, http_client, monkeypatch, year, expected):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    db.session.add_all([
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
            standard_service_life='220000', operating_hours_total=271341, operating_hours_year=7840),
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type='steam', report_year=2025, database_version_id=1,
            standard_service_life='40', commissioning_year=2012),
    ])
    db.session.commit()
    client, _ = http_client
    response = client.get(f'/rational_structure/equipment_runtime?year={year}&column_C=002')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    buttons = re.findall(r'<button\b[^>]*bi-info-circle[^>]*>', headers)
    assert len(buttons) == 18
    for button in buttons:
        assert 'data-bs-html="true"' in button
        assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in button
        content = re.search(r'\btitle="([^"]*)"', button).group(1)
        assert '<p>' not in content
        assert unescape(content).count('<p>') >= 2
        assert '<strong>' in unescape(content)
    dismantling = unescape(buttons[2])
    assert 'Формула: Расчетный год демонтажа по ресурсу' in dismantling
    assert f'{year} + ОКРУГЛ(«Остаток до достижения двойного ресурса, ч/лет» / «Среднегодовая наработка за три года, ч»; 0)' in dismantling
    assert '«Год ввода оборудования в эксплуатацию» + 2 × «Нормативный срок службы (парковый ресурс), лет (ч)»' in dismantling
    assert 'Если «Среднегодовая наработка за три года, ч» = 0' in dismantling
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    index = [key for key, _ in RUNTIME_COLUMNS].index('AP')
    assert re.sub(r'\s+', '', cells[index]) == expected
