import re

import pytest
from flask import render_template_string

pytest.importorskip("selenium")
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from test_consumption_cell_styles_browser import browser, ROOT
from test_growth_rounding import ROUNDING_TEMPLATES


@pytest.mark.parametrize("template", ROUNDING_TEMPLATES, ids=lambda path: path.stem)
def test_no_template_keeps_the_old_reload_handler(template):
    source = template.read_text(encoding="utf-8")
    assert 'url.searchParams.set("rounding_digits", this.value)' not in source
    assert 'rounding_digits: roundingDigits' not in source


@pytest.fixture
def rounding_page(app, browser, tmp_path):
    with app.test_request_context():
        growth = render_template_string("{% include 'energy_consumption/_growth_rounding.html' %}")
    script = (ROOT / "app/static/js/energy_consumption/growth_rounding.js").read_text(encoding="utf-8")
    growth = re.sub(r'<script[^>]+growth_rounding\.js[^>]*></script>', '', growth)
    live = '\n'.join((ROOT / "app/static/js/energy_consumption" / name).read_text(encoding="utf-8")
                     for name in ("consumption_live_save.js", "demand_summary_live_save.js"))
    html = '''<!doctype html><meta charset="utf-8">
<button id="demandSummarySaveBtn">Сохранить</button>
<select id="rounding_digits"><option value="0">Без округления</option><option value="1" selected>1</option><option value="2">2</option><option value="3">3</option><option value="-1">Целое</option></select>
''' + growth + '''
<table id="powerDemandSummaryTable" class="power-demand-summary-table" data-save-cell-url="/save" data-rounding-digits="1" data-csrf-token="csrf"><tbody>
<tr data-parameter-key="energy_consumption_mln_kvt_ch"><td class="summary-year-cell" data-bs-original-title="1234,56789"><span id="calculated">1 234,6</span></td>
<td class="summary-year-cell"><input id="clean" class="fuel-param-input" data-model="EesRussiaEnergyConsumptionParameter" data-parameter-key="energy_consumption_mln_kvt_ch" data-slice="2025" data-db-full="1234,56789" data-initial="1 234,6" value="1 234,6"></td>
<td class="summary-year-cell"><input id="dirty" class="fuel-param-input" data-model="EesRussiaEnergyConsumptionParameter" data-parameter-key="energy_consumption_mln_kvt_ch" data-slice="2024" data-db-full="123" data-initial="123" value="123"></td>
<td class="summary-year-cell summary-plan-empty pd-ec-variant-year-out" id="masked"></td></tr>
<tr data-parameter-key="peak_datetime"><td class="summary-year-cell" id="date">31.12.2025 23:59</td></tr>
<tr data-parameter-key="entity_note"><td class="summary-year-cell" id="yearNote">123,4567</td></tr>
<tr class="pd-ec-verification-row" data-parameter-key="energy_consumption_mln_kvt_ch"><td class="summary-year-cell" title="0,00000012345" id="verification">0</td></tr>
<tr data-parameter-key="energy_consumption_yoy_growth_pct"><td class="summary-year-cell" title="1,23456789" id="growth">1,23</td></tr>
<tr data-parameter-key="energy_consumption_sipr_mln_kvt_ch" data-pd-ec-sipr-integer-display="1"><td class="summary-year-cell" title="1234,56789" id="sipr">1 234,6</td></tr>
</tbody></table>
<form id="demand-params-form"><input type="hidden" name="rounding_digits" value="1"><table id="power-demand-edit-table"><tbody><tr><td><input id="detail" name="ec_mln[]" data-initial="1 234,6" value="1 234,6" title="1234,56789"></td></tr></tbody></table></form>
<table id="power-demand-view-table"><tbody><tr><td id="view" title="1234,56789">1 234,6</td></tr></tbody></table>
<script>window.pageToken='original';window.posts=[];window.fetch=async(url,options)=>{window.posts.push(JSON.parse(options.body));return {ok:true,json:async()=>({ok:true})};};</script>
<script>''' + script + live + '''</script>'''
    page = tmp_path / "rounding.html"
    page.write_text(html, encoding="utf-8")
    browser.get(page.as_uri() + '?rounding_digits=1&growth_rounding_digits=2&start_year=2024')
    browser.execute_script('''
        const field = document.getElementById('dirty');
        field.value = '456,789';field.dispatchEvent(new Event('input',{bubbles:true}));
    ''')
    return browser


def test_general_rounding_is_instant_independent_and_preserves_source_and_dirty_fields(rounding_page):
    driver = rounding_page
    select = Select(driver.find_element(By.ID, "rounding_digits"))
    for digits, expected in [("2", "1 234,57"), ("3", "1 234,568"), ("-1", "1 235"),
                             ("0", "1 234,56789"), ("1", "1 234,6")]:
        select.select_by_value(digits)
        state = driver.execute_script('''return {
            values:['calculated','clean','detail','view'].map(id=>{const el=document.getElementById(id);return el.value ?? el.textContent}),
            initial:document.getElementById('clean').dataset.initial,
            dirty:document.getElementById('dirty').value, growth:document.getElementById('growth').textContent,
            date:document.getElementById('date').textContent,note:document.getElementById('yearNote').textContent,
            masked:document.getElementById('masked').textContent,token:window.pageToken,posts:window.posts,
            rounding:document.querySelector('input[name="rounding_digits"]').value,
            tableRounding:document.getElementById('powerDemandSummaryTable').dataset.roundingDigits,
            url:location.search,verification:document.getElementById('verification').textContent
        };''')
        assert state["values"] == [expected] * 4
        assert state["initial"] == expected
        assert state["dirty"] == "456,789"
        assert state["growth"] == "1,23"
        assert state["date"] == "31.12.2025 23:59"
        assert state["note"] == "123,4567"
        assert state["masked"] == ""
        assert state["token"] == "original" and not state["posts"]
        assert state["rounding"] == state["tableRounding"] == digits
        assert "start_year=2024" in state["url"]
        assert state["verification"] == ("0,00000012345" if digits == "0" else "0")
    select.select_by_value("3")
    driver.find_element(By.ID, "demandSummarySaveBtn").click()
    WebDriverWait(driver, 5).until(lambda page: len(page.execute_script("return window.posts")) == 1)
    post = driver.execute_script("return window.posts[0]")
    assert post["rounding_digits"] == 3 and post["value"] == "456,789"


def test_sipr_and_new_rows_keep_the_selected_precision(rounding_page):
    driver = rounding_page
    driver.execute_script("window.__pdEcSummarySiprMode = true;")
    Select(driver.find_element(By.ID, "rounding_digits")).select_by_value("2")
    assert driver.find_element(By.ID, "sipr").text == "1 235"
    Select(driver.find_element(By.ID, "rounding_digits")).select_by_value("0")
    assert driver.find_element(By.ID, "sipr").text == "1 234,56789"
    Select(driver.find_element(By.ID, "growth_rounding_digits")).select_by_value("0")
    assert driver.find_element(By.ID, "growth").text == "1,234568"
    driver.execute_script('''
        const row = document.createElement('tr');row.dataset.parameterKey='energy_consumption_mln_kvt_ch';
        row.innerHTML='<td id="newValue" class="summary-year-cell" title="1234,56789">0</td>';
        document.querySelector('tbody').appendChild(row);
        document.dispatchEvent(new CustomEvent('ec-summary-rows-rendered'));
    ''')
    assert driver.find_element(By.ID, "newValue").text == "1 234,56789"
