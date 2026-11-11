from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from flask.templating import render_template
from openpyxl import load_workbook
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database, price_bytes
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.routes import marginal_price_routes
from app.rational_structure.services.marginal_price_services import (
    build_marginal_price_context,
    calculate_marginal_price_annual_energy,
    import_marginal_price_workbook,
)


def noisy_price_bytes():
    stream = BytesIO()
    with ZipFile(BytesIO(price_bytes())) as source, ZipFile(stream, 'w', ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename.startswith('xl/worksheets/sheet'):
                content = content.replace(b'<v>1.23456789</v>', b'<v>105.10000000000001</v>')
                content = content.replace(b'<v>100</v>', b'<v>0.10000000000000001</v>')
            target.writestr(item, content)
    return stream.getvalue()


def test_import_stores_decimal_text_and_calculates_exact_totals(calculation_database):
    import_marginal_price_workbook(noisy_price_bytes(), 1, 'tester', 'decimal.xlsx')
    db.session.remove()
    context = build_marginal_price_context(MultiDict({'territory': 'south'}), 1)
    saved = context['workbook'].data['south']['rows'][0]['values']
    assert saved['C'] == '105.1'
    assert saved['P'] == '0.1'
    assert saved['A'] == 2042
    assert saved['B'] == 1
    assert context['rows'][0]['values']['C'] == Decimal('105.1')
    assert isinstance(context['rows'][0]['values']['C'], Decimal)
    assert context['rows'][0]['annual_energy'] == Decimal('0.2')
    assert isinstance(context['rows'][0]['annual_energy'], Decimal)


@pytest.mark.parametrize('periods,total', [
    ([0.1, 0.2], Decimal('0.3')),
    ([105.10000000000001, 0.2], Decimal('105.3')),
    (['0.1234567890123456789', '0.0000000000000000001'], Decimal('0.1234567890123456790')),
    ([float('nan'), 1], None),
    ([float('inf'), 1], None),
    ([True, 1], None),
    (['1\u00a0234,5', '0,5'], Decimal('1235.0')),
])
def test_decimal_sums_preserve_precision_and_reject_invalid_periods(periods, total):
    rows = [{'values': {'A': 2030, 'D': '001', 'P': value}, 'errors': []} for value in periods]
    result = calculate_marginal_price_annual_energy(rows)
    assert result[0]['annual_energy'] == total
    assert result[0]['annual_energy_error'] == (total is None)
    assert result[0]['values']['D'] == '001'
    assert 'annual_energy' not in rows[0]


def test_legacy_floats_render_without_noise_and_export_as_numbers(calculation_database, http_client, monkeypatch):
    source = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    data = deepcopy(source.data)
    for row in data['south']['rows']:
        row['values']['C'] = 105.10000000000001
        row['values']['P'] = 0.10000000000000002
    source.data = data
    db.session.commit()
    monkeypatch.setattr(marginal_price_routes, 'render_template', render_template)
    client, _ = http_client
    html = client.get('/rational_structure/marginal_price?territory=south&start_year=2041&end_year=2042'
                      '&rounding_digits=0&price_rounding_digits=0').get_data(as_text=True)
    assert '105,1' in html
    assert '0,2' in html
    assert '105,10000000000001' not in html
    assert '0,10000000000000002' not in html
    assert source.data == data
    response = client.get('/rational_structure/marginal_price/export')
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data), data_only=True)
    sheet = book['Юг']
    assert sheet['C5'].data_type == 'n'
    assert sheet['C5'].value == 105.1
    assert sheet['P5'].value == 0.1
    assert sheet['Q5'].value == 0.2
    assert sheet['C5'].alignment.horizontal == 'center'
    book.close()
