from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import delete, select

from test_calculation_pages import calculation_database
from test_technical_characteristics import database
from test_equipment_runtime_machine_sources import context
from test_equipment_runtime_modernization import set_current_year
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import runtime_columns
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_machine_services import _modernization_sipr_year
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook
from app.refdata.models.years.year_service_model import YearService


@pytest.mark.parametrize('year,supply,end,expected', [
    (2030, 0, 2032, 2033), (2030, None, 2032, 2033),
    (2030, 2029, 2032, 2030), (2030, -1, 2032, 2030),
    (2032, 0, 2032, 2033), (2033, 0, 2032, 2033),
    (0, 0, 2032, 0), (-1, 0, 2032, -1), (None, 0, 2032, None),
    (2030, 0, 2038, 2039), (2030, 2031, None, 2030),
    (2030, 0, None, None), (0, None, None, 0),
])
def test_sipr_modernization_excel_branches(year, supply, end, expected):
    assert _modernization_sipr_year({'AR': year, 'AU': supply}, end) == expected


@pytest.mark.parametrize('year', [0, 2029, 2031, 2032, 2033, 2042])
@pytest.mark.parametrize('supply', [0, 2029, -1])
def test_sipr_modernization_matches_original_excel_formula(year, supply):
    expected = year if 0 < year < 2032 and supply > 0 else (
        2032 if 0 < year < 2032 and supply == 0 else year)
    assert _modernization_sipr_year({'AR': year, 'AU': supply}, 2031) == expected


def test_live_sipr_modernization_is_separate_from_card_and_drives_dismantling(calculation_database):
    set_current_year(2024)
    db.session.add(YearService(database_version_id=1, year_sipr_end=2032))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        expected_service_life_year=2030, commissioning_year=2000))
    machine = db.session.get(Machine, 1)
    machine.date_exploitation_expected = 0
    machine.date_modernization_power_change_expected = 2040
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], AS='#VALUE!'),
             formulas=dict(row['formulas'], AS='=1/0'), errors=[*row['errors'], 'AS'])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()
    result = context(column_AS='2033')
    assert result['total'] == 1
    row = result['rows'][0]
    assert row['values']['AR'] == 2030
    assert row['values']['AS'] == 2033
    assert row['values']['planned_modernization_year'] == 2040
    assert 'AS' not in row['errors'] and 'AS' not in row['formulas']
    restored = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert restored['calculation']['rows'][0]['values']['AS'] == 2033
    assert restored['calculation']['rows'][0]['values']['planned_modernization_year'] == 2040
    columns = runtime_columns()
    keys = [column['key'] for column in columns]
    assert keys[keys.index('AR'):keys.index('AR') + 3] == ['AR', 'AS', 'planned_modernization_year']
    as_column = columns[keys.index('AS')]
    assert as_column['highlight_color'] == 'C6E0B4'
    assert as_column['calculation_toggle'] is False


@pytest.mark.parametrize('supply', [None, 0])
@pytest.mark.parametrize('with_workbook', [True, False])
def test_missing_supply_calculates_modernization_without_changing_card(
        calculation_database, supply, with_workbook):
    set_current_year(2024)
    db.session.add(YearService(database_version_id=1, year_sipr_end=2031))
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        commissioning_year=1989, standard_service_life='220000',
        operating_hours_total=211670, operating_hours_year=7777))
    machine = db.session.get(Machine, 1)
    machine.date_exploitation_expected = supply
    if not with_workbook:
        db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()

    result = context(column_AS='2032')
    assert result['total'] == 1
    row = result['rows'][0]
    assert row['values']['AQ'] == 2025
    assert row['values']['AR'] == 2025
    assert row['values']['AS'] == 2032
    assert row['values']['AU'] == supply
    db.session.refresh(machine)
    assert machine.date_exploitation_expected == supply

    restored = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    values = restored['calculation']['rows'][0]['values']
    assert values['AR'] == 2025
    assert values['AS'] == 2032
    assert values['AU'] == supply


def test_previous_card_export_does_not_confuse_planned_year_with_excel_as():
    columns = [dict(column, key='planned_modernization_year', label='Плановый год модернизации')
               if column['key'] == 'AS' else column
               for column in runtime_columns() if column['key'] != 'planned_modernization_year']
    book = Workbook()
    sheet = book.active
    sheet.title = 'Расчет'
    sheet.append([column['label'] for column in columns])
    values = {'C': '002', 'G': 'ТЭС', 'planned_modernization_year': 2035, 'BC': 2040}
    sheet.append([values.get(column['key']) for column in columns])
    summary = book.create_sheet('Лист2')
    summary.append([])
    summary.append(['№', 'Показатель', 'Единица измерения'])
    summary.append([1, 'Ресурс', 'ч'])
    stream = BytesIO()
    book.save(stream)
    book.close()
    restored = read_equipment_runtime_workbook(stream.getvalue())['calculation']['rows'][0]['values']
    assert restored['planned_modernization_year'] == 2035
    assert restored['BC'] == 2040
    assert 'AS' not in restored
