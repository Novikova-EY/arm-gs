from threading import Event, Thread
import re

from flask_wtf.csrf import generate_csrf

import pytest
from werkzeug.serving import make_server

from app.energy_consumption.services import data_refresh_services as refresh
from app.energy_consumption.services import ec_summary_page_cache as summary_cache
from test_consumption_data_refresh import (
    ConsumptionSource, consumption_app, consumption_cache, consumption_db,
)
from test_growth_rounding import ROUNDING_TEMPLATES

pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
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
def consumption_server(consumption_app):
    server = make_server("127.0.0.1", 0, consumption_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield consumption_app, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def open_page(browser, url, path="/russia/"):
    browser.get(url + "/test-login")
    page = url + "/energy_consumption" + path + "?rounding_digits=2&start_year=2024#table"
    browser.get(page)
    return page


def edit(browser, value):
    browser.execute_script('''const field = document.getElementById('test-value');
        field.value = arguments[0]; field.dispatchEvent(new Event('input', {bubbles:true}));''', value)


def wait_for_change(browser):
    def detected(driver):
        driver.execute_script("window.dispatchEvent(new Event('focus'))")
        return driver.find_element(By.ID, "energyBalanceRefreshButton").text == "Версия базы данных изменилась. Обновите страницу."

    WebDriverWait(browser, 5).until(detected)


def test_committed_import_notifies_reader_without_overwriting_edits(browser, consumption_server, consumption_db):
    app, url = consumption_server
    page = open_page(browser, url)
    edit(browser, "999")
    app.config["TEST_VALUE"] = "200"
    consumption_db.add_all([ConsumptionSource(value=200), ConsumptionSource(value=300)])
    consumption_db.commit()
    wait_for_change(browser)
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert "btn-danger" in button.get_attribute("class").split()
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"
    before = summary_cache._get_cache_generation()
    button.click()
    browser.switch_to.alert.dismiss()
    assert summary_cache._get_cache_generation() == before
    assert browser.current_url == page
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"
    button.click()
    browser.switch_to.alert.accept()
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script(
        "return document.getElementById('test-value')?.value"
    ) == "200")
    assert browser.current_url == page
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert button.text == "Обновить данные"
    assert "btn-warning" in button.get_attribute("class").split()


def test_manual_refresh_in_second_tab_does_not_turn_first_tab_red(browser, consumption_server):
    app, url = consumption_server
    page = open_page(browser, url)
    first_tab = browser.current_window_handle
    browser.switch_to.new_window("tab")
    try:
        browser.get(page)
        button = browser.find_element(By.ID, "energyBalanceRefreshButton")
        before = summary_cache._get_cache_generation()
        button.click()
        WebDriverWait(browser, 5).until(EC.staleness_of(button))
        assert summary_cache._get_cache_generation() == before + 1
        assert refresh.get_energy_consumption_data_revision() == 0
    finally:
        browser.close()
        browser.switch_to.window(first_tab)
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
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert button.text == "Обновить данные"
    assert "btn-warning" in button.get_attribute("class").split()


@pytest.mark.parametrize("path", ["/", "/russia/", "/summary/oes/", "/summary_table/oes/gaes_charge/"])
def test_shared_button_on_hub_detail_and_summary_pages(browser, consumption_server, path):
    app, url = consumption_server
    open_page(browser, url, path)
    buttons = browser.find_elements(By.ID, "energyBalanceRefreshButton")
    if path == "/":
        assert buttons == []
        return
    assert len(buttons) == 1
    assert buttons[0].is_displayed()
    assert browser.execute_script(
        "return getComputedStyle(document.getElementById('energyBalanceRefreshButton')).backgroundColor"
    ) == "rgb(255, 193, 7)"
    refresh.publish_energy_consumption_data_change()
    wait_for_change(browser)
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script(
        "return getComputedStyle(document.getElementById('energyBalanceRefreshButton')).backgroundColor"
    ) in {"rgb(220, 53, 69)", "rgb(187, 45, 59)"})


def test_failed_refresh_keeps_red_state_and_page(browser, consumption_server, monkeypatch):
    app, url = consumption_server
    page = open_page(browser, url)
    refresh.publish_energy_consumption_data_change()
    wait_for_change(browser)
    monkeypatch.setitem(app.view_functions, "energy_consumption_bp.refresh_data", lambda: ("Unavailable", 503))
    browser.find_element(By.ID, "energyBalanceRefreshButton").click()
    WebDriverWait(browser, 5).until(lambda driver: "503" in driver.find_element(By.ID, "energyBalanceRefreshStatus").text)
    assert browser.current_url == page
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "100"
    assert "btn-danger" in browser.find_element(By.ID, "energyBalanceRefreshButton").get_attribute("class").split()


