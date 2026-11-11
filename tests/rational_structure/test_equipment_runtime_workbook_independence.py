from copy import deepcopy
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, event, select
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import machine_sources
from test_equipment_runtime_modernization import set_current_year
from test_technical_characteristics import database
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import (
    build_equipment_runtime_context, read_equipment_runtime_workbook,
)
from app.rational_structure.services.equipment_runtime_summary_services import build_runtime_summary
from app.refdata.models.years.year_service_model import YearService


@pytest.fixture
def independent_runtime(machine_sources):
    set_current_year(2024)
    db.session.add(YearService(database_version_id=1, year_sipr_end=2031))
    characteristic = db.session.scalar(select(EquipmentTechnicalCharacteristic).where(
        EquipmentTechnicalCharacteristic.equipment_code == '002',
        EquipmentTechnicalCharacteristic.database_version_id == 1,
        EquipmentTechnicalCharacteristic.report_year == 2024))
    characteristic.commissioning_year = 1989
    characteristic.standard_service_life = '220000'
    characteristic.operating_hours_total = 211670
    characteristic.operating_hours_year = 7777
    db.session.get(Machine, 1).date_exploitation_expected = None
    power = db.session.scalar(select(MachinePower).where(
        MachinePower.id_machine == 1, MachinePower.year_number == 2024,
        MachinePower.database_version_id == 1))
    power.p_ust = 110
    db.session.commit()
    return machine_sources


def exported_cells(context):
    book = load_workbook(BytesIO(export_equipment_runtime(context).getvalue()))
    try:
        return {sheet.title: list(sheet.values) for sheet in book}
    finally:
        book.close()


@pytest.mark.parametrize('sheet', ['calculation', 'summary'])
@pytest.mark.parametrize('year', [None, 2024])
def test_all_columns_filters_years_and_export_ignore_saved_workbook(independent_runtime, sheet, year):
    args = MultiDict({'sheet': sheet, 'per_page': 'all'})
    if year is not None:
        args['year'] = str(year)
    before = build_equipment_runtime_context(args, 1)
    before_export = exported_cells(before)
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = {
        'calculation': {'rows': [{'values': {'C': '002', 'D': 'invalid year', 'AS': 2099, 'N': 999999}}]},
        'summary': {'columns': [], 'rows': [{'values': {'B': 'Подложная сводка из книги'}}]},
    }
    db.session.commit()
    poisoned = build_equipment_runtime_context(args, 1)
    assert poisoned == before
    assert exported_cells(poisoned) == before_export
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    without_workbook = build_equipment_runtime_context(args, 1)
    assert without_workbook == before
    assert exported_cells(without_workbook) == before_export


def test_runtime_does_not_query_workbook_table(independent_runtime):
    statements = []

    def record_statement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = db.engine
    event.listen(engine, 'before_cursor_execute', record_statement)
    try:
        result = build_equipment_runtime_context(MultiDict({'year': '2024'}), 1)
        export_equipment_runtime(result)
    finally:
        event.remove(engine, 'before_cursor_execute', record_statement)
    assert statements
    assert not any(CalculationWorkbook.__tablename__ in statement for statement in statements)
    row = next(row for row in result['rows'] if row['values']['C'] == '002')
    assert row['values'].keys() == {key for key, _ in RUNTIME_COLUMNS} | {'D'}
    assert row['values']['AS'] == 2032
    assert row['formulas'] == {}
    assert row['errors'] == []
    assert 'BK' not in row['values']


def test_summary_uses_calculated_events_and_equipment_filters(independent_runtime):
    args = MultiDict({'year': '2024', 'sheet': 'summary', 'energy_zone': '1', 'per_page': 'all'})
    result = build_equipment_runtime_context(args, 1)
    columns = {column['label']: column['key'] for column in result['table']['columns']}
    first, modernization, second, dismantling = result['rows']
    assert first['values']['B'] == 'Первый ресурс'
    assert second['values']['B'] == 'Второй ресурс'
    assert modernization['values']['B'] == 'Тип группы из карточки (Уголь)'
    assert modernization['values'][columns['2031']] is None
    assert modernization['values'][columns['2032']] == 110
    assert modernization['values'][columns['2042']] == 110
    assert dismantling['values'][columns['2042']] is None
    args['energy_zone'] = '2'
    other_zone = build_equipment_runtime_context(args, 1)
    assert all('Тип группы из карточки' not in row['values']['B'] for row in other_zone['rows'])
    assert '2043' not in columns


@pytest.mark.parametrize('current_year,end_year', [(2024, 2042), (2030, 2048)])
def test_summary_export_follows_reference_horizon(independent_runtime, current_year, end_year):
    set_current_year(current_year)
    result = build_equipment_runtime_context(MultiDict({'year': '2024', 'per_page': 'all'}), 1)
    assert result['summary_table']['columns'][-1]['label'] == str(end_year)
    restored = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert restored['summary']['columns'][-1]['label'] == str(end_year)
    key = restored['summary']['columns'][-1]['key']
    group = next(row for row in restored['summary']['rows']
                 if row['values']['B'] == 'Тип группы из карточки (Уголь)')
    assert group['values'][key] == 110


def test_summary_accumulates_power_by_group_fuel_and_event_year_without_duplicate_codes():
    equipment = [
        (1, 'Газ', 2032, 2035, Decimal('110')),
        (1, 'Газ', 2032, 2035, Decimal('110')),
        (2, 'Газ', 2033, None, Decimal('50.25')),
        (3, 'Уголь', 2031, 2042, Decimal('20')),
        (4, 'Газ', 2043, 2024, Decimal('30')),
        (5, 'Газ', None, 2032, None),
    ]
    rows = [{'machine_id': identity, 'pgu_machine_id': None,
             'values': {'K': 'Группа', 'AM': fuel, 'AS': modernization, 'BC': dismantling, 'N': power}}
            for identity, fuel, modernization, dismantling, power in equipment]
    before = deepcopy(rows)
    result = build_runtime_summary(rows, 2024, 2042)
    columns = {column['label']: column['key'] for column in result['columns']}
    first, gas, coal, second, gas_dismantling, coal_dismantling = result['rows']
    assert gas['values']['B'] == 'Группа (Газ)'
    assert coal['values']['B'] == 'Группа (Уголь)'
    assert gas['values'][columns['2031']] is None
    assert gas['values'][columns['2032']] == 110
    assert gas['values'][columns['2033']] == Decimal('160.25')
    assert gas['values'][columns['2042']] == Decimal('160.25')
    assert coal['values'][columns['2031']] == 20
    assert gas_dismantling['values'][columns['2034']] is None
    assert gas_dismantling['values'][columns['2035']] == 110
    assert coal_dismantling['values'][columns['2041']] is None
    assert coal_dismantling['values'][columns['2042']] == 20
    assert rows == before
