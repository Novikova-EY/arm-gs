import re

import pytest
from flask import render_template_string

pytest.importorskip("selenium")
from selenium.webdriver.support.ui import WebDriverWait

from test_consumption_cell_styles_browser import browser, PAGES, ROOT, TEMPLATES


@pytest.mark.parametrize("template", [*PAGES, "energy_consumption/energy_consumption_summary.html"])
def test_year_values_do_not_wrap_or_clip_and_tables_scroll(app, browser, tmp_path, template):
    source = (TEMPLATES / template).read_text(encoding="utf-8-sig")
    include = re.search(r"include '(.*?)'", source)
    body = (TEMPLATES / include[1]).read_text(encoding="utf-8-sig") if include else source
    with app.test_request_context():
        legacy = render_template_string("\n".join(re.findall(r"<style>(.*?)</style>", body, re.S)),
                                        summary_entity_col_w="14rem", summary_parameter_col_w="14rem",
                                        summary_hist_col_w="8rem", summary_route_variant="coeff")
    css = "\n".join((ROOT / "app/static/css" / name).read_text(encoding="utf-8") for name in (
        "bootstrap.min.css", "style.css", "table_headers.css", "energy_consumption_live_save.css"))
    script = (ROOT / "app/static/js/energy_consumption/year_cell_width.js").read_text(encoding="utf-8")
    long_number = "123 456 789 012 345,12345678901234567890"
    page = tmp_path / "wide-values.html"
    page.write_text('''<!doctype html><meta charset="utf-8"><style>''' + css + legacy + '''
body { margin: 0; padding: 10px; }
</style><div id="powerDemandSummaryScrollWrap" class="table-responsive power-demand-summary-scroll">
<table id="powerDemandSummaryTable" class="table power-demand-summary-table fuel-params-edit-table pd-coeff-year-seg-table pd-coeff-hide-k-columns">
<colgroup><col class="summary-col-entity"><col class="summary-col-parameter"><col class="summary-col-year-mw"><col class="summary-col-year-mw"><col class="summary-col-year-mw"><col class="summary-col-note"></colgroup>
<thead><tr><th>Энергосистема</th><th>Показатель</th><th>2024</th><th>2025</th><th>2026</th><th>Примечание</th></tr></thead>
<tbody><tr data-parameter-key="peak_datetime"><td class="summary-entity-cell">Энергосистема</td><td class="summary-parameter-cell">Значение</td>
<td id="plain" class="summary-year-cell">''' + long_number + '''</td>
<td class="summary-year-cell"><span id="highlight" class="text-danger text-wrap">''' + long_number + '''</span></td>
<td class="summary-year-cell"><textarea id="date" class="form-control fuel-param-input power-demand-summary-datetime-field">31.12.2025 23:59</textarea></td>
<td class="ec-summary-row-note-cell"><textarea class="form-control ec-summary-row-note">Примечание с переносами строк</textarea></td></tr>
<tr><td class="summary-entity-cell">Энергосистема</td><td class="summary-parameter-cell">Ввод</td>
<td class="summary-year-cell"><input id="numeric" class="form-control fuel-param-input" value="1"></td>
<td class="summary-year-cell"><input id="readonly" class="form-control" readonly value="''' + long_number + '''"></td>
<td class="summary-year-cell pd-ec-year-col-hidden" style="display:none">Скрытый год</td><td></td></tr></tbody></table></div>
<div id="detail-wrap" class="table-responsive"><table id="power-demand-edit-table" class="table power-demand-params-table"><tbody><tr>
<td>2025</td><td><input id="detail" class="form-control" name="ec_mln[]" value="''' + long_number + '''"></td>
<td><input id="sipr" class="form-control" name="ec_sipr[]" readonly value="''' + long_number + '''"></td>
<td><textarea name="note[]" class="form-control">Примечание</textarea></td></tr></tbody></table></div>
<div id="view-wrap" class="table-responsive"><table id="power-demand-view-table" class="table power-demand-params-table"><tbody><tr>
<td>2025</td><td title="Full precision">''' + long_number + '''</td><td title="Full precision">''' + long_number + '''</td>
<td class="text-break">Примечание с переносами</td></tr></tbody></table></div>
<script>''' + script + '''</script>''', encoding="utf-8")
    browser.set_window_size(640, 800)
    browser.get(page.as_uri())
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script('''
        return document.getElementById('numeric').closest('td').style.getPropertyValue('--ec-year-field-width') !== '';
    '''))
    browser.execute_script('''
        const field = document.getElementById('numeric');
        field.value = arguments[0];
        field.dispatchEvent(new Event('input', {bubbles:true}));
        const row = document.createElement('tr');
        row.innerHTML = '<td>2026</td><td><input id="added" class="form-control" name="ec_mln[]"></td><td></td><td></td>';
        row.querySelector('input').value = arguments[0] + '1234567890';
        document.querySelector('#power-demand-edit-table tbody').appendChild(row);
    ''', long_number)
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script('''
        return document.getElementById('added').closest('td').style.getPropertyValue('--ec-year-field-width') !== '';
    '''))
    state = browser.execute_script('''
        const ids = ['numeric', 'readonly', 'date', 'detail', 'sipr', 'added'];
        const fields = ids.map(id => {
            const field = document.getElementById(id);
            const cell = field.closest('td');
            return {id, fits: field.scrollWidth <= field.clientWidth + 1,
                withinCell: field.getBoundingClientRect().right <= cell.getBoundingClientRect().right + 1,
                whiteSpace: getComputedStyle(field).whiteSpace};
        });
        const lines = ['plain', 'highlight'].map(id => {
            const element = document.getElementById(id);
            const range = document.createRange(); range.selectNodeContents(element);
            return range.getClientRects().length;
        });
        const wrappers = ['powerDemandSummaryScrollWrap', 'detail-wrap', 'view-wrap'].map(id => {
            const wrap = document.getElementById(id);
            wrap.scrollLeft = 200;
            return {id, overflow: getComputedStyle(wrap).overflowX,
                scrolls: wrap.scrollWidth > wrap.clientWidth && wrap.scrollLeft > 0};
        });
        const fontSizes = [...document.querySelectorAll('tbody td, tbody input, tbody textarea')].map(el => parseFloat(getComputedStyle(el).fontSize));
        return {fields, lines, wrappers, fontSizes, noteWhiteSpace: getComputedStyle(document.querySelector('.ec-summary-row-note')).whiteSpace,
            hidden: getComputedStyle(document.querySelector('.pd-ec-year-col-hidden')).display,
            pageFits: document.documentElement.scrollWidth <= window.innerWidth};
    ''')
    assert all(field["fits"] and field["withinCell"] and field["whiteSpace"] == "nowrap" for field in state["fields"]), state
    assert state["lines"] == [1, 1], state
    assert all(wrap["overflow"] == "auto" and wrap["scrolls"] for wrap in state["wrappers"]), state["wrappers"]
    assert state["noteWhiteSpace"] == "pre-wrap"
    assert state["hidden"] == "none"
    assert state["pageFits"], state
    assert state["fontSizes"] == pytest.approx([18.4] * len(state["fontSizes"]))
