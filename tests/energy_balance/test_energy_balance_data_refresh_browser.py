from threading import Event, Thread

from flask import current_app
from jinja2 import ChoiceLoader, DictLoader
import pytest
from werkzeug.serving import make_server

from test_energy_balance_data_refresh import refresh_app
from app.energy_balance.services import energy_balance_cache as cache

pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.fixture
def refresh_server(refresh_app):
    server = make_server("127.0.0.1", 0, refresh_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield refresh_app, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def open_table(browser, url):
    browser.get(url + "/test-login")
    page = url + "/energy_balance/ee_balance/ees-rossii/?start_year=2024&end_year=2026&rounding_digits=2#table"
    browser.get(page)
    return page


def edit(browser, value="999"):
    browser.execute_script('''const field = document.getElementById('test-value');
        field.value = arguments[0]; field.dispatchEvent(new Event('input', {bubbles: true}));''', value)


def wait_for_change(browser):
    def detected(driver):
        driver.execute_script("window.dispatchEvent(new Event('focus'))")
        return driver.find_element(By.ID, "energyBalanceRefreshButton").text == "Версия базы данных изменилась. Обновите страницу."

    WebDriverWait(browser, 5).until(detected)


def test_external_change_only_notifies_and_cancel_preserves_edits(browser, refresh_server):
    app, url = refresh_server
    original_url = open_table(browser, url)
    edit(browser)
    app.config["TEST_VALUE"] = "200"
    cache.publish_energy_balance_data_change()
    wait_for_change(browser)
    assert "btn-danger" in browser.find_element(By.ID, "energyBalanceRefreshButton").get_attribute("class").split()
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"
    assert browser.current_url == original_url
    before = cache.get_energy_balance_cache_generation()
    browser.find_element(By.ID, "energyBalanceRefreshButton").click()
    browser.switch_to.alert.dismiss()
    assert cache.get_energy_balance_cache_generation() == before
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"
    browser.find_element(By.ID, "energyBalanceRefreshButton").click()
    browser.switch_to.alert.accept()
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script("return document.getElementById('test-value')?.value") == "200")
    assert browser.current_url == original_url
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert button.text == "Обновить данные"
    assert "btn-warning" in button.get_attribute("class").split()
    assert "btn-danger" not in button.get_attribute("class").split()


def test_refresh_in_another_tab_does_not_mark_unchanged_data_red(browser, refresh_server):
    app, url = refresh_server
    page = open_table(browser, url)
    original_tab = browser.current_window_handle
    browser.switch_to.new_window("tab")
    try:
        browser.get(page)
        button = browser.find_element(By.ID, "energyBalanceRefreshButton")
        before = cache.get_energy_balance_cache_generation()
        button.click()
        WebDriverWait(browser, 5).until(EC.staleness_of(button))
        assert cache.get_energy_balance_cache_generation() == before + 1
        assert cache.get_energy_balance_data_revision() == 0
    finally:
        browser.close()
        browser.switch_to.window(original_tab)
    result = browser.execute_async_script('''
        const done = arguments[0];
        const config = JSON.parse(document.getElementById('energy-balance-refresh-config').textContent);
        fetch(config.statusUrl, {cache: 'no-store'})
            .then(response => response.json())
            .then(result => done({revision: result.revision, original: config.revision}));
    ''')
    assert result["revision"] == result["original"]
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert button.text == "Обновить данные"
    assert "btn-warning" in button.get_attribute("class").split()
    assert "btn-danger" not in button.get_attribute("class").split()


def test_refresh_failure_keeps_entered_values_and_allows_retry(browser, refresh_server, monkeypatch):
    app, url = refresh_server
    open_table(browser, url)
    original = app.view_functions["energy_balance_bp.refresh_data"]
    monkeypatch.setitem(app.view_functions, "energy_balance_bp.refresh_data", lambda: ("unavailable", 503))
    edit(browser)
    cache.publish_energy_balance_data_change()
    wait_for_change(browser)
    browser.find_element(By.ID, "energyBalanceRefreshButton").click()
    browser.switch_to.alert.accept()
    WebDriverWait(browser, 5).until(lambda driver: "503" in driver.find_element(By.ID, "energyBalanceRefreshStatus").text)
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"
    assert browser.find_element(By.ID, "energyBalanceRefreshButton").is_enabled()
    assert browser.find_element(By.ID, "energyBalanceRefreshButton").text == "Версия базы данных изменилась. Обновите страницу."
    assert "btn-danger" in browser.find_element(By.ID, "energyBalanceRefreshButton").get_attribute("class").split()
    monkeypatch.setitem(app.view_functions, "energy_balance_bp.refresh_data", original)
    app.config["TEST_VALUE"] = "300"
    browser.find_element(By.ID, "energyBalanceRefreshButton").click()
    browser.switch_to.alert.accept()
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script("return document.getElementById('test-value')?.value") == "300")


