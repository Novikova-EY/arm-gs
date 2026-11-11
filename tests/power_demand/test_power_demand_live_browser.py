from pathlib import Path
from threading import Thread

import pytest
from flask import render_template, request
from flask_wtf.csrf import generate_csrf
from werkzeug.serving import make_server

from test_power_demand_data_refresh import load_app, load_db
from app.power_demand.services import data_refresh_services as refresh
from app.common.services.help_services import format_decimal_trim_for_display

pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--host-resolver-rules=MAP cdn.jsdelivr.net ~NOTFOUND")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.fixture
def load_server(load_app):
    server = make_server("127.0.0.1", 0, load_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield load_app, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def open_page(browser, url):
    browser.get(url + "/test-login")
    token = browser.find_element(By.TAG_NAME, "body").text
    browser.get(url + "/power_demand/russia/?rounding_digits=2#table")
    return token


def test_external_changes_own_saves_and_refresh_guard(browser, load_server):
    app, url = load_server

    def save():
        refresh.publish_power_demand_data_change()
        return {"ok": True}

    app.view_functions["power_demand_bp.demand_summary_save_cell"] = save
    token = open_page(browser, url)
    script = '''const done = arguments[arguments.length - 1];
        window.powerDemandSaveFetch('/power_demand/summary/cell', {
            method: 'POST', headers: {'X-CSRFToken': arguments[0], 'X-Requested-With': 'XMLHttpRequest'}
        }).then(() => {window.dispatchEvent(new Event('focus')); done();});'''
    browser.execute_async_script(script, token)
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert "btn-warning" in button.get_attribute("class")
    refresh.publish_power_demand_data_change()
    browser.execute_script("window.dispatchEvent(new Event('focus'))")
    WebDriverWait(browser, 5).until(lambda d: "btn-danger" in button.get_attribute("class"))
    browser.execute_async_script(script, token)
    assert "btn-danger" in button.get_attribute("class")
    browser.execute_script('''const field = document.getElementById('test-value');
        field.value = '999'; field.dispatchEvent(new Event('input', {bubbles:true}));''')
    button.click()
    browser.switch_to.alert.dismiss()
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"
    button.click()
    browser.switch_to.alert.accept()
    WebDriverWait(browser, 5).until(lambda d: d.find_element(By.ID, "test-value").get_attribute("value") == "100")
    assert browser.current_url.endswith("?rounding_digits=2#table")


@pytest.mark.parametrize("kind", ["summary", "detail", "ozp"])
def test_value_styles_with_legacy_css(browser, tmp_path, kind):
    root = Path(__file__).resolve().parents[2] / "app/static"
    table_id = {"summary": "powerDemandSummaryTable", "detail": "power-demand-edit-table", "ozp": "ozpMaximaTable"}[kind]
    feature = (root / "css/energy_consumption_live_save.css").read_text(encoding="utf-8")
    feature += (root / "css/power_demand_live_save.css").read_text(encoding="utf-8").split(";", 1)[1]
    page = tmp_path / "styles.html"
    page.write_text('''<!doctype html><meta charset="utf-8"><style>'''
        + (root / "css/bootstrap.min.css").read_text(encoding="utf-8")
        + "</style><style>" + feature + "</style><style>"
        + (root / "css/power_demand_summary_page.css").read_text(encoding="utf-8") + '''</style>
        <div style="width:390px"><table id="''' + table_id + '''" data-active-summary="oes" class="power-demand-summary-table fuel-params-edit-table table" style="table-layout:fixed;width:390px"><colgroup><col style="width:130px"><col style="width:130px"><col style="width:130px"></colgroup><tbody>
        <tr><td style="height:100px">Показатель</td><td class="summary-year-cell"><input id="editable" class="form-control fuel-param-input" name="p_max[]" value="100"></td></tr>
        <tr><td>Расчет</td><td id="calculated" class="summary-year-cell">200</td></tr>
        <tr><td>Успех</td><td class="summary-year-cell pd-summary-cell-save-success"><input id="saved" class="form-control fuel-param-input is-save-success" value="300"></td></tr>
        <tr><td>Ошибка</td><td class="summary-year-cell pd-summary-cell-save-error"><input id="error" class="form-control fuel-param-input is-save-error" value="400"></td></tr>
        <tr data-parameter-key="peak_datetime">
        <td id="date-display" class="summary-year-cell power-demand-view-datetime-cell">10.01.2024 18:00</td>
        <td class="summary-year-cell pd-summary-control-cell"><textarea id="date-field" data-initial="10.01.2024 18:00" class="form-control fuel-param-input power-demand-summary-datetime-field power-demand-edit-datetime-field" data-parameter-key="peak_datetime" name="dt[]" rows="2">10.01.2024 18:00</textarea></td>
        <td class="summary-year-cell pd-summary-control-cell"><textarea id="short-date-field" class="form-control fuel-param-input power-demand-summary-datetime-field power-demand-edit-datetime-field" data-parameter-key="peak_datetime" name="dt[]" rows="2">2024</textarea></td>
        </tr></tbody></table></div><script>'''
        + (root / "js/power_demand/datetime_fields.js").read_text(encoding="utf-8")
        + "</script>", encoding="utf-8")
    browser.get(page.as_uri())
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script('''
        return document.getElementById('date-field').style.getPropertyValue('--pd-datetime-height') !== '';
    '''))
    state = browser.execute_script('''const read = id => {
        const el = document.getElementById(id), s = getComputedStyle(el);
        return {bg:s.backgroundColor, image:s.backgroundImage, border:s.borderStyle,
                height:el.offsetHeight, cell:el.closest('td').clientHeight};};
        const rects = id => {
            const field = document.getElementById(id).getBoundingClientRect();
            const cell = document.getElementById(id).closest('td').getBoundingClientRect();
            return [field.left-cell.left, field.top-cell.top, cell.right-field.right, cell.bottom-field.bottom];
        };
        return {edit:read('editable'), calc:read('calculated'), saved:read('saved'), error:read('error'),
            gaps:{edit:rects('editable'), saved:rects('saved'), error:rects('error')}};''')
    assert state["edit"]["bg"] == "rgb(255, 255, 255)"
    assert state["edit"]["border"] == "solid"
    for gaps in state["gaps"].values():
        assert all(gap >= 4 for gap in gaps), gaps
    if kind != "detail":
        assert "rgb(233, 237, 241)" in state["calc"]["image"]
    assert state["saved"]["bg"] == "rgb(209, 231, 221)"
    assert state["error"]["bg"] == "rgb(248, 215, 218)"
    date = browser.execute_script('''
        const cell = document.getElementById('date-display');
        const text = cell.firstChild, range = document.createRange();
        range.setStart(text, 0); range.setEnd(text, 10);
        const date = Array.from(range.getClientRects());
        range.setStart(text, 11); range.setEnd(text, 16);
        const time = Array.from(range.getClientRects());
        const field = document.getElementById('date-field'), style = getComputedStyle(field);
        return {dateLines:date.length, timeLines:time.length,
            timeBelow:time[0].top > date[0].top,
            whitespace:style.whiteSpace, wordBreak:style.wordBreak, overflowWrap:style.overflowWrap,
            clipped:field.scrollHeight > field.clientHeight, value:field.value,
            position:style.position, overflowX:style.overflowX, overflowY:style.overflowY,
            resize:style.resize};
    ''')
    assert date == {
        "dateLines": 1, "timeLines": 1, "timeBelow": True,
        "whitespace": "pre-wrap", "wordBreak": "keep-all", "overflowWrap": "normal",
        "clipped": False, "value": "10.01.2024\n18:00",
        "position": "static", "overflowX": "hidden", "overflowY": "hidden", "resize": "none",
    }
    growth = browser.execute_async_script('''
        const done = arguments[arguments.length - 1];
        const settle = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        (async () => {
            const field = document.getElementById('date-field'), cell = field.closest('td');
            const short = document.getElementById('short-date-field');
            const fillsRow = () => [field, short].every(el => Math.abs(el.offsetHeight - el.closest('td').clientHeight) <= 2);
            const initial = cell.getBoundingClientRect().height;
            const initiallyFilled = fillsRow();
            const centered = parseFloat(getComputedStyle(short).paddingTop) > parseFloat(getComputedStyle(field).paddingTop);
            field.focus();
            field.value = '10.01.2024\\n18:00\\n19:00\\n20:00';
            field.dispatchEvent(new Event('input', {bubbles:true}));
            await settle();
            const expanded = cell.getBoundingClientRect().height;
            const visible = field.scrollHeight <= field.clientHeight;
            const expandedFilled = fillsRow();
            const withinCell = field.getBoundingClientRect().bottom <= cell.getBoundingClientRect().bottom;
            field.value = '10.01.2024 18:00';
            field.dispatchEvent(new Event('input', {bubbles:true}));
            await settle();
            const restored = cell.getBoundingClientRect().height;
            const table = field.closest('table');
            table.parentElement.style.width = '780px';
            table.style.width = '780px';
            table.querySelectorAll('col').forEach(col => {col.style.width = '260px';});
            window.dispatchEvent(new Event('resize'));
            await settle();
            const widened = cell.getBoundingClientRect().height;
            const display = document.getElementById('date-display');
            const range = document.createRange();
            range.setStart(display.firstChild, 0); range.setEnd(display.firstChild, 10);
            const dateRect = range.getBoundingClientRect();
            range.setStart(display.firstChild, 11); range.setEnd(display.firstChild, 16);
            const timeRect = range.getBoundingClientRect();
            done({grows:expanded > initial, visible, withinCell, shrinks:restored < expanded,
                staysTwoLines:widened === restored && field.value === '10.01.2024\\n18:00',
                readonlyTwoLines:timeRect.top > dateRect.top,
                initialMatches:field.value === field.dataset.initial, yearUnchanged:short.value === '2024',
                initiallyFilled, expandedFilled, widenedFilled:fillsRow(), centered,
                position:getComputedStyle(field).position});
        })();
    ''')
    assert growth == {
        "grows": True, "visible": True, "withinCell": True, "shrinks": True,
        "staysTwoLines": True, "readonlyTwoLines": True, "initialMatches": True,
        "yearUnchanged": True, "initiallyFilled": True, "expandedFilled": True,
        "widenedFilled": True, "centered": True, "position": "static",
    }


