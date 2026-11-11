import re
from decimal import Decimal

import pytest
from flask.templating import render_template
from sqlalchemy import delete, select
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import (
    build_equipment_runtime_context, read_equipment_runtime_workbook,
)


def context(year=2024, **filters):
    return build_equipment_runtime_context(MultiDict(dict(year=str(year), per_page='all', **filters)), 1)


@pytest.mark.parametrize('resource,total,commissioning,expected', [
    ('220000', 271341, 1983, Decimal('168659')),
    ('270000', 560428, None, 0),
    ('220000', 440000, None, 0),
    ('220000', 0, None, Decimal('440000')),
    ('220 000,5', Decimal('271341.25'), None, Decimal('168659.75')),
    ('40', 84396, 2012, Decimal('68')),
    ('40', None, 1900, Decimal('-44')),
    ('100', None, 2000, Decimal('176')),
    ('100.5', 150, None, Decimal('51')),
    ('40,5', None, 2012, Decimal('69')),
    (None, 100, 2000, None),
    ('', 100, 2000, None),
    ('нет данных', 100, 2000, None),
    ('NaN', 100, 2000, None),
    ('220000', None, 2000, None),
    ('40', 100, None, None),
])
@pytest.mark.parametrize('equipment_type', ['steam', 'gas'])
def test_double_resource_branches_and_missing_inputs(calculation_database, resource, total, commissioning,
                                                     expected, equipment_type):
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type=equipment_type, report_year=2024, database_version_id=1,
        standard_service_life=resource, operating_hours_total=total, commissioning_year=commissioning))
    db.session.commit()
    result = context()
    row = next(row for row in result['rows'] if row['values']['C'] == '002')
    assert row['values']['AO'] == expected
    assert next(row for row in result['rows'] if row['values']['C'] == '003')['values']['AO'] is None


def test_double_resource_uses_exact_year_code_and_version_without_workbook(calculation_database):
    for code, kind, year, version, resource, total, commissioning in [
        ('002', 'steam', 2024, 1, '220000', 271341, 1983),
        ('002', 'gas', 2025, 1, '40', None, 2012),
        ('002', 'steam', 2024, 2, '1000', 100, None),
        ('003', 'steam', 2024, 1, '2000', 100, None),
        ('002', 'boiler_energy', 2024, 1, '3000', 100, None),
    ]:
        db.session.add(EquipmentTechnicalCharacteristic(
            equipment_code=code, equipment_type=kind, report_year=year, database_version_id=version,
            standard_service_life=resource, operating_hours_total=total, commissioning_year=commissioning))
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    result = context(column_AO='168659')
    assert result['workbook'] is None
    assert result['total'] == 1
    assert result['rows'][0]['values']['C'] == '002'
    exported = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert exported['calculation']['rows'][0]['values']['AO'] == 168659
    assert next(row for row in context(2025)['rows'] if row['values']['C'] == '002')['values']['AO'] == 67
    assert all(row['values']['AO'] is None for row in context(2026)['rows'])


def test_double_resource_does_not_choose_between_ambiguous_records(calculation_database):
    for kind in ('steam', 'gas'):
        db.session.add(EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type=kind, report_year=2024, database_version_id=1,
            standard_service_life='220000', operating_hours_total=271341))
    db.session.commit()
    row = next(row for row in context()['rows'] if row['values']['C'] == '002')
    assert row['values']['AO'] is None


def test_double_resource_replaces_saved_value_formula_and_error(calculation_database):
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], AO='#VALUE!'),
             formulas=dict(row['formulas'], AO='=1/0'), errors=[*row['errors'], 'AO'])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        standard_service_life='220000', operating_hours_total=271341))
    db.session.commit()
    result = context()
    assert result['table']['error_count'] == 0
    for row in result['rows']:
        assert row['values']['AO'] == (168659 if row['values']['C'] == '002' else None)
        assert 'AO' not in row['formulas']
        assert 'AO' not in row['errors']


@pytest.mark.parametrize('year,expected', [(2024, '68'), (2025, '-45'), (2026, '–')])
def test_double_resource_page_formula_and_values(calculation_database, http_client, monkeypatch, year, expected):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    for report_year, commissioning in ((2024, 2012), (2025, 1900)):
        db.session.add(EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type='steam', report_year=report_year, database_version_id=1,
            standard_service_life='40', commissioning_year=commissioning))
    db.session.commit()
    client, _ = http_client
    response = client.get(f'/rational_structure/equipment_runtime?year={year}&column_C=002')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    button = re.search(r'<button\b[^>]*aria-label="Формула: Остаток до достижения двойного ресурса, ч/лет"[^>]*>', headers).group()
    assert 'bi-info-circle' in button
    assert 'max(2 × «Нормативный срок службы (парковый ресурс), лет (ч)» − «Наработка с начала эксплуатации, ч», 0)' in button
    assert f'«Год ввода оборудования в эксплуатацию» + 2 × «Нормативный срок службы (парковый ресурс), лет (ч)» − {year}' in button
    assert 'технических характеристик' not in button
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    index = [key for key, _ in RUNTIME_COLUMNS].index('AO')
    assert re.sub(r'\s+', '', cells[index]) == expected