@pytest.mark.parametrize("kind, table_id", [
    ("ee_balance", "eeBalanceTable"),
    ("power_balance", "powerBalanceTable"),
])
@pytest.mark.parametrize("width", [900, 1440])
def test_refresh_button_is_yellow_and_left_of_rounding_above_table(
    browser, refresh_server, monkeypatch, kind, table_id, width
):
    app, url = refresh_server
    monkeypatch.setattr(app, "jinja_loader", ChoiceLoader([
        DictLoader({"base.html": '''<!doctype html><html><head><meta charset="utf-8">
          <link rel="stylesheet" href="/static/css/bootstrap.min.css">
          </head><body>{% block content %}{% endblock %}</body></html>'''}),
        app.jinja_loader,
    ]))
    monkeypatch.setitem(app.jinja_env.globals, "get_reference_years", lambda: [2024, 2025, 2026])

    def table_page(slug):
        context = dict(
            sheet={"slug": slug}, rows=[], years=[2026], filter_year_list=[2026],
            start_year=2024, end_year=2026, rounding_digits=1,
        )
        current_app.update_template_context(context)
        return app.jinja_env.get_template(f"energy_balance/{kind}/{kind}_table.html").render(context)

    monkeypatch.setitem(app.view_functions, f"energy_balance_bp.{kind}_table", table_page)
    browser.set_window_size(width, 1000)
    browser.get(url + "/test-login")
    page = url + f"/energy_balance/{kind}/ees-rossii/"
    browser.get(page)
    buttons = browser.find_elements(By.ID, "energyBalanceRefreshButton")
    assert len(buttons) == 1
    button = buttons[0]
    assert button.is_displayed()
    assert "btn-warning" in button.get_attribute("class").split()
    layout = browser.execute_script('''
        const button = document.getElementById('energyBalanceRefreshButton');
        const rounding = document.querySelector('label[for="rounding_digits"]');
        const heading = document.querySelector('#' + arguments[0] + ' thead');
        const a = button.getBoundingClientRect(), b = rounding.getBoundingClientRect();
        return {
            sameToolbar: button.closest('#energyBalanceDataRefresh').parentElement === rounding.parentElement,
            left: a.right <= b.left,
            sameLine: Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) < 2,
            aboveHeader: a.bottom <= heading.getBoundingClientRect().top,
            background: getComputedStyle(button).backgroundColor
        };
    ''', table_id)
    assert layout["sameToolbar"] and layout["left"] and layout["sameLine"] and layout["aboveHeader"]
    assert layout["background"] == "rgb(255, 193, 7)"
    cache.publish_energy_balance_data_change()
    wait_for_change(browser)
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script(
        "return getComputedStyle(document.getElementById('energyBalanceRefreshButton')).backgroundColor"
    ) in {"rgb(220, 53, 69)", "rgb(187, 45, 59)"})
    before = cache.get_energy_balance_cache_generation()
    button.click()
    WebDriverWait(browser, 5).until(lambda driver: cache.get_energy_balance_cache_generation() > before)
    WebDriverWait(browser, 5).until(lambda driver: driver.execute_script("return document.getElementById('energyBalanceRefreshLabel')?.textContent.trim()") == "Обновить данные")
    assert browser.current_url == page


def test_edits_during_refresh_response_prevent_reload(browser, refresh_server, monkeypatch):
    app, url = refresh_server
    open_table(browser, url)
    started, release = Event(), Event()
    original = app.view_functions["energy_balance_bp.refresh_data"]

    def slow_refresh():
        started.set()
        assert release.wait(10)
        return original()

    monkeypatch.setitem(app.view_functions, "energy_balance_bp.refresh_data", slow_refresh)
    try:
        browser.find_element(By.ID, "energyBalanceRefreshButton").click()
        assert started.wait(5)
        edit(browser, "new-edit")
        release.set()
        WebDriverWait(browser, 5).until(lambda driver: "Появились новые правки" in driver.find_element(By.ID, "energyBalanceRefreshStatus").text)
        assert browser.find_element(By.ID, "test-value").get_attribute("value") == "new-edit"
    finally:
        release.set()
