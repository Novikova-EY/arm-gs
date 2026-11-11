from pathlib import Path

import pytest
from flask.templating import render_template

from test_calculation_pages import calculation_database
from test_technical_characteristics import database, http_client

pytest.importorskip('selenium')
from selenium import webdriver
from selenium.webdriver.support.ui import Select, WebDriverWait

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.fixture
def page_url(calculation_database, http_client, monkeypatch, tmp_path):
    from app.rational_structure.routes import marginal_price_routes

    monkeypatch.setattr(marginal_price_routes, 'render_template', render_template)
    client, _ = http_client
    content = client.get('/rational_structure/marginal_price').get_data(as_text=True)
    styles = '\n'.join((ROOT / 'app/static/css' / name).read_text(encoding='utf-8') for name in (
        'bootstrap.min.css', 'style.css', 'table_headers.css',
        'rational_structure/pages.css', 'rational_structure/calculation_pages.css',
    ))
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    start = base.index('        (function () {')
    layout_script = base[start:base.index('    </script>', start)]
    bootstrap = (ROOT / 'app/static/js/bootstrap.bundle.min.js').read_text(encoding='utf-8')
    tooltips = (ROOT / 'app/static/js/common/info_tooltips.js').read_text(encoding='utf-8')
    page = tmp_path / 'marginal_price.html'
    page.write_text(
        '<!doctype html><meta charset="utf-8"><style>' + styles + '</style>' + content
        + '<script>' + bootstrap + '</script><script>' + tooltips + '</script><script>' + layout_script + '</script>', encoding='utf-8',
    )
    return page.as_uri()


def test_rounding_selects_submit_filters_immediately(browser, page_url):
    browser.get(page_url)
    browser.execute_script('''
        window.submittedFilters = [];
        document.getElementById('calculation-filter-form').addEventListener('submit', event => {
            event.preventDefault();
            window.submittedFilters.push(Object.fromEntries(new FormData(event.target)));
        });
    ''')
    Select(browser.find_element('id', 'price-rounding')).select_by_value('3')
    WebDriverWait(browser, 3).until(lambda driver: driver.execute_script('return window.submittedFilters.length') == 1)
    first = browser.execute_script('return window.submittedFilters[0]')
    assert first == {'territory': 'europe', 'start_year': '2041', 'end_year': '2042',
                     'price_rounding_digits': '3', 'rounding_digits': '-1'}
    Select(browser.find_element('id', 'calculation-rounding')).select_by_value('6')
    WebDriverWait(browser, 3).until(lambda driver: driver.execute_script('return window.submittedFilters.length') == 2)
    assert browser.execute_script('return window.submittedFilters[1]') == {**first, 'rounding_digits': '6'}
    assert browser.find_elements('css selector', 'button[form="calculation-filter-form"]') == []
    assert len(browser.find_elements('css selector', '#calculation-filter-form button[type="submit"]')) == 1


def metrics(driver):
    return driver.execute_script('''
        const wrap = document.querySelector('.rs-calculation-scroll');
        const panel = wrap.querySelector('.rs-calculation-stack');
        const header = wrap.querySelector('thead th');
        const r = header.getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        const hit = document.elementFromPoint(r.x + 10, r.y + r.height / 2);
        return {
            scroll: wrap.scrollTop, panelTop: panelRect.top, panelBottom: panelRect.bottom,
            wrapTop: wrap.getBoundingClientRect().top, headerTop: r.top, headerBottom: r.bottom,
            headerOnTop: header.contains(hit), viewportHeight: innerHeight,
            offset: parseFloat(getComputedStyle(wrap).getPropertyValue('--pd-summary-controls-sticky-height')),
            panelHeight: panelRect.height,
        };
    ''')


def assert_sticky(value):
    assert value['scroll'] > 0
    assert abs(value['panelTop'] - value['wrapTop']) <= 1
    assert abs(value['headerTop'] - value['panelBottom']) <= 2
    assert value['headerBottom'] < value['viewportHeight']
    assert value['headerOnTop']


@pytest.mark.parametrize('width', [1000, 1600])
def test_controls_and_header_remain_visible_on_scroll_and_resize(browser, page_url, width):
    browser.set_window_size(width, 1100)
    browser.get(page_url)
    wait = WebDriverWait(browser, 8)
    wait.until(lambda driver: metrics(driver)['offset'] > 0)
    browser.execute_script('''
        const body = document.querySelector('.rs-calculation-table tbody');
        const row = body.querySelector('tr:not(.rs-year-heading)');
        for (let i = 0; i < 120; i++) body.append(row.cloneNode(true));
        document.querySelector('.rs-calculation-scroll').scrollTop = 900;
    ''')
    wait.until(lambda driver: metrics(driver)['scroll'] > 0)
    assert_sticky(metrics(browser))
    original_height = metrics(browser)['panelHeight']
    browser.execute_script("bootstrap.Collapse.getOrCreateInstance(document.getElementById('marginal-price-import'), {toggle: false}).show()")
    wait.until(lambda driver: metrics(driver)['panelHeight'] > original_height + 10)
    wait.until(lambda driver: abs(metrics(driver)['offset'] - metrics(driver)['panelHeight']) <= 1)
    assert_sticky(metrics(browser))
    browser.execute_script("bootstrap.Collapse.getOrCreateInstance(document.getElementById('marginal-price-import')).hide()")
    wait.until(lambda driver: abs(metrics(driver)['panelHeight'] - original_height) <= 1)
    assert_sticky(metrics(browser))
    browser.execute_script("document.querySelector('th[data-column-key=Q] button').focus()")
    wait.until(lambda driver: driver.execute_script("return document.querySelector('.tooltip-inner')?.textContent.includes('Годовая энергия = сумма')"))
    assert browser.execute_script("return getComputedStyle(document.querySelector('.rs-year-heading th')).backgroundColor") == 'rgb(255, 229, 208)'
    assert browser.execute_script("return getComputedStyle(document.querySelector('td[data-annual-energy-year]')).textAlign") == 'center'
    browser.set_window_size(1200 if width == 1600 else 1500, 1100)
    wait.until(lambda driver: abs(metrics(driver)['offset'] - metrics(driver)['panelHeight']) <= 1)
    assert_sticky(metrics(browser))
