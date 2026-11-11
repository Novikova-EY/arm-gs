from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

pytest.importorskip("selenium")
from selenium.webdriver.common.by import By

from test_external_code_check_sticky_browser import browser, check_page


@pytest.fixture(scope="module")
def page_url():
    content = check_page(with_equipment=True).replace(
        "</table>",
        '<tbody><tr id="testGroupHeading"><td colspan="12">Group</td></tr></tbody></table>',
        1,
    ).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def page(browser, page_url):
    browser.set_window_size(1440, 900)
    browser.get(page_url)
    browser.execute_script("localStorage.clear()")
    browser.refresh()
    return browser


def click(page, element_id):
    page.find_element(By.ID, element_id).click()


def options(page):
    return page.find_elements(By.CSS_SELECTOR, "#externalCodeVersionList input")


def visible_versions(page):
    return page.execute_script('''
        return Array.from(document.querySelectorAll('#externalCodeCheckTable thead [data-external-code-version]'))
            .filter(cell => !cell.hidden).map(cell => cell.dataset.externalCodeVersion);
    ''')


@pytest.mark.parametrize("width", [760, 1440])
def test_selected_columns_align_and_persist_between_pages(page, page_url, width):
    page.set_window_size(width, 900)
    click(page, "externalCodeVersionFilter")
    click(page, "externalCodeVersionSelectAll")
    options(page)[0].click()
    options(page)[2].click()
    click(page, "externalCodeVersionApply")
    assert visible_versions(page) == ["legacy", "2"]
    assert page.find_element(By.ID, "externalCodeVersionCount").text == "Версии: 2 из 9"
    assert page.execute_script("return document.getElementById('externalCodeVersionsHeading').colSpan") == 2
    assert page.execute_script('''
        return Array.from(document.querySelectorAll('.external-code-station-row')).every(row =>
            row.cells[0].colSpan === 3 && Array.from(row.cells).slice(1).filter(cell => !cell.hidden).length === 2);
    ''')
    for row_class in ("external-code-equipment-group-row", "external-code-machine-row", "pgu-row"):
        assert page.execute_script('''
            return Array.from(document.querySelector(arguments[0]).querySelectorAll('[data-external-code-version]'))
                .filter(cell => !cell.hidden).map(cell => cell.dataset.externalCodeVersion);
        ''', "." + row_class) == ["legacy", "2"]
    page.get(page_url + "?page=2&union_energy_system_filter=410")
    assert visible_versions(page) == ["legacy", "2"]
    click(page, "externalCodeVersionFilter")
    click(page, "externalCodeVersionReset")
    click(page, "externalCodeVersionApply")
    assert len(visible_versions(page)) == 9
    page.refresh()
    assert len(visible_versions(page)) == 9


def test_search_select_all_cancel_and_empty_selection(page):
    click(page, "externalCodeVersionFilter")
    click(page, "externalCodeVersionSelectAll")
    click(page, "externalCodeVersionApply")
    assert page.find_element(By.ID, "externalCodeVersionError").is_displayed()
    assert len(visible_versions(page)) == 9
    search = page.find_element(By.ID, "externalCodeVersionSearch")
    search.send_keys("рабочая версия 3")
    assert sum(option.is_displayed() for option in options(page)) == 1
    click(page, "externalCodeVersionSelectAll")
    click(page, "externalCodeVersionApply")
    assert visible_versions(page) == ["3"]
    click(page, "externalCodeVersionFilter")
    search.send_keys("несуществующая версия")
    assert page.find_element(By.ID, "externalCodeVersionEmpty").is_displayed()
    assert not page.find_element(By.ID, "externalCodeVersionSelectAll").is_enabled()
    click(page, "externalCodeVersionReset")
    click(page, "externalCodeVersionCancel")
    assert visible_versions(page) == ["3"]
    click(page, "externalCodeVersionFilter")
    assert sum(option.is_selected() for option in options(page)) == 1
    search.send_keys("\ue00c")  # Escape
    assert not page.find_element(By.ID, "externalCodeVersionMenu").is_displayed()


def test_hidden_edits_are_preserved_and_spanning_rows_resize(page):
    code = page.find_element(By.CSS_SELECTOR, '.external-code-input[data-record-id="1"]')
    code.clear()
    code.send_keys("edited-legacy-code")
    click(page, "externalCodeVersionFilter")
    options(page)[0].click()
    click(page, "externalCodeVersionApply")
    assert not code.is_displayed()
    assert code.get_attribute("value") == "edited-legacy-code"
    assert page.find_element(By.ID, "externalCodeSaveBtn").is_enabled()
    assert "1" in page.find_element(By.ID, "externalCodeChangedHint").text
    assert page.find_element(By.CSS_SELECTOR, "#testGroupHeading td").get_attribute("colspan") == "11"
    click(page, "externalCodeVersionFilter")
    click(page, "externalCodeVersionReset")
    click(page, "externalCodeVersionApply")
    assert code.is_displayed()
    assert code.get_attribute("value") == "edited-legacy-code"
