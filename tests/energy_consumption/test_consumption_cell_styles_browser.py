import re
from pathlib import Path

import pytest
from flask import render_template_string

pytest.importorskip("selenium")
from selenium import webdriver


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app/templates"
PAGES = sorted(
    str(path.relative_to(TEMPLATES)).replace("\\", "/")
    for path in (TEMPLATES / "energy_consumption/pages").glob("*.html")
    if re.search(r"include 'energy_consumption/pages/.*_body.html'", path.read_text(encoding="utf-8-sig"))
)
PAGES.append("energy_consumption/energy_consumption_edit.html")


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.mark.parametrize("template", PAGES)
def test_styles_reach_active_pages_and_only_affect_value_fields(app, browser, tmp_path, template):
    source = (TEMPLATES / template).read_text(encoding="utf-8-sig")
    assert "extends 'base.html'" in source
    body_include = re.search(r"include '(.*?)'", source)
    body = (TEMPLATES / body_include[1]).read_text(encoding="utf-8-sig") if body_include else source
    assert "_cell_editing_legend.html" not in body

    app.add_url_rule("/style-test", endpoint="energy_consumption_bp.style_test", view_func=lambda: "")
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    head = re.search(r"<head>(.*?)</head>", base, re.S)[1]
    with app.test_request_context("/style-test"):
        rendered_head = render_template_string(head)
    assert "css/energy_consumption_live_save.css?v=12" in rendered_head
    assert "js/energy_consumption/year_cell_width.js?v=1" in rendered_head
    with app.test_request_context("/unrelated-page"):
        assert "energy_consumption_live_save.css" not in render_template_string(head)

    styles = "\n".join((ROOT / "app/static/css" / name).read_text(encoding="utf-8") for name in (
        "bootstrap.min.css", "style.css", "table_headers.css",
    ))
    legacy = "\n".join(re.findall(r"<style>(.*?)</style>", body, re.S))
    feature = (ROOT / "app/static/css/energy_consumption_live_save.css").read_text(encoding="utf-8")
    page = tmp_path / "cells.html"
    page.write_text('''<!doctype html><meta charset="utf-8">
<style>''' + styles + '''</style><style id="cell-styles">''' + feature + '''</style><style>''' + legacy + '''</style>
<table id="powerDemandSummaryTable" data-ec-unify-block-bg="1" class="power-demand-summary-table fuel-params-edit-table table table-striped table-hover">
<thead><tr><th id="heading">РџРѕРєР°Р·Р°С‚РµР»СЊ</th><th>Р—РЅР°С‡РµРЅРёРµ</th></tr></thead><tbody>
<tr class="summary-row-param" data-ec-block-stripe="0"><td id="label" style="height: 96px">РџРѕС‚СЂРµР±Р»РµРЅРёРµ СЌР»РµРєС‚СЂРёС‡РµСЃРєРѕР№ СЌРЅРµСЂРіРёРё<br>РІС‹СЃРѕРєР°СЏ СЃС‚СЂРѕРєР°</td><td class="summary-year-cell"><input id="editable" class="form-control fuel-param-input" value="123,4"></td></tr>
<tr class="summary-row-param" data-ec-block-stripe="0"><td>Р Р°СЃС‡РµС‚</td><td id="calculated" class="summary-year-cell">234,5</td></tr>
<tr><td>Р Р°СЃС‡РµС‚РЅР°СЏ РїСЂРѕРІРµСЂРєР°</td><td class="summary-year-cell"><span id="calculated-highlight" class="text-danger">0,01</span></td></tr>
<tr class="summary-row-param" data-ec-block-stripe="0"><td>РўРѕР»СЊРєРѕ С‡С‚РµРЅРёРµ</td><td class="summary-year-cell"><input id="readonly" class="form-control pd-coeff-display-mw" readonly value="345,6"></td></tr>
<tr><td><select id="perimeter" class="form-select"><option>Р‘РµР· РќРў</option></select></td><td class="summary-year-cell summary-plan-empty" id="unavailable"></td></tr>
<tr><td>РЎРѕС…СЂР°РЅРµРЅРѕ</td><td class="summary-year-cell"><input id="saved" class="form-control fuel-param-input is-save-success" value="111"></td></tr>
<tr><td>РћС€РёР±РєР°</td><td class="summary-year-cell"><input id="error" class="form-control fuel-param-input is-save-error" value="222"></td></tr>
<tr><td style="height: 110px">РџСЂРёРјРµС‡Р°РЅРёРµ СЂР°СЃС‡РµС‚РЅРѕР№ СЃС‚СЂРѕРєРё</td><td class="ec-summary-row-note-cell"><textarea id="note" class="form-control ec-summary-row-note">РўРµРєСЃС‚</textarea></td></tr>
</tbody></table>
<table id="coefficientStyleTestTable" class="table table-striped table-hover pd-coeff-year-seg-table"><tbody>
<tr class="summary-kind-group"><td class="summary-parameter-cell" id="group-parameter">Группа</td><td class="summary-year-cell" id="group-year">2025</td><td class="summary-coeff-mixin-cell" id="group-mixin">Среднее</td></tr>
<tr class="summary-kind-child"><td class="summary-parameter-cell" id="child-parameter">Показатель</td><td class="summary-year-cell" id="child-year">2025</td><td class="summary-coeff-mixin-cell" id="child-mixin">Среднее</td></tr>
</tbody></table>
<table id="power-demand-edit-table" class="power-demand-params-table table"><tbody><tr>
<td><select id="year" class="form-select"><option>2025</option></select></td>
<td><input id="detail-editable" class="form-control" name="ec_mln[]" value="456,7"></td>
<td><input id="detail-readonly" class="form-control bg-light" name="ec_sipr[]" readonly value="567,8"></td>
<td style="height: 100px"><textarea id="detail-note" class="form-control" name="note[]">РўРµРєСЃС‚</textarea></td>
</tr></tbody></table>''', encoding="utf-8")
    browser.get(page.as_uri())
    state = browser.execute_script('''
        const read = id => {
            const s = getComputedStyle(document.getElementById(id));
            return { background: s.backgroundColor, image: s.backgroundImage,
                border: s.borderStyle, color: s.color, outline: s.outlineColor,
                outlineStyle: s.outlineStyle };
        };
        const unchanged = ['heading', 'label', 'perimeter', 'year', 'unavailable'];
        const before = unchanged.map(read);
        document.getElementById('cell-styles').disabled = true;
        const baseline = unchanged.map(read);
        document.getElementById('cell-styles').disabled = false;
        const values = Object.fromEntries(['label', 'editable', 'calculated', 'readonly', 'calculated-highlight',
            'detail-editable', 'detail-readonly'].map(id => [id, read(id)]));
        const gaps = id => {
            const field = document.getElementById(id);
            const a = field.getBoundingClientRect();
            const b = field.closest('td').getBoundingClientRect();
            return [a.left-b.left, a.top-b.top, b.right-a.right, b.bottom-a.bottom];
        };
        document.getElementById('saved').focus();
        values.saved = read('saved');
        const savedGaps = gaps('saved');
        document.getElementById('error').focus();
        values.error = read('error');
        const fieldGaps = ['editable', 'detail-editable', 'note', 'detail-note', 'error'].map(gaps);
        fieldGaps.push(savedGaps);
        const coefficientRows = ['group', 'child'].map(prefix =>
            ['parameter', 'year', 'mixin'].map(cell => read(prefix + '-' + cell).background));
        return { before, baseline, values, fieldGaps, coefficientRows };
    ''')
    assert state["before"] == state["baseline"]
    assert state["coefficientRows"] == [
        ["rgb(238, 245, 255)"] * 3,
        ["rgb(251, 252, 255)"] * 3,
    ]
    values = state["values"]
    for name in ("editable", "detail-editable"):
        assert values[name]["background"] == "rgb(255, 255, 255)"
        assert values[name]["border"] == "solid"
    assert values["calculated"]["background"] == values["label"]["background"]
    assert values["calculated"]["image"] == values["label"]["image"]
    for name in ("calculated", "readonly", "detail-readonly"):
        assert values[name]["color"] == "rgb(0, 0, 0)"
    for name in ("readonly", "detail-readonly"):
        assert "rgb(233, 237, 241)" in values[name]["image"]
    for name, gaps in zip(("editable", "detail-editable", "note", "detail-note", "error", "saved"), state["fieldGaps"]):
        if name in ("editable", "detail-editable", "error", "saved"):
            assert all(gap >= 4 for gap in gaps), (name, gaps)
        else:
            assert all(abs(gap) <= 2 for gap in gaps), (name, gaps)
    assert values["calculated-highlight"]["color"] == "rgb(0, 0, 0)"
    assert values["readonly"]["border"] == "none"
    assert values["saved"]["background"] == "rgb(209, 231, 221)"
    assert values["error"]["background"] == "rgb(248, 215, 218)"
    assert values["saved"]["outline"] == "rgb(25, 135, 84)"
    assert values["error"]["outline"] == "rgb(220, 53, 69)"
    assert values["saved"]["outlineStyle"] == values["error"]["outlineStyle"] == "solid"
