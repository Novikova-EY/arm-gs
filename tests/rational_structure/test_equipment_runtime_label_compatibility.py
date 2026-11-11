from io import BytesIO

import pytest
from openpyxl import load_workbook
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_technical_characteristics import database
from app.rational_structure.services.equipment_runtime_columns import runtime_columns
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import (
    build_equipment_runtime_context, read_equipment_runtime_workbook,
)


@pytest.mark.parametrize('card_only', [False, True])
def test_exports_with_previous_year_labels_remain_readable(calculation_database, card_only):
    context = build_equipment_runtime_context(MultiDict(), 1)
    context['filtered_rows'][0]['values'].update(AS=2032, planned_modernization_year=2035, BC=2040)
    book = load_workbook(export_equipment_runtime(context))
    sheet = book['Расчет']
    keys = [column['key'] for column in runtime_columns()]
    sheet.cell(1, keys.index('BC') + 1).value = 'Плановый год демонтажа с учетом модернизации'
    if card_only:
        sheet.delete_cols(keys.index('AS') + 1)
    else:
        sheet.cell(1, keys.index('AS') + 1).value = 'Год модернизации с учетом СиПР'
    stream = BytesIO()
    book.save(stream)
    book.close()
    row = read_equipment_runtime_workbook(stream.getvalue())['calculation']['rows'][0]['values']
    assert row['planned_modernization_year'] == 2035
    assert row['BC'] == 2040
    if not card_only:
        assert row['AS'] == 2032
