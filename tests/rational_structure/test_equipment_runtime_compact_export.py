from io import BytesIO

import pytest
from openpyxl import load_workbook

from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import context
from test_technical_characteristics import database
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_CHARACTERISTIC_FIELDS, runtime_columns
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook


@pytest.mark.parametrize('card_only', [False, True])
def test_exports_before_characteristic_columns_keep_year_mapping(calculation_database, card_only):
    result = context()
    result['filtered_rows'][0]['values'].update(AS=2032, planned_modernization_year=2035, BC=2040)
    book = load_workbook(export_equipment_runtime(result))
    sheet = book['Расчет']
    columns = runtime_columns()
    removed = set(RUNTIME_CHARACTERISTIC_FIELDS) | ({'AS'} if card_only else set())
    for index in reversed(range(len(columns))):
        if columns[index]['key'] in removed:
            sheet.delete_cols(index + 1)
    stream = BytesIO()
    book.save(stream)
    book.close()
    row = read_equipment_runtime_workbook(stream.getvalue())['calculation']['rows'][0]['values']
    assert row['C'] == '002'
    assert row['AN'] == 0
    assert row['planned_modernization_year'] == 2035
    assert row['BC'] == 2040
    assert not set(RUNTIME_CHARACTERISTIC_FIELDS) & set(row)
    if card_only:
        assert 'AS' not in row
    else:
        assert row['AS'] == 2032
