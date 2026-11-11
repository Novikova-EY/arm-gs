import re
import sqlite3
from threading import Thread

import pytest
from flask import render_template_string
from flask_wtf.csrf import generate_csrf
from werkzeug.serving import make_server

pytest.importorskip("selenium")
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from test_consumption_cell_styles_browser import browser, ROOT
from test_consumption_data_refresh import consumption_app, consumption_cache
from app.energy_consumption.routes import energy_consumption_summary_routes as routes
from app.energy_consumption.services import data_refresh_services as refresh


@pytest.fixture
def live_summary(consumption_app, monkeypatch, tmp_path):
    database = tmp_path / "values.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE consumption (value TEXT)")
        connection.execute("INSERT INTO consumption VALUES ('100')")

    # Keep the real HTTP/CSRF boundary; isolate storage from the working database.
    def save(model, parameter, value, **kwargs):
        assert model == "UnionEnergySystemEnergyConsumptionParameter"
        assert parameter == "energy_consumption_mln_kvt_ch"
        assert kwargs["slice_key"] == 2025
        assert kwargs["parent_id"] == 1
        assert kwargs["summary_log_scope"] == "oes"
        if value == "invalid":
            raise ValueError("Invalid number")
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE consumption SET value = ?", (value,))
        refresh.publish_energy_consumption_data_change()
        return value

    monkeypatch.setattr(routes, "can_edit_energy_consumption", lambda user: True)
    monkeypatch.setattr(routes.dps, "save_demand_summary_cell", save)
    source = (ROOT / "app/templates/energy_consumption/pages/summary_oes_body.html").read_text(encoding="utf-8")
    table_attrs = source[source.index('<table id="powerDemandSummaryTable"'):source.index("<colgroup>")]
    assert 'data-csrf-token="{{ csrf_token }}"' in table_attrs
    script = re.search(r'<script[^>]+demand_summary_live_save\.js[^>]*></script>', source)[0]
    markup = '''<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/static/css/energy_consumption_live_save.css">
<button id="demandSummarySaveBtn">Save</button>
<table id="powerDemandSummaryTable" class="power-demand-summary-table"
 data-save-cell-url="/energy_consumption/summary/cell" data-summary-log-scope="oes"
 data-csrf-token="{{ csrf_token }}"><tbody><tr class="summary-row-param">
<td class="summary-year-cell"><input id="value" class="form-control fuel-param-input"
 data-model="UnionEnergySystemEnergyConsumptionParameter" data-slice="2025"
 data-parameter-key="energy_consumption_mln_kvt_ch" data-parent-fk="id_union_energy_system"
 data-parent-id="1" data-initial="{{ value }}" value="{{ value }}"></td>
</tr></tbody></table>
{% with data_refresh=energy_consumption_refresh %}
{% include 'common/_data_refresh.html' %}
{% endwith %}
<script src="/static/js/energy_consumption/consumption_live_save.js" defer></script>
''' + script

    def page():
        with sqlite3.connect(database) as connection:
            value = connection.execute("SELECT value FROM consumption").fetchone()[0]
        return render_template_string(markup, csrf_token=generate_csrf(), value=value)

    consumption_app.view_functions["energy_consumption_bp.demand_summary_oes"] = page
    server = make_server("127.0.0.1", 0, consumption_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_autosave_survives_reload_and_rejected_value_can_be_corrected(browser, live_summary):
    browser.get(live_summary + "/test-login")
    url = live_summary + "/energy_consumption/summary/oes/?pd_page_size=0"
    browser.get(url)
    wait = WebDriverWait(browser, 5)

    def edit(value, key):
        field = browser.find_element(By.ID, "value")
        field.send_keys(Keys.CONTROL, "a")
        field.send_keys(value)
        field.send_keys(key)
        return field

    field = edit("123,456", Keys.TAB)
    wait.until(lambda driver: "is-save-success" in field.get_attribute("class"))
    assert field.value_of_css_property("background-color") == "rgba(209, 231, 221, 1)"
    browser.refresh()
    assert browser.current_url == url
    assert browser.find_element(By.ID, "value").get_attribute("value") == "123,456"

    field = edit("invalid", Keys.ENTER)
    wait.until(lambda driver: "is-save-error" in field.get_attribute("class"))
    assert field.get_attribute("value") == "invalid"
    assert field.get_attribute("title") == "Invalid number"
    assert field.value_of_css_property("background-color") == "rgba(248, 215, 218, 1)"
    field = edit("456,789", Keys.ENTER)
    wait.until(lambda driver: "is-save-success" in field.get_attribute("class"))
    browser.refresh()
    assert browser.find_element(By.ID, "value").get_attribute("value") == "456,789"


def check_refresh_button(browser):
    browser.execute_async_script('''const done = arguments[0];
        const original = window.fetch;
        window.fetch = async function (...args) {
            const response = await original(...args);
            if (args[0].includes('/data-revision/')) {
                window.fetch = original;
                setTimeout(done, 0);
            }
            return response;
        };
        window.dispatchEvent(new Event('focus'));
    ''')
    return browser.find_element(By.ID, "energyBalanceRefreshButton")


def test_own_autosaves_stay_yellow_but_other_tab_changes_still_notify(browser, live_summary):
    browser.get(live_summary + "/test-login")
    browser.get(live_summary + "/energy_consumption/summary/oes/?pd_page_size=0")
    for value in ("200", "300"):
        field = browser.find_element(By.ID, "value")
        field.send_keys(Keys.CONTROL, "a")
        field.send_keys(value, Keys.TAB)
        WebDriverWait(browser, 5).until(lambda driver: "is-save-success" in field.get_attribute("class"))
        button = check_refresh_button(browser)
        assert button.text == "Обновить данные"
        assert "btn-warning" in button.get_attribute("class").split()
    refresh.publish_energy_consumption_data_change()
    button = check_refresh_button(browser)
    assert "btn-danger" in button.get_attribute("class").split()
    field.send_keys(Keys.CONTROL, "a")
    field.send_keys("400", Keys.TAB)
    WebDriverWait(browser, 5).until(lambda driver: "is-save-success" in field.get_attribute("class"))
    assert "btn-danger" in check_refresh_button(browser).get_attribute("class").split()
    assert field.get_attribute("value") == "400"


def test_status_response_started_before_autosave_cannot_turn_button_red(browser, live_summary):
    browser.get(live_summary + "/test-login")
    browser.get(live_summary + "/energy_consumption/summary/oes/?pd_page_size=0")
    check_refresh_button(browser)
    browser.execute_async_script('''const done = arguments[0];
        const original = window.fetch;
        window.fetch = async function (...args) {
            const response = await original(...args);
            if (args[0].includes('/data-revision/')) {
                window.fetch = original;
                return new Promise(resolve => {
                    window.releaseRevisionCheck = () => resolve(response);
                    done();
                });
            }
            return response;
        };
        window.dispatchEvent(new Event('focus'));
    ''')
    field = browser.find_element(By.ID, "value")
    field.send_keys(Keys.CONTROL, "a")
    field.send_keys("200", Keys.TAB)
    WebDriverWait(browser, 5).until(lambda driver: "is-save-success" in field.get_attribute("class"))
    browser.execute_async_script('''const done = arguments[0];
        window.releaseRevisionCheck(); setTimeout(done, 50);''')
    assert browser.find_element(By.ID, "energyBalanceRefreshButton").text == "Обновить данные"
    assert check_refresh_button(browser).text == "Обновить данные"
