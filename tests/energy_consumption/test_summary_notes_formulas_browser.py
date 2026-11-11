import json

import pytest
pytest.importorskip("selenium")
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from test_consumption_cell_styles_browser import browser, PAGES, ROOT, TEMPLATES
from app.energy_consumption.services.summary_formula_presentation import attach_summary_formula_tooltips


@pytest.fixture
def summary_page(browser, tmp_path):
    rows = []
    for index, (label, parameter, calculated, block_start, span) in enumerate([
        ("Исходная энергосистема", "energy_consumption_mln_kvt_ch", False, True, 2),
        ("Исходная энергосистема", "energy_consumption_yoy_growth_pct", True, False, 2),
        ("Расчетная энергосистема", "energy_consumption_mln_kvt_ch", True, True, 1),
    ]):
        rows.append(dict(entity_label=label, entity_kind="group", entity_depth=0,
                         entity_rowspan=span, show_entity_cell=block_start,
                         show_entity_note_cell=block_start,
                         demand_model_name="FederalDistrictEnergyConsumptionParameter" if index == 2 else "UnionEnergySystemEnergyConsumptionParameter",
                         parameter_key=parameter, parameter_label="Потребление электрической энергии" if index != 1 else "Годовой темп прироста",
                         pd_ec_formula_derived_row=calculated,
                         parent_fk_column="id_federal_district" if index == 2 else "id_union_energy_system",
                         parent_id=index + 1, year_values=["123,5"], year_numeric_tooltips=["123,4567890123456789"],
                         pd_ec_note_key=chr(97 + index) * 64, pd_ec_note_version_id=7, entity_note_text="Note " + str(index)))
    attach_summary_formula_tooltips({"summary_rows": rows})
    payload = dict(years=[2025], summary_rows=rows,
                   config=dict(can_edit_summary_cells=True, show_summary_note_col=True, start_year=2025, rounding_digits=0))
    scripts = {name: (ROOT / "app/static/js/energy_consumption" / name).read_text(encoding="utf-8")
               for name in ("consumption_live_save.js", "summary_row_notes.js", "demand_summary_client_render.js")}
    html = '''<!doctype html><meta charset="utf-8">
<button id="demandSummarySaveBtn" type="button">Сохранить</button>
<table id="powerDemandSummaryTable" data-summary-view="oes" data-rounding-digits="0" data-note-save-url="/note" data-csrf-token="csrf"><tbody id="powerDemandSummaryTbody"></tbody></table>
<script id="ec-summary-client-render-config" type="application/json">{"data_path":"/data","scope":"oes","can_edit_summary_cells":true}</script>
<script>window.posts=[];window.numericSaves=0;
document.getElementById('demandSummarySaveBtn').addEventListener('click',()=>{window.numericSaves++});
window.fetch=async function(url,options){
if(options && options.method==='POST'){window.posts.push({url,body:JSON.parse(options.body),csrf:options.headers['X-CSRFToken']});return {ok:true,json:async()=>({ok:true})};}
return {ok:true,json:async()=>(''' + json.dumps(payload, ensure_ascii=False) + ''')};};</script>'''
    for name in ("consumption_live_save.js", "summary_row_notes.js", "demand_summary_client_render.js"):
        html += "<script>" + scripts[name] + "</script>"
    path = tmp_path / "summary.html"
    path.write_text(html, encoding="utf-8")
    browser.get(path.as_uri())
    result = browser.execute_async_script('''
        const done = arguments[0];
        if (!window.__ecSummaryRowsReady) { done({error: 'Renderer did not start'}); return; }
        window.__ecSummaryRowsReady.then(() => done({html: document.querySelector('tbody').innerHTML}))
            .catch(error => done({error: String(error), html: document.querySelector('tbody').innerHTML}));
    ''')
    assert len(browser.find_elements(By.CSS_SELECTOR, "textarea.ec-summary-row-note")) == 3, result
    return browser


