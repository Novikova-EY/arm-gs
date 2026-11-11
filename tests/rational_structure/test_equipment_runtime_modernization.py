import re
from decimal import Decimal
from html import unescape

import pytest
from flask.templating import render_template
from sqlalchemy import delete, select
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_equipment_runtime_double_resource import context
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_machine_services import _modernization_year
from app.rational_structure.services.equipment_runtime_services import (
    build_equipment_runtime_context, read_equipment_runtime_workbook,
)
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year


def set_current_year(year, version=1):
    feature = db.session.scalar(select(YearFeature).where(
        YearFeature.database_version_id == version, YearFeature.name == 'текущий (оценка)'))
    if feature is None:
        feature = YearFeature(name='текущий (оценка)', database_version_id=version)
        db.session.add(feature)
        db.session.flush()
    for row in db.session.scalars(select(Year).where(Year.database_version_id == version)):
        if row.id_year_feature == feature.id:
            row.id_year_feature = None
    row = db.session.scalar(select(Year).where(Year.database_version_id == version, Year.number == year))
    if row is None:
        row = Year(number=year, database_version_id=version)
        db.session.add(row)
    row.id_year_feature = feature.id
    db.session.commit()


def save_supply(supply, report_year=2024):
    db.session.get(Machine, 1).date_exploitation_expected = supply
    workbook = db.session.scalar(select(CalculationWorkbook).where(
        CalculationWorkbook.kind == 'equipment_runtime', CalculationWorkbook.database_version_id == 1))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], D=report_year, M=1900, AU=supply, AR='#VALUE!'),
             formulas=dict(row['formulas'], AR='=1/0'), errors=[*row['errors'], 'AR'])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()


@pytest.mark.parametrize('current,first,supply,commissioning,expected', [
    (2024, 2024, 2030, 2000, 0),
    (2024, 2025, 0, None, 2025),
    (2024, 2042, 0, None, 2042),
    (2024, 2043, 0, None, 0),
    (2024, 2061, 0, None, 0),
    (2024, 0, 0, None, 0),
    (2024, 0, 2026, 1983, 2026),
    (2024, 2081, 2023, 2023, 0),
    (2024, 2042, 2035, 2000, 2035),
    (2024, 2043, 2050, 2000, 2050),
    (2029, 2029, 2050, 2000, 2050),
    (2029, 2030, 0, None, 2030),
    (2029, 2043, 0, None, 0),
    (2030, 2030, 2050, 2000, 2050),
    (2030, 2031, 0, None, 2031),
    (2030, 2048, 0, None, 2048),
    (2030, 2049, 0, None, 0),
    (None, 2030, 0, 2000, None),
    (None, 2024, None, None, 0),
    (2024, None, 2026, 2000, None),
    (2024, 2030, None, 2000, 2030),
    (2024, 2025, None, None, 2025),
    (2024, 2042, None, None, 2042),
    (2024, 2043, None, None, 0),
    (2024, 0, None, None, 0),
    (2024, None, None, None, None),
    (2024, 2030, 2026, None, None),
    (2024, 2024, None, None, 0),
])
def test_modernization_dynamic_boundaries_and_excel_branch_order(
        calculation_database, current, first, supply, commissioning, expected):
    if current is not None:
        set_current_year(current)
    save_supply(supply)
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        expected_service_life_year=first, commissioning_year=commissioning))
    db.session.commit()
    result = context()
    row = next(row for row in result['rows'] if row['values']['C'] == '002')
    assert row['values']['AR'] == expected
    assert 'AR' not in row['formulas']
    assert 'AR' not in row['errors']


@pytest.mark.parametrize('first,end,expected', [
    (Decimal('2025.49'), 2042, 2025),
    (Decimal('2025.5'), 2042, 2026),
    (Decimal('2042.01'), 2042, 0),
    (Decimal('2041.5'), 2042, 2042),
    (2030, None, None),
])
def test_modernization_compares_before_excel_rounding(first, end, expected):
    assert _modernization_year(None, {'AQ': first, 'AU': 0}, 2024, end) == expected


def test_modernization_uses_selected_year_for_lower_boundary_and_reference_for_upper(calculation_database):
    set_current_year(2024)
    set_current_year(2036, version=2)
    save_supply(0, report_year=2025)
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='gas', report_year=2025, database_version_id=1,
        expected_service_life_year=2026))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='gas', report_year=2026, database_version_id=1,
        expected_service_life_year=2026))
    db.session.commit()
    result = context(2025, column_AR='2026')
    assert result['current_year'] == 2024
    assert result['general_scheme_end_year'] == 2042
    assert result['total'] == 1
    restored = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert restored['calculation']['rows'][0]['values']['AR'] == 2026
    set_current_year(2030)
    result = context(2025, column_AR='2026')
    assert result['current_year'] == 2030
    assert result['general_scheme_end_year'] == 2048
    assert result['total'] == 1
    assert result['rows'][0]['values']['AR'] == 2026
    result = context(2026, column_AR='0')
    assert result['total'] == 1
    assert result['rows'][0]['values']['AR'] == 0
    other = build_equipment_runtime_context(MultiDict({'year': '2025'}), 2)
    assert other['current_year'] == 2036
    assert other['general_scheme_end_year'] == 2054


def test_modernization_missing_workbook_does_not_use_stale_supply(calculation_database):
    set_current_year(2024)
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        expected_service_life_year=2030))
    db.session.commit()
    rows = context()['rows']
    row = next(row for row in rows if row['values']['C'] == '002')
    assert row['values']['AU'] is None
    assert row['values']['AR'] == 2030
    assert all(row['values']['AR'] is None for row in rows if row['values']['AQ'] is None)


def test_modernization_does_not_choose_ambiguous_characteristic(calculation_database):
    set_current_year(2024)
    save_supply(2030)
    for kind in ('steam', 'gas'):
        db.session.add(EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type=kind, report_year=2024, database_version_id=1,
            expected_service_life_year=2035, commissioning_year=2000))
    db.session.commit()
    assert next(row for row in context()['rows'] if row['values']['C'] == '002')['values']['AR'] is None


def test_modernization_page_and_formatted_help(calculation_database, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    set_current_year(2030)
    save_supply(0, report_year=2025)
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2025, database_version_id=1,
        expected_service_life_year=2048))
    db.session.commit()
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime?year=2025&column_AR=2048')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    button = re.search(r'<button\b[^>]*aria-label="Формула: Расчетный год модернизации до 2049 года"[^>]*>', headers).group()
    assert 'Расчетный год модернизации до 2049 года' in headers
    assert 'data-bs-html="true"' in button
    assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in button
    content = unescape(re.search(r'\btitle="([^"]*)"', button).group(1))
    assert 'Пустой «Плановый год ввода оборудования» в расчете принимается равным 0' in content
    assert content.count('<p>') >= 4
    assert '<strong>' in content
    assert '«Год достижения первого нормативного ресурса» &lt; 2026' in content
    assert '«Год достижения первого нормативного ресурса» ≤ 2048' in content
    assert '«Год ввода оборудования в эксплуатацию» = «Плановый год ввода оборудования»' in content
    assert 'ОКРУГЛ(«Год достижения первого нормативного ресурса»; 0)' in content
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    index = [key for key, _ in RUNTIME_COLUMNS].index('AR')
    assert re.sub(r'\s+', '', cells[index]) == '2048'
