import json
from datetime import datetime, timedelta, timezone
from threading import Thread
from types import SimpleNamespace

import pytest
from werkzeug.serving import make_server
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from test_data_refresh_history import Reader, Source, history, history_app, _patch_infrastructure
from app.extensions import db

pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.fixture
def history_server(history_app):
    server = make_server("127.0.0.1", 0, history_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield history_app, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.mark.parametrize("package,path,source", [
    ("energy_consumption", "/russia/", "app.energy_consumption.models.test_history"),
    ("power_demand", "/russia/", "app.power_demand.models.test_history"),
    ("energy_balance", "/ee_balance/ees-rossii/", "app.energy_balance.models.test_history"),
])
def test_revision_change_is_only_shown_in_refresh_button(browser, history_server, monkeypatch, package, path, source):
    from app.energy_consumption.services import data_refresh_services as ec
    from app.power_demand.services import data_refresh_services as pd
    from app.energy_balance.services import energy_balance_cache as eb

    app, url = history_server
    monkeypatch.setattr(Source, "__module__", source)
    service = {"energy_consumption": ec, "power_demand": pd, "energy_balance": eb}[package]
    browser.get(url + "/login")
    page = url + "/" + package + path + "?start_year=2024#table"
    browser.get(page)
    assert "Данные страницы на" in browser.find_element(By.ID, "dataRefreshLoadedAt").text
    assert browser.execute_script('''const loadedAt = document.getElementById('dataRefreshLoadedAt');
        return loadedAt.parentElement.contains(document.querySelector('h1'));''')
    browser.execute_script('''const field = document.getElementById('test-value');
        field.value = '999'; field.dispatchEvent(new Event('input', {bubbles: true}));''')
    with app.app_context(), Session(db.engine) as session:
        session.add(Source(value=200, year_number=2025, database_version_id=7, name="<script>test</script>"))
        session.commit()
    service._data_revision += 1

    def detected(driver):
        driver.execute_script("window.dispatchEvent(new Event('focus'))")
        button = driver.find_element(By.ID, "energyBalanceRefreshButton")
        return "btn-danger" in button.get_attribute("class")

    WebDriverWait(browser, 5).until(detected)
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert button.text == "Версия базы данных изменилась. Обновите страницу."
    assert browser.find_element(By.ID, "energyBalanceRefreshStatus").text == ""
    assert not browser.find_elements(By.ID, "dataRefreshHistoryButton")
    assert not browser.find_elements(By.ID, "dataRefreshHistoryDialog")
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"

    browser.refresh()
    WebDriverWait(browser, 5).until(lambda driver: driver.find_element(By.ID, "test-value").get_attribute("value") == "100")
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert "btn-danger" not in button.get_attribute("class")
    assert button.text == "Обновить данные"


@pytest.mark.parametrize("package,path", [
    ("energy_consumption", "/russia/"),
    ("power_demand", "/russia/"),
    ("energy_balance", "/ee_balance/ees-rossii/"),
])
def test_loaded_at_changes_only_after_successful_refresh(browser, history_server, monkeypatch, package, path):
    from app.energy_consumption.services import data_refresh_services as ec
    from app.power_demand.services import data_refresh_services as pd
    from app.energy_balance.services import energy_balance_cache as eb

    app, url = history_server
    service = {"energy_consumption": ec, "power_demand": pd, "energy_balance": eb}[package]
    now = [datetime(2026, 11, 5, 7, 21, 32, tzinfo=timezone.utc)]
    monkeypatch.setattr(history, "datetime", SimpleNamespace(now=lambda _tz: now[0]))
    browser.get(url + "/login")
    page = url + "/" + package + path + "?start_year=2024#table"
    browser.get(page)
    initial_label = browser.find_element(By.ID, "dataRefreshLoadedAt").text
    config = json.loads(browser.find_element(By.ID, "energy-balance-refresh-config").get_attribute("textContent"))
    assert config["loadedAt"] == now[0].isoformat()

    now[0] += timedelta(minutes=20)
    with app.app_context(), Session(db.engine) as session:
        monkeypatch.setattr(Source, "__module__", f"app.{package}.models.test_history")
        session.add(Source(value=200, database_version_id=7))
        session.commit()
    service._data_revision += 1
    browser.execute_script("window.dispatchEvent(new Event('focus'))")
    WebDriverWait(browser, 5).until(lambda driver: "btn-danger" in driver.find_element(
        By.ID, "energyBalanceRefreshButton",
    ).get_attribute("class"))
    assert browser.find_element(By.ID, "dataRefreshLoadedAt").text == initial_label

    browser.execute_script('''const field = document.getElementById('test-value');
        field.value = '999'; field.dispatchEvent(new Event('input', {bubbles: true}));''')
    browser.find_element(By.ID, "energyBalanceRefreshButton").click()
    browser.switch_to.alert.dismiss()
    assert browser.find_element(By.ID, "dataRefreshLoadedAt").text == initial_label
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"

    browser.find_element(By.ID, "energyBalanceRefreshButton").click()
    browser.switch_to.alert.accept()
    WebDriverWait(browser, 5).until(lambda driver: driver.find_element(
        By.ID, "dataRefreshLoadedAt",
    ).text != initial_label)
    config = json.loads(browser.find_element(By.ID, "energy-balance-refresh-config").get_attribute("textContent"))
    assert config["loadedAt"] == now[0].isoformat()
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "100"
    assert browser.current_url == page


@pytest.mark.parametrize("package,path", [
    ("energy_consumption", "/russia/"),
    ("power_demand", "/russia/"),
    ("energy_balance", "/ee_balance/ees-rossii/"),
])
def test_refresh_warning_matches_selected_version_history(browser, history_server, monkeypatch, package, path):
    from app.energy_consumption.services import data_refresh_services as ec
    from app.power_demand.services import data_refresh_services as pd
    from app.energy_balance.services import energy_balance_cache as eb

    app, url = history_server
    service = {"energy_consumption": ec, "power_demand": pd, "energy_balance": eb}[package]
    monkeypatch.setattr(Source, "__module__", f"app.{package}.models.test_history")
    browser.get(url + "/login")
    browser.get(url + "/" + package + path)
    browser.execute_script('''const field = document.getElementById('test-value');
        field.value = '999'; field.dispatchEvent(new Event('input', {bubbles: true}));''')

    with app.app_context(), Session(db.engine) as session:
        session.add(Source(value=800, database_version_id=8))
        session.commit()
    service._data_revision += 1

    browser.execute_script('''const originalFetch = window.fetch;
        window.fetch = async function (...args) {
            const response = await originalFetch(...args);
            if (String(args[0]).includes('/data-revision/')) {
                await response.clone().json();
                window.refreshChecked = true;
            }
            return response;
        };''')

    def check_status():
        browser.execute_script("window.refreshChecked = false")

        def checked(driver):
            return driver.execute_script('''window.dispatchEvent(new Event('focus'));
                return window.refreshChecked;''')

        WebDriverWait(browser, 5).until(checked)

    check_status()
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert "btn-danger" not in button.get_attribute("class")
    assert button.text == "Обновить данные"
    assert not browser.find_elements(By.ID, "dataRefreshHistoryButton")

    with app.app_context(), Session(db.engine) as session:
        session.add(Source(value=700, database_version_id=7, name="Текущая версия"))
        session.commit()
    service._data_revision += 1
    check_status()
    assert "btn-danger" in button.get_attribute("class")
    assert button.text == "Версия базы данных изменилась. Обновите страницу."
    assert browser.find_element(By.ID, "energyBalanceRefreshStatus").text == ""
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"

    # Returning to the page revision must clear an already displayed warning.
    service._data_revision = 0
    check_status()
    assert "btn-danger" not in button.get_attribute("class")
    assert button.text == "Обновить данные"
    assert browser.find_element(By.ID, "test-value").get_attribute("value") == "999"


@pytest.mark.parametrize("history_available", [False, None])
def test_revision_still_warns_when_history_cannot_confirm_changes(
    browser, history_server, monkeypatch, history_available,
):
    from app.power_demand.services import data_refresh_services as pd

    _app, url = history_server
    browser.get(url + "/login")
    browser.get(url + "/power_demand/russia/")
    if history_available is None:
        monkeypatch.setattr(history, "_enabled", lambda: False)
    else:
        monkeypatch.setattr(history, "_history_query", lambda *_args: (
            None, "История изменений временно недоступна.",
        ))
    pd._data_revision += 1

    def detected(driver):
        driver.execute_script("window.dispatchEvent(new Event('focus'))")
        return "btn-danger" in driver.find_element(By.ID, "energyBalanceRefreshButton").get_attribute("class")

    WebDriverWait(browser, 5).until(detected)
    button = browser.find_element(By.ID, "energyBalanceRefreshButton")
    assert button.text == "Версия базы данных изменилась. Обновите страницу."
    assert browser.find_element(By.ID, "energyBalanceRefreshStatus").text == ""
