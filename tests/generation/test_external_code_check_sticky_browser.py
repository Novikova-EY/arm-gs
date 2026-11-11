from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


def check_page(with_equipment=False, with_shared_equipment=False, grouped=False):
    templates = ROOT / "app/templates"
    source = (templates / "generation/stations/external_code_check.html").read_text(encoding="utf-8")
    content = source[source.index('<div class="container-fluid mt-2">'):source.index('<script id="initial-state-json"')]
    controls = '''
        <div class="d-flex justify-content-between mb-2"><button>Фильтры / Поиск</button><span>Найдено станций: 50</span></div>
        <div id="testFilterFields" class="row g-2 mb-2">
            <div class="col-6"><input class="form-control" placeholder="Электростанция"></div>
            <div class="col-6"><input class="form-control" placeholder="UUID"></div>
        </div>
        <div class="mb-2" id="testPagination"><button>Назад</button><button>1</button><button>Далее</button></div>
    '''
    env = Environment(loader=ChoiceLoader([
        DictLoader({
            "generation/stations/station_filters.html": controls,
            "generation/includes/pagination_station.html": "",
            "generation/stations/aggregated_data/energy_system_types/energy_system_type_header.html": '<tr><td colspan="12">Тип энергосистемы</td></tr>',
            "generation/stations/aggregated_data/union_energy_systems/union_energy_system_header.html": '<tr><td colspan="12">ОЭС</td></tr>',
            "generation/stations/aggregated_data/regional_energy_systems/regional_energy_system_header.html": '<tr><td colspan="12">РЭС</td></tr>',
        }),
        FileSystemLoader(templates),
    ]), autoescape=True)
    env.globals["url_for"] = lambda *args, **kwargs: "#"
    versions = [{"id": None, "version_number": "Без версии"}] + [
        {"id": i, "version_number": f"СиПР 2026-2031 (рабочая версия {i})"} for i in range(1, 9)
    ]
    stations = [SimpleNamespace(
        id=i, name=f"Электростанция {i}", external_code=f"station-code-{i}", regional_district=None, machines=[],
        external_code_equipment_groups=[], external_code_ungrouped_machines=[],
        external_codes_by_version={None if i == 1 else 1: f"station-code-{i}"},
        external_code_record_ids_by_version={None if i == 1 else 1: i}, external_code_mismatch=True,
    ) for i in range(1, 51)]
    if with_equipment or with_shared_equipment:
        machine = SimpleNamespace(
            id=1001, external_code="machine-code", machine_group="1", machine_number="1", display_name="Агрегат 1",
            pgu_machines=[SimpleNamespace(pgu_machine_name="ПГУ 1")],
            external_codes_by_version={1: "machine-code", 2: "different-machine-code"},
            external_code_record_ids_by_version={1: 1001, 2: 1002}, external_code_mismatch=True,
        )
        stations[0].external_code_equipment_groups = [SimpleNamespace(
            id=100, name="Группа 1", external_code="group-code", numb="1", main=False, database_version_id=1,
            duplicate_code_count=1, external_codes_by_version={1: "group-code", 2: "group-code"},
            external_code_record_ids_by_version={1: 100, 2: 101}, external_code_mismatch=True,
            machines=[machine],
        )]
    block_context = {}
    if with_shared_equipment:
        from app.generation.services.station_services.external_code_check_services import build_external_code_check_blocks

        shared_group = stations[0].external_code_equipment_groups[0]
        shared_group.station_ids = (1, 2)
        second_machine = SimpleNamespace(
            **{**vars(machine), "id": 2001, "display_name": "Агрегат второй станции", "pgu_machines": [],
               "external_code": "second-machine-code", "external_codes_by_version": {1: "second-machine-code", 2: "second-machine-code"},
               "external_code_record_ids_by_version": {1: 2001, 2: 2002}}
        )
        stations[1].external_code_equipment_groups = [SimpleNamespace(**{**vars(shared_group), "machines": [second_machine]})]
        block_context["external_code_display_blocks"] = build_external_code_check_blocks(stations)
    if grouped:
        block_context.update(
            sorted_energy_system_type_ids=[1], stations_grouped={1: {2: {3: {4: stations}}}},
            grouped_display_order={1: {2: {3: [4]}}}, regional_districts_count_per_res={3: 1},
            show_headers={"energy_system_types": [1], "union_energy_systems": [2], "regional_energy_systems": [3]},
        )
    rendered = env.from_string(content).render(
        database_versions=versions, stations=stations, per_page=10, request=SimpleNamespace(args={}),
        **block_context,
    )
    styles = "\n".join((ROOT / "app/static/css" / name).read_text(encoding="utf-8")
                       for name in ("bootstrap.min.css", "style.css", "table_headers.css"))
    base = (templates / "base.html").read_text(encoding="utf-8")
    start = base.index("        (function () {")
    script = base[start:base.index("    </script>", start)]
    code_script = (ROOT / "app/static/js/generation/stations/external_code_check.js").read_text(encoding="utf-8")
    filter_script = (ROOT / "app/static/js/generation/stations/external_code_version_filter.js").read_text(encoding="utf-8")
    return (f'<!doctype html><meta charset="utf-8"><style>{styles}</style>{rendered}'
            f'<script>{script}</script><script>{code_script}</script><script>{filter_script}</script>')


