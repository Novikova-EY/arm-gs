import re
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import render_template_string

pytest.importorskip("selenium")
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from test_consumption_cell_styles_browser import browser, ROOT
from test_growth_rounding import ROUNDING_TEMPLATES


@pytest.mark.parametrize("template", ROUNDING_TEMPLATES, ids=lambda path: path.stem)
def test_controls_are_ordered_and_year_form_keeps_growth_precision(app, browser, tmp_path, template):
    source = template.read_text(encoding="utf-8")
    start = source.index("{% include 'energy_consumption/_growth_rounding.html' %}")
    end = source.index("</select>", start) + len("</select>")
    controls = source[start:end] + "</div>"
    with app.test_request_context("/energy_consumption/?rounding_digits=1"):
        rendered = render_template_string(controls, rounding_digits=1, rd=1)
    script = (ROOT / "app/static/js/energy_consumption/growth_rounding.js").read_text(encoding="utf-8")
    rendered = re.sub(r'<script[^>]+growth_rounding\.js[^>]*></script>', lambda match: '<script>' + script + '</script>', rendered)
    css = (ROOT / "app/static/css/bootstrap.min.css").read_text(encoding="utf-8")
    path = tmp_path / "rounding.html"
    path.write_text('''<!doctype html><meta charset="utf-8"><style>''' + css + '''</style>
<form id="powerDemandSummaryYearForm"><input name="start_year" value="2024"></form>
<table id="powerDemandSummaryTable"><tbody>
<tr data-parameter-key="energy_consumption_mln_kvt_ch"><td class="summary-year-cell"><input id="dirty" value="123,45" data-initial="100"></td></tr>
<tr data-parameter-key="energy_consumption_yoy_growth_pct"><td class="summary-year-cell" title="1,23456789">1,23</td></tr>
<tr data-parameter-key="energy_consumption_sipr_yoy_growth_pct"><td class="summary-year-cell" data-bs-original-title="-2,3456789"><span class="text-danger">-2,35</span></td></tr>
<tr data-parameter-key="energy_consumption_yoy_growth_pct"><td id="masked" class="summary-year-cell summary-plan-empty pd-ec-variant-year-out"></td></tr>
</tbody></table><script>window.pageToken='original';</script>
<div class="d-flex align-items-center gap-2">''' + rendered + '''</div>''', encoding="utf-8")
    browser.get(path.as_uri() + "?rounding_digits=1&start_year=2024")
    growth = browser.find_element(By.ID, "growth_rounding_digits")
    general = browser.find_element(By.ID, "rounding_digits")
    assert Select(growth).first_selected_option.get_attribute("value") == "2"
    assert Select(general).first_selected_option.get_attribute("value") == "1"
    assert growth.rect["x"] + growth.rect["width"] <= general.rect["x"]
    assert browser.execute_script('''return new FormData(document.getElementById('powerDemandSummaryYearForm')).get('growth_rounding_digits');''') == "2"
    Select(growth).select_by_value("3")
    WebDriverWait(browser, 5).until(lambda driver: "growth_rounding_digits=3" in driver.current_url)
    params = parse_qs(urlsplit(browser.current_url).query)
    assert params == {"rounding_digits": ["1"], "start_year": ["2024"], "growth_rounding_digits": ["3"]}
    for digits, expected in [("3", ["1,235", "-2,346"]), ("1", ["1,2", "-2,3"]),
                             ("2", ["1,23", "-2,35"]), ("-1", ["1", "-2"]),
                             ("0", ["1,234568", "-2,345679"])]:
        Select(growth).select_by_value(digits)
        assert browser.execute_script('''return [...document.querySelectorAll('tr[data-parameter-key$="yoy_growth_pct"] .summary-year-cell:not(#masked)')].map(cell=>cell.textContent);''') == expected
        assert browser.execute_script("return window.pageToken") == "original"
        assert browser.find_element(By.ID, "dirty").get_attribute("value") == "123,45"
        assert browser.find_element(By.ID, "masked").text == ""
    Select(growth).select_by_value("3")
    browser.execute_script('''
        const row = document.createElement('tr');
        row.dataset.parameterKey = 'energy_consumption_yoy_growth_pct';
        row.innerHTML = '<td id="newGrowth" class="summary-year-cell" title="9007199254740993,1254">0</td>';
        document.querySelector('tbody').appendChild(row);
        document.dispatchEvent(new CustomEvent('ec-summary-rows-rendered'));
    ''')
    assert browser.find_element(By.ID, "newGrowth").text == "9 007 199 254 740 993,125"
