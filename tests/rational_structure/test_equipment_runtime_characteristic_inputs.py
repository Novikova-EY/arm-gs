from decimal import Decimal

import pytest
from sqlalchemy import select

from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import context
from test_equipment_runtime_planned_events import planned_card
from test_technical_characteristics import database
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_CHARACTERISTIC_FIELDS, runtime_columns
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook
from app.rational_structure.services.technical_characteristic_columns import BASE_LABELS


@pytest.mark.parametrize('kind', ['steam', 'gas'])
def test_characteristic_inputs_follow_code_year_and_version(planned_card, kind):
    parent, _ = planned_card
    db.session.add_all([
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type=kind, report_year=2024, database_version_id=1,
            commissioning_year=1983, standard_service_life='220 000,5',
            operating_hours_total=Decimal('271341.25'), operating_hours_year=Decimal('7677.5'),
            expected_service_life_year=2030),
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type=kind, report_year=2025, database_version_id=1,
            commissioning_year=1984, standard_service_life='40', operating_hours_total=0,
            operating_hours_year=0, expected_service_life_year=2035),
        EquipmentTechnicalCharacteristic(
            equipment_code='002', equipment_type=kind, report_year=2024, database_version_id=2,
            commissioning_year=1900, standard_service_life='1'),
    ])
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], **dict.fromkeys(RUNTIME_CHARACTERISTIC_FIELDS, '#VALUE!')),
             formulas=dict(row['formulas'], **dict.fromkeys(RUNTIME_CHARACTERISTIC_FIELDS, '=1/0')),
             errors=[*row['errors'], *RUNTIME_CHARACTERISTIC_FIELDS])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()
    expected = {'M': 1983, 'S': '220 000,5', 'T': Decimal('271341.25'),
                'U': Decimal('7677.5'), 'V': 2030}
    result = context(column_M='1983', column_S='220 000,5', column_U='7677.5')
    assert result['total'] == 1
    row = result['rows'][0]
    assert row['machine_id'] == parent.id
    assert {key: row['values'][key] for key in expected} == expected
    assert not set(expected) & set(row['formulas'])
    assert not set(expected) & set(row['errors'])
    restored = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert {key: restored['calculation']['rows'][0]['values'][key] for key in expected} == expected
    row = next(row for row in context(2025)['rows'] if row['values']['C'] == '002')
    assert {key: row['values'][key] for key in expected} == {'M': 1984, 'S': '40', 'T': 0, 'U': 0, 'V': 2035}
    row = next(row for row in context(2026)['rows'] if row['values']['C'] == '002')
    assert all(row['values'][key] is None for key in expected)


def test_ambiguous_characteristics_do_not_display_arbitrary_parameters(calculation_database):
    db.session.add_all([
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type=kind,
                                         report_year=2024, database_version_id=1,
                                         commissioning_year=year, standard_service_life='40')
        for kind, year in (('steam', 1980), ('gas', 2000))
    ])
    db.session.commit()
    row = next(row for row in context()['rows'] if row['values']['C'] == '002')
    assert all(row['values'][key] is None for key in RUNTIME_CHARACTERISTIC_FIELDS)


def test_characteristic_columns_reuse_labels_and_are_only_in_calculation_view():
    columns = {column['key']: column for column in runtime_columns()}
    for key, field in RUNTIME_CHARACTERISTIC_FIELDS.items():
        assert columns[key]['label'] == BASE_LABELS[field]
        assert columns[key]['calculation_toggle'] is True
    assert columns['S']['text'] is True
    assert columns['M']['year'] is True and columns['V']['year'] is True
    assert columns['T']['integer'] is False and columns['U']['integer'] is False