def test_hierarchy_row_colors_match_consumption_summary(browser, tmp_path):
    root = Path(__file__).resolve().parents[2] / "app/static"
    template = (root.parent / "templates/power_demand/power_demand_summary.html").read_text(encoding="utf-8")
    assert "power_demand_summary_page.css') }}?v=7" in template

    styles = (root / "css/bootstrap.min.css").read_text(encoding="utf-8")
    styles += (root / "css/energy_consumption_live_save.css").read_text(encoding="utf-8")
    styles += (root / "css/power_demand_live_save.css").read_text(encoding="utf-8").split(";", 1)[1]
    styles += (root / "css/power_demand_summary_page.css").read_text(encoding="utf-8")
    page = tmp_path / "hierarchy-colors.html"
    page.write_text('''<!doctype html><meta charset="utf-8"><style>''' + styles + '''</style>
        <table id="powerDemandSummaryTable" data-active-summary="oes" class="table table-striped table-hover">
        <tbody>
        <tr class="summary-kind-group"><td id="group-label">ОЭС</td><td id="group-year" class="summary-year-cell">100</td></tr>
        <tr class="summary-kind-child"><td id="child-label">Регион</td><td id="child-year" class="summary-year-cell">90</td></tr>
        <tr class="pd-pd-verify-for-row"><td id="verify-label">Проверка</td><td id="verify-year" class="summary-year-cell">0</td></tr>
        <tr class="pd-pd-calc-max-row"><td id="calc-label">Максимум</td><td id="calc-year" class="summary-year-cell">120</td></tr>
        <tr class="pd-pd-chi-row"><td id="chi-label">ЧЧИ</td><td id="chi-year" class="summary-year-cell">1</td></tr>
        <tr class="pd-pd-ee-row"><td id="ee-label">Потребление</td><td id="ee-year" class="summary-year-cell">200</td></tr>
        </tbody></table>''', encoding="utf-8")
    browser.get(page.as_uri())
    state = browser.execute_script('''
        const read = id => {
            const style = getComputedStyle(document.getElementById(id));
            return {background:style.backgroundColor, image:style.backgroundImage};
        };
        return Object.fromEntries(['group-label', 'group-year', 'child-label', 'child-year',
            'verify-label', 'verify-year', 'calc-label', 'calc-year', 'chi-label', 'chi-year',
            'ee-label', 'ee-year'].map(id => [id, read(id)]));
    ''')
    for label, year, color in (
        ("group-label", "group-year", "rgb(238, 245, 255)"),
        ("child-label", "child-year", "rgb(251, 252, 255)"),
        ("verify-label", "verify-year", "rgb(226, 236, 247)"),
        ("calc-label", "calc-year", "rgb(227, 239, 232)"),
        ("chi-label", "chi-year", "rgb(245, 232, 220)"),
        ("ee-label", "ee-year", "rgb(248, 233, 233)"),
    ):
        assert state[label]["background"] == state[year]["background"] == color
        assert state[year]["image"] == "none"