def test_each_client_row_has_an_editable_note_and_calculated_values_stay_readonly(summary_page):
    state = summary_page.execute_script('''return [...document.querySelectorAll('tbody tr')].map(row=>({
        notes:row.querySelectorAll('textarea.ec-summary-row-note').length,
        rowspan:row.querySelector('.ec-summary-row-note-cell').rowSpan,
        note:row.querySelector('textarea').value,
        numericInputs:row.querySelectorAll('.summary-year-cell input').length,
        formula:row.querySelector('.summary-parameter-cell .ec-formula-info')?.title || ''
    }));''')
    assert [row["notes"] for row in state] == [1, 1, 1]
    assert [row["rowspan"] for row in state] == [1, 1, 1]
    assert [row["note"] for row in state] == ["Note 0", "Note 1", "Note 2"]
    assert [row["numericInputs"] for row in state] == [1, 0, 0]
    assert state[1]["formula"] and state[2]["formula"]
    entity_icons = summary_page.find_elements(By.CSS_SELECTOR, ".summary-entity-cell .ec-formula-info")
    assert not entity_icons
    parameter_icons = summary_page.find_elements(By.CSS_SELECTOR, ".summary-parameter-cell .ec-formula-info")
    assert len(parameter_icons) == 2
    assert "=" in parameter_icons[1].get_attribute("title")


def test_calculated_row_note_autosaves_its_own_key_with_csrf(summary_page):
    note = summary_page.find_elements(By.CSS_SELECTOR, "textarea.ec-summary-row-note")[2]
    note.send_keys(Keys.CONTROL, "a")
    note.send_keys("Calculated row explanation")
    summary_page.execute_script("arguments[0].blur()", note)
    WebDriverWait(summary_page, 5).until(lambda driver: len(driver.execute_script("return window.posts")) == 1)
    post = summary_page.execute_script("return window.posts[0]")
    assert post == {"url": "/note", "body": {"row_key": "c" * 64, "value": "Calculated row explanation", "database_version_id": "7"}, "csrf": "csrf"}
    assert "is-save-success" in note.get_attribute("class")


@pytest.mark.parametrize("numeric_changed", [False, True])
def test_save_button_waits_for_notes_before_existing_numeric_save(summary_page, numeric_changed):
    summary_page.execute_script('''
        document.querySelectorAll('textarea.ec-summary-row-note')[1].value = 'Manual note';
        if (arguments[0]) document.querySelector('input.fuel-param-input').value = '200';
    ''', numeric_changed)
    summary_page.find_element(By.ID, "demandSummarySaveBtn").click()
    WebDriverWait(summary_page, 5).until(lambda driver: driver.execute_script('''
        return document.querySelectorAll('textarea.ec-summary-row-note')[1].dataset.initial === 'Manual note';
    '''))
    assert summary_page.execute_script("return window.posts[0].body.row_key") == "b" * 64
    assert summary_page.execute_script("return window.numericSaves") == (1 if numeric_changed else 0)


@pytest.mark.parametrize("template", [name for name in PAGES if name.endswith(".html") and "energy_consumption_edit" not in name])
@pytest.mark.parametrize("sipr", [False, True])
def test_no_rounding_uses_full_precision_for_every_row_in_both_modes(summary_page, template, sipr):
    source = (TEMPLATES / template).read_text(encoding="utf-8-sig")
    import re
    body = (TEMPLATES / re.search(r"include '(.*?)'", source)[1]).read_text(encoding="utf-8")
    start = body.index("var PD_EC_NORMAL_ROW_KEYS")
    end = body.index("function syncPdEcRowPickerModalOptions()", start)
    script = body[start:end]
    summary_page.execute_script("window.__pdEcSummarySiprMode = arguments[0]; window.pdEcSummaryTableStandalone=true;", sipr)
    summary_page.execute_script('''
        const tr = document.createElement('tr');
        tr.className = 'summary-row-param pd-ec-verification-row';
        tr.dataset.parameterKey = 'energy_consumption_mln_kvt_ch';
        tr.innerHTML = '<td class="summary-year-cell" title="0,000000123456789">0</td>';
        document.querySelector('tbody').appendChild(tr);
        const masked = document.createElement('tr');
        masked.className = 'summary-row-param';
        masked.dataset.parameterKey = 'energy_consumption_mln_kvt_ch';
        masked.innerHTML = '<td class="summary-year-cell summary-plan-empty pd-ec-variant-year-out" title="999,123456789"></td>';
        document.querySelector('tbody').appendChild(masked);
    ''')
    summary_page.execute_script(script + ";syncPdEcSummaryTableSiprIntegerDisplay();")
    values = summary_page.execute_script('''return [...document.querySelectorAll('tbody tr')].filter(row=>row.dataset.parameterKey==='energy_consumption_mln_kvt_ch').map(row=>{
        const cell=row.querySelector('.summary-year-cell'); return cell.querySelector('input')?.value || cell.textContent;
    });''')
    assert values == ["123,4567890123456789", "123,4567890123456789", "0,000000123456789", ""]
