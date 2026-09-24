# -*- coding: utf-8 -*-
"""Пересъёмка скриншотов модулей «Спрос» и «Экология» без пересборки DOCX."""

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
USER_ID = 1

EC_TOGGLES = (
    "filtersToggleBtn",
    "importExportToggleBtn",
    "pdEcSummaryTerritoryCompactToggle",
    "pdEcSummaryPerimeterVariantToggle",
    "pdEcSummaryGaesDetailToggle",
    "pdEcSummaryNtDetailToggle",
    "pdEcSummaryHideEmptyToggle",
    "pdEcSummaryIsolatedEnergyUnitsToggle",
    "pdEcSummarySiprToggle",
    "pdEcSummaryVerificationToggle",
)

DEMAND_SIMPLE = [
    ("08_energy_consumption", "/energy_consumption/"),
    ("09_energy_consumption_summary", "/energy_consumption/summary/oes/"),
]

ECOLOGY_PAGES = [
    ("18_ecology", "/ecology/"),
    ("18b_ecology_gis_tek_pg", "/ecology/gis_tek/pg/"),
    ("18c_ecology_gis_tek_zv", "/ecology/gis_tek/pollutants/"),
    ("18d_ecology_analysis_pg", "/ecology/analysis/pg-vse/"),
    ("18e_ecology_operating_tes", "/ecology/operating_tes/vsego/obemy/"),
    ("18f_ecology_new_tes", "/ecology/new_tes/vsego/obemy/"),
    ("18g_ecology_totals", "/ecology/totals_summary/pg-vse/"),
]


def session_cookie() -> str:
    app = create_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = str(USER_ID)
            sess["_fresh"] = True
        client.get("/")
        cookie = client.get_cookie("session", domain="localhost")
        if cookie is None:
            raise RuntimeError("session cookie not found")
        return cookie.value


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1700,1100")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--force-device-scale-factor=1")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(120)
    return driver


def auth(driver: webdriver.Chrome, cookie: str) -> None:
    driver.get(BASE + "/auth/login")
    driver.delete_all_cookies()
    driver.add_cookie({"name": "session", "value": cookie, "path": "/"})


def mask_fio(driver: webdriver.Chrome) -> None:
    driver.execute_script(
        """
        const anon = 'ФИО пользователя';
        document.querySelectorAll('span.me-4.fs-4').forEach(el => {
          el.textContent = anon;
        });
        document.querySelectorAll('.toast,.alert,.modal-backdrop').forEach(e => {
          e.style.display = 'none';
        });
        """
    )


def click_id(driver: webdriver.Chrome, element_id: str) -> None:
    try:
        el = WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.ID, element_id))
        )
    except TimeoutException:
        return
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.15)
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
        except Exception:
            pass


def open_wait(
    driver: webdriver.Chrome,
    path: str,
    *,
    wait_table: bool = False,
    wait_css: str | None = None,
) -> None:
    driver.get(BASE + path)
    WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    if wait_css:
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
            )
        except TimeoutException:
            pass
    if wait_table:
        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "table.table, table.power-demand-summary-table, "
                        "#powerDemandSummaryTable, .table-responsive table",
                    )
                )
            )
        except TimeoutException:
            pass
    time.sleep(1.0)
    mask_fio(driver)


def shot(driver: webdriver.Chrome, stem: str) -> Path:
    mask_fio(driver)
    out = OUT / f"{stem}.png"
    driver.save_screenshot(str(out))
    print("OK", stem, out.stat().st_size)
    return out


def main() -> None:
    cookie = session_cookie()
    driver = make_driver()
    try:
        auth(driver, cookie)
        driver.get(BASE + "/")
        time.sleep(1)
        if "/auth/login" in driver.current_url:
            raise RuntimeError("auth failed")

        for stem, path in DEMAND_SIMPLE:
            open_wait(driver, path, wait_css=".home-outline" if stem.startswith("08") else None)
            if stem.startswith("09_"):
                open_wait(driver, path, wait_table=True)
            shot(driver, stem)

        open_wait(driver, "/energy_consumption/summary/oes/", wait_table=True)
        for btn in EC_TOGGLES:
            click_id(driver, btn)
        shot(driver, "09b_ec_summary_oes_all_toggles")

        open_wait(driver, "/energy_consumption/summary/federal_districts/", wait_table=True)
        for btn in (
            "pdEcSummaryTerritoryCompactToggle",
            "pdEcSummaryPerimeterVariantToggle",
            "pdEcSummaryGaesDetailToggle",
            "pdEcSummaryNtDetailToggle",
            "pdEcSummarySiprToggle",
        ):
            click_id(driver, btn)
        shot(driver, "09c_ec_summary_fo_compact")

        open_wait(driver, "/energy_consumption/summary/energy_zones/", wait_table=True)
        for btn in (
            "pdEcSummaryTerritoryCompactToggle",
            "pdEcSummaryGaesDetailToggle",
            "pdEcSummaryNtDetailToggle",
            "pdEcSummaryHideEmptyToggle",
            "pdEcSummarySiprToggle",
        ):
            click_id(driver, btn)
        shot(driver, "09d_ec_summary_ez_compact")

        open_wait(driver, "/energy_consumption/summary/oes/gaes_charge/", wait_table=True)
        for btn in ("pdEcSummaryTerritoryCompactToggle", "filtersToggleBtn"):
            click_id(driver, btn)
        shot(driver, "09e_ec_gaes_charge")

        open_wait(driver, "/energy_consumption/summary_table/start/")
        shot(driver, "09f_ec_summary_table_hub")

        open_wait(driver, "/energy_consumption/summary_table/oes/", wait_table=True)
        for btn in (
            "pdEcSummaryTerritoryCompactToggle",
            "pdEcSummaryGaesDetailToggle",
            "pdEcSummaryNtDetailToggle",
            "pdEcSummarySiprToggle",
            "pdEcSummaryPerimeterVariantToggle",
        ):
            click_id(driver, btn)
        shot(driver, "09g_ec_summary_table_oes")

        for stem, path in ECOLOGY_PAGES:
            open_wait(
                driver,
                path,
                wait_table=stem not in {"18_ecology"},
                wait_css=".home-outline" if stem == "18_ecology" else None,
            )
            shot(driver, stem)

        print("DONE")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