def test_datetime_formatting_preserves_save_state_and_caret(browser, tmp_path):
    root = Path(__file__).resolve().parents[2] / "app/static"
    page = tmp_path / "datetime.html"
    page.write_text('''<!doctype html><meta charset="utf-8">
        <table id="powerDemandSummaryTable"><tbody>
        <tr data-parameter-key="peak_datetime">
        <td class="summary-hist-cell"> 10.01.2024 18:00 </td>
        <td><textarea id="date-field" name="dt[]" data-initial="10.01.2024 18:00">10.01.2024 18:00</textarea></td>
        </tr><tr><td><textarea id="note-field">10.01.2024 18:00</textarea></td></tr>
        </tbody></table><script>
        window.dateEvents = {input:0, change:0};
        ['input', 'change'].forEach(type => document.addEventListener(type, () => window.dateEvents[type]++));
        </script><script>'''
        + (root / "js/power_demand/datetime_fields.js").read_text(encoding="utf-8")
        + "</script>", encoding="utf-8")
    browser.get(page.as_uri())
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script('''
        return document.getElementById('date-field').value.includes('\\n');
    '''))
    state = browser.execute_async_script('''
        const done = arguments[arguments.length - 1];
        const settle = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        (async () => {
            const field = document.getElementById('date-field');
            const initiallyClean = field.value === field.dataset.initial;
            const noInitialEvents = window.dateEvents.input === 0 && window.dateEvents.change === 0;
            field.focus();
            field.value = '12.01.2024 19:30';
            field.setSelectionRange(11, 16);
            field.dispatchEvent(new Event('input', {bubbles:true}));
            await settle();
            const typed = field.value === '12.01.2024\\n19:30';
            const caretKept = field.selectionStart === 11 && field.selectionEnd === 16;
            const stillDirty = field.value !== field.dataset.initial;
            field.dataset.initial = '12.01.2024 19:30';
            await settle();
            const savedClean = field.value === field.dataset.initial;
            const row = field.closest('tr').cloneNode(true);
            const added = row.querySelector('textarea');
            added.id = 'added-date';
            added.value = '13.01.2024 20:00';
            added.dataset.initial = added.value;
            field.closest('tbody').append(row);
            await settle();
            done({initiallyClean, noInitialEvents, typed, caretKept, stillDirty, savedClean,
                addedFormatted:added.value === '13.01.2024\\n20:00' && added.value === added.dataset.initial,
                readonlyFormatted:row.querySelector('td').textContent === '10.01.2024\\n18:00',
                noteUntouched:document.getElementById('note-field').value === '10.01.2024 18:00',
                events:window.dateEvents});
        })();
    ''')
    assert state == {
        "initiallyClean": True, "noInitialEvents": True, "typed": True, "caretKept": True,
        "stillDirty": True, "savedClean": True, "addedFormatted": True,
        "readonlyFormatted": True, "noteUntouched": True, "events": {"input": 1, "change": 0},
    }


