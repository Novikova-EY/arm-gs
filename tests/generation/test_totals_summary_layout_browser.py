"""Layout regression checks using the real summary table and shared styles."""
from pathlib import Path
from urllib.parse import quote

import pytest
from jinja2 import Environment, FileSystemLoader

pytest.importorskip("selenium")
from selenium import webdriver


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = "generation/stations_total_summary/stations_total_summary.html"


@pytest.fixture(scope="module")
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


def summary_page(year_count, page_scroll):
    templates = ROOT / "app/templates"
    source = (templates / TEMPLATE).read_text(encoding="utf-8")
    table = source[source.index("    <style>"):source.index("</table>") + len("</table>")]
    env = Environment(loader=FileSystemLoader(templates), autoescape=True)
    env.filters["format_decimal"] = lambda value: value
    years = range(2025, 2025 + year_count)
    value = "123 456 789,123"
    rendered = env.from_string(table).render(
        start_year=years.start,
        end_year=years.stop - 1,
        year_features={year: "Прогнозный год" for year in years},
        should_show_totals={"total": True},
        total_energy_system_types_yearly_p_ust=dict.fromkeys(years, value),
        total_energy_system_types_yearly_p_ogr=dict.fromkeys(years, value),
        total_energy_system_types_yearly_p_rasp=dict.fromkeys(years, value),
        show_p_ogr=True,
        show_p_rasp=True,
        station_type_list={},
    ) + "</div>"
    styles = "\n".join(
        (ROOT / "app/static/css" / name).read_text(encoding="utf-8")
        for name in ("bootstrap.min.css", "style.css", "table_headers.css")
    )
    if page_scroll:
        rendered = f'<div class="page-table-scroll has-x-scroll">{rendered}</div>'
    return f'<!doctype html><meta charset="utf-8"><style>{styles}</style>{rendered}'


@pytest.mark.parametrize("page_scroll", [False, True])
@pytest.mark.parametrize("year_count, width", [(26, 760), (1, 1440)])
def test_summary_columns_expand_without_wrapping(browser, page_scroll, year_count, width):
    browser.set_window_size(width, 900)
    browser.get("data:text/html;charset=utf-8," + quote(summary_page(year_count, page_scroll)))
    metrics = browser.execute_script("""
        const container = document.getElementById('totalsSummaryTableContainer');
        const host = container.closest('.page-table-scroll') || container;
        const cells = Array.from(container.querySelectorAll('td'));
        const singleLine = cells.every(cell => {
            const range = document.createRange();
            range.selectNodeContents(cell);
            return getComputedStyle(cell).whiteSpace === 'nowrap'
                && range.getBoundingClientRect().height <= parseFloat(getComputedStyle(cell).lineHeight) + 1
                && cell.scrollWidth <= cell.clientWidth + 1;
        });
        host.scrollLeft = host.scrollWidth;
        return {
            singleLine,
            overflow: host.scrollWidth > host.clientWidth + 1,
            scrollLeft: host.scrollLeft,
            value: cells[2].textContent.trim(),
            headerWhiteSpace: getComputedStyle(container.querySelector('th div')).whiteSpace,
            sticky: getComputedStyle(container.querySelector('th')).position,
            tableWidth: container.querySelector('table').getBoundingClientRect().width,
            containerWidth: container.clientWidth
        };
    """)
    assert metrics["singleLine"]
    assert metrics["value"] == "123 456 789,123"
    assert metrics["headerWhiteSpace"] == "nowrap"
    assert metrics["sticky"] == "sticky"
    assert metrics["tableWidth"] >= metrics["containerWidth"] - 1
    assert metrics["overflow"] is (year_count > 1)
    assert (metrics["scrollLeft"] > 0) is (year_count > 1)