def metrics(browser):
    return browser.execute_script('''
        const wrap = document.querySelector('.page-table-scroll');
        const panel = wrap.querySelector('.pd-ec-summary-sticky-stack');
        const rows = document.querySelector('#externalCodeCheckTable').tHead.rows;
        const first = rows[0].cells[0].getBoundingClientRect();
        const second = rows[1].cells[0].getBoundingClientRect();
        const panelRect = panel.getBoundingClientRect();
        const pagination = document.getElementById('testPagination').getBoundingClientRect();
        const hit = document.elementFromPoint(second.x + 10, second.y + second.height / 2);
        return {
            wrapTop: wrap.getBoundingClientRect().top, panelTop: panelRect.top, panelBottom: panelRect.bottom,
            panelHeight: panelRect.height, firstTop: first.top, firstBottom: first.bottom, secondTop: second.top,
            secondBottom: second.bottom, headerOnTop: rows[1].contains(hit),
            paginationTop: pagination.top, paginationBottom: pagination.bottom,
            scrollTop: wrap.scrollTop, viewportHeight: innerHeight,
            offset: parseFloat(getComputedStyle(wrap).getPropertyValue('--pd-summary-controls-sticky-height')),
        };
    ''')


def assert_sticky_layout(value):
    assert value["scrollTop"] > 0
    assert abs(value["panelTop"] - value["wrapTop"]) <= 1
    assert value["paginationTop"] >= value["panelTop"]
    assert value["paginationBottom"] <= value["panelBottom"]
    assert value["firstTop"] >= value["panelBottom"] - 1
    assert abs(value["secondTop"] - value["firstBottom"]) <= 2
    assert value["secondBottom"] < value["viewportHeight"]
    assert value["headerOnTop"]


@pytest.mark.parametrize("width", [760, 1440])
def test_filters_pagination_and_both_header_rows_stay_visible(browser, width):
    browser.set_window_size(width, 900)
    browser.get("data:text/html;charset=utf-8," + quote(check_page()))
    wait = WebDriverWait(browser, 5)
    wait.until(lambda driver: metrics(driver)["offset"] > 0)
    browser.execute_script("document.querySelector('.page-table-scroll').scrollTop = 800")
    wait.until(lambda driver: metrics(driver)["panelTop"] <= metrics(driver)["wrapTop"] + 1)
    assert_sticky_layout(metrics(browser))
    browser.execute_script("document.getElementById('testFilterFields').style.display = 'none'")
    wait.until(lambda driver: abs(metrics(driver)["offset"] - metrics(driver)["panelHeight"]) <= 1)
    assert_sticky_layout(metrics(browser))
    browser.execute_script("document.getElementById('testFilterFields').style.display = ''")
    wait.until(lambda driver: abs(metrics(driver)["offset"] - metrics(driver)["panelHeight"]) <= 1)
    assert_sticky_layout(metrics(browser))


def test_legacy_code_is_visible_and_editable_in_its_own_column(browser):
    from selenium.webdriver.common.by import By

    browser.set_window_size(1440, 900)
    browser.get("data:text/html;charset=utf-8," + quote(check_page()))
    headings = browser.find_elements(By.CSS_SELECTOR, "#externalCodeCheckTable thead tr:nth-child(2) th")
    assert headings[3].text == "Без версии"
    row = browser.find_element(By.CSS_SELECTOR, ".external-code-station-row")
    cells = row.find_elements(By.TAG_NAME, "td")
    legacy = cells[1].find_element(By.CSS_SELECTOR, "input.external-code-input")
    assert legacy.get_attribute("value") == "station-code-1"
    assert legacy.get_attribute("data-record-id") == "1"
    assert legacy.get_attribute("data-version-id") == ""
    assert not cells[2].find_elements(By.TAG_NAME, "input")
    assert cells[2].find_element(By.TAG_NAME, "span").get_attribute("title") == "Нет записи в этой версии БД"
    legacy.clear()
    legacy.send_keys("new-legacy-code")
    assert legacy.get_attribute("value") == "new-legacy-code"


def test_matching_group_codes_are_not_yellow_and_missing_records_have_a_separate_badge(browser):
    from selenium.webdriver.common.by import By

    browser.get("data:text/html;charset=utf-8," + quote(check_page(with_equipment=True)))
    group = browser.find_element(By.CSS_SELECTOR, ".external-code-equipment-group-row")
    for version_id in (1, 2):
        cell = group.find_element(By.CSS_SELECTOR, f'[data-external-code-version="{version_id}"]')
        assert "table-warning" not in cell.get_attribute("class")
        assert cell.find_element(By.TAG_NAME, "input").get_attribute("value") == "group-code"
    missing = group.find_element(By.CSS_SELECTOR, '[data-external-code-version="3"]')
    assert "table-warning" not in missing.get_attribute("class")
    assert missing.find_element(By.CSS_SELECTOR, ".external-code-missing").text == "– нет записи"
    assert not missing.find_elements(By.TAG_NAME, "input")
    machine = browser.find_element(By.CSS_SELECTOR, ".external-code-machine-row")
    reference = machine.find_element(By.CSS_SELECTOR, '[data-external-code-version="1"]')
    different = machine.find_element(By.CSS_SELECTOR, '[data-external-code-version="2"]')
    assert "table-warning" not in reference.get_attribute("class")
    assert "table-warning" in different.get_attribute("class")
    assert "Код отличается" in different.get_attribute("title")
    assert browser.execute_script("return getComputedStyle(arguments[0]).backgroundColor", reference) != browser.execute_script(
        "return getComputedStyle(arguments[0]).backgroundColor", different,
    )