@pytest.mark.parametrize("kind", ["detail", "ozp", "ozp_date", "formula"])
def test_live_save_success_error_recovery_and_no_red_refresh(browser, load_server, kind):
    app, url = load_server
    app.config["SAVE_ERROR"] = False
    app.config["SAVED_VALUES"] = []
    table = {
        "detail": '''<form id="demand-params-form" method="POST">
          <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
          <input type="hidden" name="rounding_digits" value="1">
          <table id="power-demand-edit-table"><tbody id="demand-rows">
          {% for blank in [false,true] %}<tr {% if blank %}class="table-light"{% endif %}>
          <td><select name="slice_year[]"><option value="2024">2024</option></select></td>
          <td><input class="form-control" name="p_max[]" value="100"><input type="hidden" name="p_max_db[]" value="100"></td>
          <td><input type="hidden" name="row_id[]" value="{{ '' if blank else '1' }}"></td></tr>{% endfor %}
          </tbody></table><button type="submit">Сохранить</button></form>
          <script src="/static/js/power_demand/demand_detail_live_save.js"></script>''',
        "ozp": '''<table id="ozpMaximaTable" data-save-url="/power_demand/ozp_maxima/save"><tbody><tr><td>
          <input class="form-control fuel-param-input" data-parameter-key="max_power" data-slice="2024" value="100">
          </td></tr></tbody></table><button id="ozpMaximaSaveBtn">Сохранить</button>
          <script>window.__ozpMaximaCsrfToken = {{ csrf_token|tojson }};</script>
          <script src="/static/js/power_demand/ozp_max_power.js" defer></script>''',
        "ozp_date": '''<table id="ozpMaximaTable" data-save-url="/power_demand/ozp_maxima/save"><tbody><tr><td>
          <textarea class="form-control fuel-param-input" data-parameter-key="peak_datetime" data-slice="2024" rows="2">09.01.2024 18:00</textarea>
          </td></tr></tbody></table><button id="ozpMaximaSaveBtn">Сохранить</button>
          <script>window.__ozpMaximaCsrfToken = {{ csrf_token|tojson }};</script>
          <script src="/static/js/power_demand/ozp_max_power.js" defer></script>''',
        "formula": '''<div id="ec-formula-flash"></div>
          <table id="ecFormulaSummaryTable" data-live-save="power-demand"
          data-save-url="/power_demand/formulas/save" data-reset-url="/power_demand/formulas/reset" data-csrf-token="{{ csrf_token }}">
          <tbody><tr data-formula-key="test"><td><textarea class="form-control ec-formula-text-input">100</textarea></td></tr></tbody></table>
          <script src="/static/js/energy_consumption/ec_summary_formulas_table.js"></script>''',
    }[kind]

    def save():
        if app.config["SAVE_ERROR"]:
            return {"ok": False, "error": "Ошибка проверки"}, 400
        app.config["SAVED_VALUES"].append(request.form.to_dict() if kind == "detail" else request.get_json())
        refresh.publish_power_demand_data_change()
        return {"ok": True, "rows": [{"id": 1, "year": "2024", "p_max": "200"}]}

    def page():
        if request.method == "POST":
            return save()
        context = {"csrf_token": generate_csrf()}
        app.update_template_context(context)
        return app.jinja_env.from_string("{% extends 'base.html' %}{% block content %}" + table + "{% endblock %}").render(context)

    app.view_functions["power_demand_bp.russia_demand"] = page
    app.view_functions["power_demand_bp.ozp_maxima_save"] = save
    app.view_functions["power_demand_bp.power_demand_formulas_save"] = save
    open_page(browser, url)
    selector = {"detail": '[name="p_max[]"]', "ozp": '.fuel-param-input', "ozp_date": 'textarea.fuel-param-input', "formula": '.ec-formula-text-input'}[kind]
    values = ("10.01.2024 18:00", "11.01.2024 19:00", "12.01.2024 20:00") if kind == "ozp_date" else ("200", "300", "400")

    def edit(value):
        browser.execute_script('''const field = document.querySelector(arguments[0]); field.value = arguments[1];
          field.dispatchEvent(new Event('input', {bubbles:true}));
          field.dispatchEvent(new Event('change', {bubbles:true}));''', selector, value)

    def wait_state(state):
        WebDriverWait(browser, 5).until(lambda d: state in d.find_element(By.CSS_SELECTOR, selector).get_attribute("class"))

    edit(values[0])
    wait_state("is-save-success")
    assert len(app.config["SAVED_VALUES"]) == 1
    browser.execute_script("window.dispatchEvent(new Event('focus'))")
    assert "btn-warning" in browser.find_element(By.ID, "energyBalanceRefreshButton").get_attribute("class")
    app.config["SAVE_ERROR"] = True
    edit(values[1])
    wait_state("is-save-error")
    app.config["SAVE_ERROR"] = False
    edit(values[2])
    wait_state("is-save-success")
    assert len(app.config["SAVED_VALUES"]) == 2
    if kind == "ozp_date":
        assert app.config["SAVED_VALUES"][-1]["cells"][0] == {
            "ozp_end_year": "2024", "parameter_key": "peak_datetime", "value": values[2],
        }