def test_edits_during_refresh_prevent_reload(browser, consumption_server, monkeypatch):
    app, url = consumption_server
    open_page(browser, url)
    started, release = Event(), Event()
    original = app.view_functions["energy_consumption_bp.refresh_data"]

    def slow_refresh():
        started.set()
        assert release.wait(10)
        return original()

    monkeypatch.setitem(app.view_functions, "energy_consumption_bp.refresh_data", slow_refresh)
    try:
        browser.find_element(By.ID, "energyBalanceRefreshButton").click()
        assert started.wait(5)
        edit(browser, "new-edit")
        release.set()
        WebDriverWait(browser, 5).until(lambda driver: "Появились новые правки" in driver.find_element(By.ID, "energyBalanceRefreshStatus").text)
        assert browser.find_element(By.ID, "test-value").get_attribute("value") == "new-edit"
    finally:
        release.set()


@pytest.mark.parametrize("template", ROUNDING_TEMPLATES, ids=lambda path: path.stem)
@pytest.mark.parametrize("width", [900, 1440])
def test_refresh_is_left_of_both_rounding_controls_on_every_table(browser, consumption_server, monkeypatch, template, width):
    app, url = consumption_server
    source = template.read_text(encoding="utf-8-sig")
    wrapper = template.with_name(template.name.replace("_body.html", ".html"))
    wrapper_source = wrapper.read_text(encoding="utf-8-sig")
    content = re.search(r"{%\s*block\s+content\s*%}", wrapper_source)
    assert content is not None
    prefix = wrapper_source[:content.start()]
    start = source.index("{% include 'energy_consumption/_growth_rounding.html' %}")
    end = source.index("</select>", start) + len("</select>")
    controls = source[start:end] + "</div>"

    def page():
        context = {"rounding_digits": 1, "rd": 1, "csrf_token": generate_csrf()}
        app.update_template_context(context)
        return app.jinja_env.from_string(prefix + '''{% block content %}
          <div class="d-flex align-items-center justify-content-end gap-2">'''
          + controls + "</div>{% endblock %}").render(context)

    monkeypatch.setitem(app.view_functions, "energy_consumption_bp.russia_demand", page)
    browser.set_window_size(width, 1000)
    open_page(browser, url)
    assert len(browser.find_elements(By.ID, "energyBalanceRefreshButton")) == 1

    def assert_position():
        layout = browser.execute_script('''
            const root = document.getElementById('energyBalanceDataRefresh');
            const button = document.getElementById('energyBalanceRefreshButton');
            const growth = document.querySelector('label[for="growth_rounding_digits"]');
            const general = document.querySelector('label[for="rounding_digits"]');
            const a = button.getBoundingClientRect(), b = growth.getBoundingClientRect();
            const c = general.getBoundingClientRect();
            return {sameParent: root.parentElement === growth.parentElement.parentElement,
                left: a.right <= b.left && b.right <= c.left,
                sameLine: Math.abs((a.top+a.bottom-b.top-b.bottom)/2) < 2
                    && Math.abs((a.top+a.bottom-c.top-c.bottom)/2) < 2};
        ''')
        assert layout == {"sameParent": True, "left": True, "sameLine": True}

    assert_position()
    refresh.publish_energy_consumption_data_change()
    wait_for_change(browser)
    assert_position()


def test_initial_formatting_and_calculated_fields_do_not_prompt_about_edits(browser, consumption_server, monkeypatch):
    app, url = consumption_server
    original = app.view_functions["energy_consumption_bp.russia_demand"]

    def formatted_page():
        html = original()
        html = html.replace('<input id="test-value"', '<input id="test-calculated" readonly value="10"><input id="test-value"')
        return html.replace("</body>", '''<script>
          document.addEventListener('DOMContentLoaded', function () {
            document.getElementById('test-value').value = '100.0';
          });
        </script></body>''')

    monkeypatch.setitem(app.view_functions, "energy_consumption_bp.russia_demand", formatted_page)
    open_page(browser, url)
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "100.0"
    browser.execute_script("document.getElementById('test-calculated').value = '20'")
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    button.click()
    WebDriverWait(browser, 5).until(EC.staleness_of(button))
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "100.0"
