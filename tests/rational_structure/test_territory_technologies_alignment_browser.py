from pathlib import Path

import pytest
from flask.templating import render_template

from test_territory_technologies import territory_database, workbook
from test_technical_characteristics import database, http_client
from app.rational_structure.services.territory_technology_services import import_territory_inputs

pytest.importorskip('selenium')
from selenium import webdriver

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.mark.parametrize('sheet', ['technologies', 'transfers'])
@pytest.mark.parametrize('editable', [True, False])
def test_numeric_cells_are_centered(browser, territory_database, http_client, monkeypatch, tmp_path, sheet, editable):
    from app.rational_structure.routes import territory_technology_routes as routes

    monkeypatch.setattr(routes, 'render_template', render_template)
    client, user = http_client
    user.has_admin = editable
    import_territory_inputs(workbook(), 1, 'tester', 'test.xlsx')
    response = client.get('/rational_structure/territory_technologies', query_string={'sheet': sheet})
    assert response.status_code == 200
    styles = '\n'.join((ROOT / 'app/static/css' / name).read_text(encoding='utf-8') for name in (
        'bootstrap.min.css', 'style.css', 'table_headers.css',
        'rational_structure/territory_technologies.css', 'rational_structure/pages.css',
    ))
    page = tmp_path / 'territory.html'
    page.write_text('<!doctype html><meta charset="utf-8"><style>' + styles + '</style>'
                    + response.get_data(as_text=True), encoding='utf-8')
    browser.get(page.as_uri())
    result = browser.execute_script('''
        const cells = [...document.querySelectorAll('.rs-territory-table td.text-center')];
        const inputs = [...document.querySelectorAll('.rs-territory-table .rs-number-input')];
        return {
            cells: cells.length,
            inputs: inputs.length,
            centered: [...cells, ...inputs].every(el => getComputedStyle(el).textAlign === 'center'),
            middle: cells.every(el => getComputedStyle(el).verticalAlign === 'middle')
        };
    ''')
    assert result['cells'] > 0
    assert (result['inputs'] > 0) == editable
    assert result['centered']
    assert result['middle']
