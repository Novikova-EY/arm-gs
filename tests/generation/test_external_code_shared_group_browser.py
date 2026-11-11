from urllib.parse import quote

import pytest

pytest.importorskip("selenium")
from selenium.webdriver.common.by import By

from test_external_code_check_sticky_browser import browser, check_page


@pytest.mark.parametrize("width,grouped", [(760, False), (1440, True)])
def test_shared_group_hierarchy_keeps_station_machine_links_and_column_filter(browser, width, grouped):
    browser.set_window_size(width, 900)
    browser.get("data:text/html;charset=utf-8," + quote(check_page(with_shared_equipment=True, grouped=grouped)))
    rows = browser.find_elements(By.CSS_SELECTOR, "#externalCodeCheckTable .external-code-station-tbody tr")
    assert "external-code-equipment-group-row" in rows[0].get_attribute("class")
    assert "Электростанция 1" in rows[1].text
    assert "Агрегат 1" in rows[2].text
    assert "pgu-row" in rows[3].get_attribute("class")
    assert "Электростанция 2" in rows[4].text
    assert "Агрегат второй станции" in rows[5].text
    assert "Электростанция 3" in rows[6].text
    assert len(browser.find_elements(By.CSS_SELECTOR, ".external-code-equipment-group-row")) == 1
    assert len(browser.find_elements(By.CSS_SELECTOR, '.external-code-input[data-record-id="100"]')) == 1
    assert len(browser.find_elements(By.CSS_SELECTOR, '.external-code-input[data-record-id="101"]')) == 1
    assert not rows[0].find_elements(By.CSS_SELECTOR, ".table-warning")
    assert rows[0].find_elements(By.CSS_SELECTOR, ".external-code-missing")

    browser.find_element(By.ID, "externalCodeVersionFilter").click()
    browser.find_element(By.ID, "externalCodeVersionSelectAll").click()
    options = browser.find_elements(By.CSS_SELECTOR, "#externalCodeVersionList input")
    options[1].click()
    options[2].click()
    browser.find_element(By.ID, "externalCodeVersionApply").click()
    for row in rows[:6]:
        visible = [cell.get_attribute("data-external-code-version") for cell in row.find_elements(
            By.CSS_SELECTOR, "[data-external-code-version]",
        ) if cell.is_displayed()]
        assert visible == ["1", "2"]
    assert not rows[0].find_elements(By.CSS_SELECTOR, ".table-warning")
    assert len(browser.find_elements(By.CSS_SELECTOR, ".external-code-machine-row")) == 2
