from copy import deepcopy
from decimal import Decimal
from io import BytesIO

import pytest
from flask.templating import render_template
from openpyxl import load_workbook
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.routes import marginal_price_routes
from app.rational_structure.services.marginal_price_services import (
    build_marginal_price_context, calculate_marginal_price_annual_energy,
)


def test_annual_energy_uses_period_values_not_excel_total_and_preserves_source(calculation_database):
    source = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    original = deepcopy(source.data)
    context = build_marginal_price_context(MultiDict(), 1)
    assert [row['annual_energy'] for row in context['rows']] == [200, 200, 100]
    assert [row['annual_energy_rowspan'] for row in context['rows']] == [2, 0, 1]
    assert source.data == original
    assert context['rows'][-1]['values']['Q'] == 200
    assert context['rows'][-1]['annual_energy'] == 100
    assert next(column for column in context['table']['columns'] if column['key'] == 'Q')['formula_help']


@pytest.mark.parametrize('values,total', [([0, 0], 0), ([0.6, 0.6], Decimal('1.2')), (['1,25', '2,5'], 3.75),
                                          ([None, 10], None), (['#N/A', 10], None), (['bad', 10], None)])
def test_annual_energy_missing_values_errors_and_precision(values, total):
    rows = [{'values': {'A': 2030, 'P': value, 'Q': 999}, 'errors': []} for value in values]
    result = calculate_marginal_price_annual_energy(rows)
    assert result[0]['annual_energy'] == total
    assert result[0]['annual_energy_error'] == (total is None)
    assert result[0]['annual_energy_rowspan'] == 2
    assert result[1]['annual_energy_rowspan'] == 0
    assert rows[0]['values']['Q'] == 999
    assert 'annual_energy' not in rows[0]


def test_error_flags_prevent_summing_cached_period_value():
    rows = [{'values': {'A': 2030, 'P': 10}, 'errors': ['P']}]
    assert calculate_marginal_price_annual_energy(rows)[0]['annual_energy_error']
    assert calculate_marginal_price_annual_energy([]) == []


def test_annual_column_available_when_excel_total_is_empty(calculation_database):
    source = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    data = deepcopy(source.data)
    for table in data.values():
        table['columns'] = [column for column in table['columns'] if column['key'] != 'Q']
        for row in table['rows']:
            row['values']['Q'] = None
    source.data = data
    db.session.commit()
    context = build_marginal_price_context(MultiDict(), 1)
    assert 'Q' in [column['key'] for column in context['table']['columns']]
    assert context['rows'][0]['annual_energy'] == 200


def test_export_merges_annual_cells_and_uses_calculated_totals(calculation_database, http_client):
    client, _ = http_client
    response = client.get('/rational_structure/marginal_price/export')
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data), data_only=False)
    for sheet in book:
        assert 'Q5:Q6' in {str(merged) for merged in sheet.merged_cells.ranges}
        assert sheet['Q5'].value == 200
        assert sheet['Q6'].value is None
        assert sheet['Q7'].value == 100
        assert sheet['P5'].alignment.horizontal == 'center'
        assert sheet['Q5'].alignment.horizontal == 'center'
        assert 'сумма' in sheet['Q4'].comment.text
    book.close()


def test_invalid_period_marks_annual_cell_in_table(calculation_database, http_client, monkeypatch):
    source = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    data = deepcopy(source.data)
    data['europe']['rows'][0]['values']['P'] = None
    source.data = data
    db.session.commit()
    monkeypatch.setattr(marginal_price_routes, 'render_template', render_template)
    client, _ = http_client
    html = client.get('/rational_structure/marginal_price').get_data(as_text=True)
    assert 'rowspan="2" data-annual-energy-year="2042" class="table-warning rs-calculation-error text-center' in html
    assert 'Не рассчитана годовая энергия за 2042 год' in html
