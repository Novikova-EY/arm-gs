import re
from pathlib import Path

import pytest
from flask.templating import render_template

from test_calculation_pages import calculation_database
from test_technical_characteristics import database, http_client
from app.rational_structure.services.equipment_runtime_columns import runtime_columns


TOGGLED_KEYS = {'M', 'S', 'T', 'U', 'V', 'AN', 'AO', 'AP', 'AQ', 'AR', 'planned_modernization_year', 'AT', 'AU', 'AV', 'AW', 'AX', 'AY', 'AZ', 'BA', 'BD', 'BF'}


def test_toggle_metadata_matches_requested_columns():
    columns = runtime_columns()
    assert {column['key'] for column in columns if column['calculation_toggle']} == TOGGLED_KEYS
    assert all(not column['calculation_toggle'] for column in columns if column['key'] in {'AS', 'BC'})


@pytest.mark.parametrize('sheet', ['calculation', 'summary'])
def test_runtime_page_toggle_markup(calculation_database, http_client, monkeypatch, sheet):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    response = client.get(f'/rational_structure/equipment_runtime?sheet={sheet}')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    button = re.search(r'<button\b[^>]*id="rs-runtime-calculation-toggle"[^>]*>Расчет</button>', html)
    if sheet == 'summary':
        assert button is None
        assert 'rs-runtime-result' not in html
        return

    assert button is not None
    assert 'btn-outline-primary' in button.group()
    assert 'type="button"' in button.group()
    assert 'aria-pressed="false"' in button.group()
    assert ' active' not in button.group()
    assert html.index('Экспорт в Excel</a>') < button.start() < html.index('<thead')
    assert 'rs-runtime-calculation rs-runtime-results-hidden' in html
    assert 'id="rs-runtime-table"' in html
    assert 'colspan="4" data-sipr-span="events" class="rs-sipr-group rs-runtime-result">Мероприятия СиПР</th>' in html
    assert len(re.findall(r'<th scope="col"[^>]*data-sipr-section="events"', html)) == 4
    assert 'js/rational_structure/equipment_runtime.js' in html
    headers = re.findall(r'<th\b[^>]*scope="col"[^>]*>', html)
    columns = runtime_columns()
    keys = [column['key'] for column in columns]
    headers.sort(key=lambda header: keys.index(re.search(r'data-column-key="([^"]+)"', header).group(1)))
    assert len(headers) == len(columns)
    for header, column in zip(headers, columns):
        assert 'title=""' in header
        assert 'Столбец ' not in header
        assert ('rs-runtime-result' in header) == (column['key'] in TOGGLED_KEYS)
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', body, re.S)
    assert rows
    for row in rows:
        cells = re.findall(r'<td\b[^>]*>', row)
        assert len(cells) == len(columns)
        for cell, column in zip(cells, columns):
            assert ('rs-runtime-result' in cell) == (column['key'] in TOGGLED_KEYS)

    css = Path('app/static/css/rational_structure/pages.css').read_text(encoding='utf-8')
    assert re.search(r'\.rs-runtime-results-hidden \.rs-runtime-result\s*\{\s*display: none;', css)
    scroll_rule = re.search(
        r'\.rs-runtime-calculation:not\(\.rs-runtime-results-hidden\) #rs-runtime-table\s*\{([^}]+)\}', css,
    ).group(1)
    assert 'max-height: 65vh !important;' in scroll_rule
    assert 'overflow-y: scroll !important;' in scroll_rule
    assert 'overflow-x: auto !important;' in scroll_rule
