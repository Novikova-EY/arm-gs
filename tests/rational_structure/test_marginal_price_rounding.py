from copy import deepcopy
from decimal import Decimal
import re

import pytest
from flask.templating import render_template
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_technical_characteristics import database, http_client
from app.rational_structure.routes import marginal_price_routes
from app.rational_structure.services.marginal_price_services import build_marginal_price_context


@pytest.mark.parametrize('value,expected', [
    (None, 2), ('-1', -1), ('0', 0), ('1', 1), ('2', 2), ('3', 3), ('6', 6),
    ('invalid', 2), ('5', 2), ('-2', 2),
])
def test_price_rounding_is_independent_and_does_not_change_saved_data(calculation_database, value, expected):
    args = MultiDict({'rounding_digits': '6'})
    if value is not None:
        args['price_rounding_digits'] = value
    initial = build_marginal_price_context(MultiDict(), 1)
    saved = deepcopy(initial['workbook'].data)
    context = build_marginal_price_context(args, 1)
    assert context['price_rounding_digits'] == expected
    assert context['rounding_digits'] == 6
    assert next(column for column in context['table']['columns'] if column['key'] == 'C')['rounding_digits'] == expected
    assert all('rounding_digits' not in column for column in context['table']['columns'] if column['key'] != 'C')
    assert context['workbook'].data == saved
    assert context['rows'][0]['values']['C'] == Decimal('1.23456789')


@pytest.mark.parametrize('query,price,energy', [
    ('rounding_digits=-1', '1,23', '100'),
    ('rounding_digits=6', '1,23', '100,000000'),
    ('rounding_digits=-1&price_rounding_digits=3', '1,235', '100'),
    ('rounding_digits=2&price_rounding_digits=-1', '1', '100,00'),
    ('rounding_digits=-1&price_rounding_digits=0', '1,23456789', '100'),
])
def test_price_cells_and_controls_use_separate_rounding(calculation_database, http_client, monkeypatch, query, price, energy):
    monkeypatch.setattr(marginal_price_routes, 'render_template', render_template)
    client, _ = http_client
    response = client.get('/rational_structure/marginal_price?territory=south&start_year=2041&end_year=2042&' + query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    assert cells[1].strip() == price
    assert cells[4].strip() == energy
    assert html.index('id="price-rounding"') < html.index('id="calculation-rounding"') < html.index('<thead')
    control = re.search(r'<select\b[^>]*id="price-rounding"[^>]*>(.*?)</select>', html, re.S)
    assert 'name="price_rounding_digits" form="calculation-filter-form"' in control.group(0)
    for control_id in ('price-rounding', 'calculation-rounding'):
        select = re.search(r'<select\b[^>]*id="' + control_id + r'"[^>]*>', html).group(0)
        assert 'onchange="this.form.requestSubmit()"' in select
    assert not re.search(r'<button\b[^>]*form="calculation-filter-form"', html)
    assert html.count('>Применить</button>') == 1
    expected = MultiDict(pair.split('=') for pair in query.split('&')).get('price_rounding_digits', '2')
    assert re.search(r'<option value="' + expected + r'"\s+selected>', control.group(1))
