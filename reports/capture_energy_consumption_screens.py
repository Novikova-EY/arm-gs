# -*- coding: utf-8 -*-
"""Скриншоты модуля «Спрос»: сводные таблицы с включёнными кнопками (без коэффициентов)."""

from __future__ import annotations

import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app import create_app

BASE = "http://127.0.0.1:5000"
OUT = Path(r"c:\arm_gs\reports\screenshots")
OUT.mkdir(parents=True, exist_ok=True)

TOGGLES = (
    "filtersToggleBtn",
    "importExportToggleBtn",
    "pdEcSummaryTerritoryCompactToggle",  # Сводная таблица
    "pdEcSummaryPerimeterVariantToggle",
    "pdEcSummaryGaesDetailToggle",  # без заряда ГАЭС
    "pdEcSummaryNtDetailToggle",
    "pdEcSummaryHideEmptyToggle",
    "pdEcSummaryIsolatedEnergyUnitsToggle",
    "pdEcSummarySiprToggle",
    "pdEcSummaryVerificationToggle",
)


def session_cookie() -> str:
    app = create_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "1"
            sess["_fresh"] = True
            sess["database_version_id"] = 46
        client.get("/")
        return client.get_cookie("session", domain="localhost").value


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1700,1200")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--force-device-scale-factor=1")
    d = webdriver.Chrome(options=opts)
    d.set_page_load_timeout(120)
    d.set_script_timeout(10)
    return d


def auth(d: webdriver.Chrome, cookie: str) -> None:
    d.get(BASE + "/auth/login")
    d.delete_all_cookies()
    d.add_cookie({"name": "session", "value": cookie, "path": "/"})


def wait_ready(d: webdriver.Chrome) -> None:
    WebDriverWait(d, 90).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    # общая таблица сводок
    try:
        WebDriverWait(d, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.power-demand-summary-table, #powerDemandSummaryTable, table.table"))
        )
    except TimeoutException:
        pass
    time.sleep(2.0)


def click_id(d: webdriver.Chrome, element_id: str) -> bool:
    try:
        el = WebDriverWait(d, 8).until(EC.presence_of_element_located((By.ID, element_id)))
        d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.15)
        try:
            el.click()
        except ElementClickInterceptedException:
            d.execute_script("arguments[0].click();", el)
        time.sleep(0.6)
        return True
    except TimeoutException:
        print("SKIP", element_id)
        return False


def shot(d: webdriver.Chrome, stem: str) -> None:
    try:
        d.execute_script(
            "try{document.querySelectorAll('.toast,.alert,.modal-backdrop')"
            ".forEach(e=>e.style.display='none');}catch(e){}"
        )
    except Exception:
        pass
    path = OUT / f"{stem}.png"
    d.save_screenshot(str(path))
    print("OK", stem, path.stat().st_size)


def open_and_toggle(d: webdriver.Chrome, path: str, toggles: tuple[str, ...]) -> None:
    d.get(BASE + path)
    wait_ready(d)
    for btn in toggles:
        click_id(d, btn)
    d.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.8)


def main() -> None:
    cookie = session_cookie()
    d = make_driver()
    try:
        auth(d, cookie)

        d.get(BASE + "/energy_consumption/")
        wait_ready(d)
        shot(d, "08_energy_consumption")  # refresh hub shot

        open_and_toggle(d, "/energy_consumption/summary/oes/", TOGGLES)
        shot(d, "09b_ec_summary_oes_all_toggles")

        open_and_toggle(
            d,
            "/energy_consumption/summary/federal_districts/",
            (
                "pdEcSummaryTerritoryCompactToggle",
                "pdEcSummaryPerimeterVariantToggle",
                "pdEcSummaryGaesDetailToggle",
                "pdEcSummaryNtDetailToggle",
                "pdEcSummarySiprToggle",
            ),
        )
        shot(d, "09c_ec_summary_fo_compact")

        open_and_toggle(
            d,
            "/energy_consumption/summary/energy_zones/",
            (
                "pdEcSummaryTerritoryCompactToggle",
                "pdEcSummaryGaesDetailToggle",
                "pdEcSummaryNtDetailToggle",
                "pdEcSummaryHideEmptyToggle",
                "pdEcSummarySiprToggle",
            ),
        )
        shot(d, "09d_ec_summary_ez_compact")

        # ГАЭС на заряд
        d.get(BASE + "/energy_consumption/summary/oes/gaes_charge/")
        wait_ready(d)
        for btn in (
            "pdEcSummaryTerritoryCompactToggle",
            "filtersToggleBtn",
        ):
            click_id(d, btn)
        time.sleep(0.8)
        shot(d, "09e_ec_gaes_charge")

        # Отдельный хаб «Сводная таблица»
        d.get(BASE + "/energy_consumption/summary_table/start/")
        wait_ready(d)
        time.sleep(0.8)
        shot(d, "09f_ec_summary_table_hub")

        open_and_toggle(
            d,
            "/energy_consumption/summary_table/oes/",
            (
                "pdEcSummaryTerritoryCompactToggle",
                "pdEcSummaryGaesDetailToggle",
                "pdEcSummaryNtDetailToggle",
                "pdEcSummarySiprToggle",
                "pdEcSummaryPerimeterVariantToggle",
            ),
        )
        shot(d, "09g_ec_summary_table_oes")

        print("DONE")
    finally:
        d.quit()


if __name__ == "__main__":
    main()
