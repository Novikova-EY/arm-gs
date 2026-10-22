# -*- coding: utf-8 -*-
"""Скриншоты модуля «Нагрузки»: сводная таблица и коэффициенты."""

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


def session_cookie() -> str:
    app = create_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "1"
            sess["_fresh"] = True
            sess["database_version_id"] = 46
        client.get("/")
        return client.get_cookie("session", domain="localhost").value


def driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1700,1200")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--force-device-scale-factor=1")
    d = webdriver.Chrome(options=opts)
    d.set_page_load_timeout(90)
    return d


def auth(d: webdriver.Chrome, cookie: str) -> None:
    d.get(BASE + "/auth/login")
    d.delete_all_cookies()
    d.add_cookie({"name": "session", "value": cookie, "path": "/"})


def wait_table(d: webdriver.Chrome) -> None:
    WebDriverWait(d, 60).until(
        EC.presence_of_element_located((By.ID, "powerDemandSummaryTable"))
    )
    time.sleep(1.5)


def click_id(d: webdriver.Chrome, element_id: str) -> bool:
    try:
        el = WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.ID, element_id)))
        d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.2)
        try:
            el.click()
        except ElementClickInterceptedException:
            d.execute_script("arguments[0].click();", el)
        time.sleep(0.8)
        return True
    except TimeoutException:
        print("SKIP missing", element_id)
        return False


def click_seg(d: webdriver.Chrome, seg: str) -> bool:
    try:
        el = d.find_element(By.CSS_SELECTOR, f'button[data-coeff-seg="{seg}"]')
        d.execute_script("arguments[0].click();", el)
        time.sleep(0.8)
        return True
    except Exception:
        print("SKIP seg", seg)
        return False


def shot(d: webdriver.Chrome, stem: str) -> None:
    try:
        d.set_script_timeout(5)
        d.execute_script(
            "try{document.querySelectorAll('.toast,.alert,.modal-backdrop')"
            ".forEach(e=>e.style.display='none');}catch(e){}"
        )
    except Exception:
        pass
    path = OUT / f"{stem}.png"
    d.save_screenshot(str(path))
    print("OK", stem, path.stat().st_size)


def open_page(d: webdriver.Chrome, path: str) -> None:
    d.set_page_load_timeout(120)
    d.get(BASE + path)
    wait_table(d)


def main() -> None:
    cookie = session_cookie()
    d = driver()
    d.set_script_timeout(10)
    try:
        auth(d, cookie)

        # --- Максимумы ОЭС: режим «Сводная таблица» + набор кнопок ---
        open_page(d, "/power_demand/summary/oes/")
        for btn in (
            "filtersToggleBtn",
            "importExportToggleBtn",
            "pdPdSummaryTerritoryCompactToggle",
            "pdPdSummaryEeToggle",
            "pdPdSummaryChiToggle",
            "pdPdSummaryNtDetailToggle",
            "pdPdSummaryPerimeterVariantToggle",
            "pdPdSummaryHistToggle",
            "pdPdSummaryCalcMaxToggle",
            "pdPdSummaryHideEmptyToggle",
            "pdPdSummaryVerificationToggle",
        ):
            click_id(d, btn)
        # не жмём medium/long – они тяжёлые; отчётный период уже включён
        d.execute_script("window.scrollTo(0, 0);")
        time.sleep(1.0)
        shot(d, "07b_pd_summary_oes_all_toggles")
        shot(d, "07c_pd_summary_oes_toolbar")

        # ФО в режиме сводной таблицы
        open_page(d, "/power_demand/summary/federal_districts/")
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdPdSummaryEeToggle",
            "pdPdSummaryChiToggle",
            "pdPdSummaryNtDetailToggle",
        ):
            click_id(d, btn)
        time.sleep(1.0)
        shot(d, "07d_pd_summary_fo_compact")

        # Энергозоны
        open_page(d, "/power_demand/summary/energy_zones/")
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdPdSummaryEeToggle",
            "pdPdSummaryChiToggle",
        ):
            click_id(d, btn)
        time.sleep(1.0)
        shot(d, "07e_pd_summary_ez_compact")

        # ОЗП
        d.get(BASE + "/power_demand/ozp_maxima/")
        WebDriverWait(d, 40).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2.0)
        shot(d, "07f_pd_ozp_maxima")

        # --- Коэффициенты ---
        open_page(d, "/power_demand/summary/coeff/oes/")
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdPdSummaryEeToggle",
            "pdPdSummaryChiToggle",
            "pdPdSummaryNtDetailToggle",
            "pdCoeffMixinColsToggle",
        ):
            click_id(d, btn)
        time.sleep(1.0)
        shot(d, "07g_pd_coeff_oes")

        open_page(d, "/power_demand/summary/coeff/federal_districts/")
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdCoeffMixinColsToggle",
        ):
            click_id(d, btn)
        time.sleep(1.0)
        shot(d, "07h_pd_coeff_fo")

        open_page(d, "/power_demand/summary/coeff/energy_zones/")
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdCoeffMixinColsToggle",
            "pdPdSummaryChiToggle",
        ):
            click_id(d, btn)
        time.sleep(1.0)
        shot(d, "07i_pd_coeff_ez")

        print("DONE")
    finally:
        d.quit()


if __name__ == "__main__":
    main()