@pytest.mark.parametrize("width", [1280, 1600])
@pytest.mark.parametrize("template,endpoint,active_summary,variant", [
    ("power_demand_edit.html", "russia_demand", "oes", "max"),
    ("ozp_max_power.html", "ozp_maxima", "oes", "max"),
    ("power_demand_summary.html", "demand_summary_oes", "oes", "max"),
    ("power_demand_summary.html", "demand_summary_federal_districts", "fo", "max"),
    ("power_demand_summary.html", "demand_summary_energy_zones", "ez", "max"),
    ("power_demand_summary.html", "demand_summary_oes_coeff", "oes", "coeff"),
    ("power_demand_summary.html", "demand_summary_federal_districts_coeff", "fo", "coeff"),
    ("power_demand_summary.html", "demand_summary_energy_zones_coeff", "ez", "coeff"),
])
def test_refresh_button_left_of_rounding(browser, load_server, template, endpoint, active_summary, variant, width):
    app, url = load_server
    app.jinja_env.filters["format_decimal_trim"] = format_decimal_trim_for_display

    def page():
        return render_template(
            "power_demand/" + template,
            csrf_token=generate_csrf(), page_title="Нагрузки", back_url="/power_demand/",
            rounding_digits=2, rounding_digits_k=3, growth_rounding_digits=2,
            start_year=2024, end_year=2024, get_reference_years=lambda: [2024],
            rows=[], years=[2024], year_features={}, summary_rows=[], columns=[],
            year_options=[], year_groups=[], active_summary=active_summary,
            summary_route_variant=variant, export_endpoint="power_demand_bp.demand_summary_oes_export",
        )

    full_endpoint = "power_demand_bp." + endpoint
    app.view_functions[full_endpoint] = page
    path = next(rule.rule for rule in app.url_map.iter_rules() if rule.endpoint == full_endpoint)
    browser.set_window_size(width, 1000)
    browser.get(url + "/test-login")
    browser.get(url + path)
    buttons = browser.find_elements(By.ID, "energyBalanceRefreshButton")
    assert len(buttons) == 1
    assert buttons[0].is_displayed()
    rounding_id = "rounding_digits_k" if variant == "coeff" else "rounding_digits"
    placement = browser.execute_script('''
        const button = document.getElementById('energyBalanceRefreshButton');
        const label = document.querySelector('label[for="' + arguments[0] + '"]');
        const b = button.getBoundingClientRect(), r = label.getBoundingClientRect();
        return {left:b.right <= r.left, sameRow:b.top < r.bottom && r.top < b.bottom};
    ''', rounding_id)
    assert placement == {"left": True, "sameRow": True}
    assert len(browser.find_elements(By.ID, "energy-balance-refresh-config")) == 1
    if variant == "coeff":
        browser.find_element(By.ID, "pdCoeffKColsToggle").click()
        assert not browser.find_element(By.ID, "rounding_digits_k").is_displayed()
        assert buttons[0].is_displayed()
