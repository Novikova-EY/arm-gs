"""DOM regression checks; requires Selenium and a local Chrome installation."""
from pathlib import Path
from urllib.parse import quote

import pytest

pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


def load_page(browser, body):
    presentation = (ROOT / "app/static/js/ecology/formula_presentation.js").read_text(encoding="utf-8")
    bootstrap = (ROOT / "app/static/js/bootstrap.bundle.min.js").read_text(encoding="utf-8")
    tooltips = (ROOT / "app/static/js/common/info_tooltips.js").read_text(encoding="utf-8")
    page = f'''<!doctype html><meta charset="utf-8">
        <script>{presentation}</script>{body}
        <script>{bootstrap}</script><script>{tooltips}</script>'''
    browser.get("data:text/html;charset=utf-8," + quote(page))


def test_plain_formula_has_expression_explanations_and_indices(browser):
    load_page(browser, '''<i id="formula" class="bi-info-circle" data-bs-toggle="tooltip"
        title="МотхCO2 = BH · KCO2. B – расход топлива; KCO2 – коэффициент."></i>''')
    title = browser.find_element(By.ID, "formula").get_attribute("title")
    assert 'ecology-formula-expression' in title
    assert '<sub>отх</sub>' in title
    assert '<sup>H</sup>' in title
    assert title.count('<p') == 3
    assert browser.find_element(By.ID, "formula").get_attribute("tabindex") == "0"
    assert browser.find_element(By.ID, "formula").get_attribute("data-bs-toggle") == "tooltip"


def test_lowercase_variable_explanation_starts_a_separate_paragraph(browser):
    load_page(browser, '''<i id="formula" class="bi-info-circle" data-bs-html="true"
        title="М = B · q&lt;sub&gt;3&lt;/sub&gt;. q&lt;sub&gt;3&lt;/sub&gt; – потери теплоты."></i>''')
    title = browser.find_element(By.ID, "formula").get_attribute("title")
    assert title.count('<p') == 2
    assert '</p><p>q<sub>3</sub> –' in title


def test_existing_html_indices_are_preserved_without_double_formatting(browser):
    load_page(browser, '''<button id="formula" class="bi-info-circle" data-bs-html="true"
        title="М&lt;sub&gt;отх&lt;/sub&gt; = B&lt;sup&gt;H&lt;/sup&gt; · Q&lt;sub&gt;н&lt;/sub&gt;"></button>''')
    title = browser.find_element(By.ID, "formula").get_attribute("title")
    assert title.count('<sub>отх</sub>') == 1
    assert title.count('<sup>H</sup>') == 1
    assert '<sub>н</sub>' in title


def test_keyboard_focus_opens_common_tooltip(browser):
    load_page(browser, '''<button id="formula" data-bs-toggle="tooltip" title="М = В × У">
        <i class="bi bi-info-circle" aria-hidden="true"></i></button>
        <script>document.addEventListener('DOMContentLoaded', function () {
            document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
        });</script>''')
    browser.execute_script("document.getElementById('formula').focus()")
    tooltip = WebDriverWait(browser, 5).until(
        lambda driver: driver.find_element(By.CSS_SELECTOR, ".ecology-formula-tooltip .tooltip-inner")
    )
    assert tooltip.text == "М = В × У"


def test_preview_updates_without_changing_source_or_executing_html(browser):
    load_page(browser, '''<table id="ecFormulaSummaryTable"><tr data-formula-key="example"><td>
        <div class="ecology-formula-preview"></div>
        <textarea class="ec-formula-text-input">BH = В / Qн. В – расход.</textarea>
        </td></tr></table>''')
    source = browser.find_element(By.CSS_SELECTOR, "textarea")
    assert source.get_attribute("value") == "BH = В / Qн. В – расход."
    assert browser.find_element(By.CSS_SELECTOR, ".ecology-formula-preview sup").text == "H"
    draft = '<img src=x onerror="window.injected=true">\nМвыб = Мотх · (1 − η)'
    browser.execute_script('''const input = document.querySelector('textarea');
        input.value = arguments[0]; input.dispatchEvent(new Event('input', {bubbles:true}));''', draft)
    preview = browser.find_element(By.CSS_SELECTOR, ".ecology-formula-preview")
    assert '<img src=x' in preview.text
    assert not preview.find_elements(By.TAG_NAME, "img")
    assert browser.execute_script("return window.injected") is None
    assert source.get_attribute("value") == draft
    assert preview.find_element(By.TAG_NAME, "sub").text == "выб"


def test_abbreviations_and_decimal_values_are_kept(browser):
    load_page(browser, '''<i id="formula" class="bi-info-circle"
        title="М, тыс. т = В · 0,01 / 1000; У – норматив, кг/т у.т. Арктика."></i>
        <button id="filter" title="Фильтр: Электростанция"></button>''')
    title = browser.find_element(By.ID, "formula").get_attribute("title")
    assert 'М, тыс. т = В · 0,01 / 1000' in title
    assert 'кг/т у.т.' in title
    assert 'Арктика' in title
    assert browser.find_element(By.ID, "filter").get_attribute("title") == "Фильтр: Электростанция"
