# -*- coding: utf-8 -*-
"""Пересъёмка скриншотов отчёта с обезличенным ФИО в шапке."""

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
from app.auth.models.user_model import User
from app.extensions import db

BASE = "http://127.0.0.1:5000"
OUT = Path(r"c:\arm_gs\reports\screenshots")
OUT.mkdir(parents=True, exist_ok=True)
ANON = "ФИО пользователя"
USER_ID = 1

SIMPLE_PAGES = [
    ("01_home", "/"),
    ("02_db_versions", "/generation/stations/database_versions"),
    ("03_refdata", "/refdata/"),
    ("03b_refdata_fuels", "/refdata/fuel"),
    ("04_generation", "/generation/"),
    ("05_stations", "/generation/stations/station_list"),
    ("05b_station_card", "/generation/stations/station_details/35592"),
    ("05c_machine_card", "/generation/stations/machine_details/35592/84536"),
    ("06_power_demand", "/power_demand/"),
    ("07_power_demand_summary", "/power_demand/summary/oes/"),
    ("08_energy_consumption", "/energy_consumption/"),
    ("09_energy_consumption_summary", "/energy_consumption/summary/oes/"),
    ("10_energy_balance", "/energy_balance/"),
    ("11_ee_generation", "/energy_balance/ee_generation/"),
    ("12_power_balance", "/energy_balance/power_balance/"),
    ("13_fuel", "/fuel/"),
    ("13b_fuel_equip_groups", "/fuel/stations_equipment_groups"),
    ("13c_fuel_turbines", "/fuel/stations_turbines"),
    ("13d_fuel_params", "/fuel/stations_equipment_group_fuel_params"),
    (
        "13e_fuel_costs",
        "/fuel/stations_equipment_group_electricity_production_cost",
    ),
    ("13f_fuel_natural", "/fuel/stations_equipment_group_natural_fuel"),
    (
        "13g_fuel_specific_cost",
        "/fuel/stations_equipment_group_specific_fuel_cost",
    ),
    (
        "13h_fuel_heat_tariffs",
        "/fuel/stations_equipment_group_heat_and_tariffs",
    ),
    ("14_fuel_calculation", "/fuel/calculation"),
    ("14b_fuel_balance", "/fuel/equipment_group_fuel_formulas"),
    (
        "14c_fuel_tep",
        "/fuel/stations_equipment_group_specific_fuel_consumption",
    ),
    ("14d_fuel_price", "/fuel/stations_equipment_group_specific_fuel_price"),
    ("14e_fuel_totals", "/fuel/totals_summary"),
    (
        "15_electrical_intensity",
        "/energy_consumption/electrical_intensity_start/",
    ),
    (
        "16_electrical_intensity_fo",
        "/electrical_intensity/electrical_intensity_fo/",
    ),
    ("16b_ei_ved_consumption", "/economics/ved_consumption/"),
    ("16c_economics_hub", "/economics/"),
    ("16d_economics_afci", "/economics/accum_fixed_capital/"),
    ("16e_economics_product_output", "/economics/product_output/"),
    ("16f_economics_population", "/economics/population/"),
    ("16g_economics_monetary_income", "/economics/accum_monetary_income/"),
    ("17_output_documents", "/output_documents_transfer"),
]

PD_TOGGLES_OES = (
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
)

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


def set_username(value: str) -> str:
    app = create_app()
    with app.app_context():
        user = db.session.get(User, USER_ID)
        if user is None:
            raise RuntimeError(f"user id={USER_ID} not found")
        old = user.username
        user.username = value
        db.session.commit()
        print(f"USERNAME: {old!r} -> {value!r}")
        return old


def session_cookie() -> str:
    app = create_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = str(USER_ID)
            sess["_fresh"] = True
            sess["database_version_id"] = 46
        client.get("/")
        return client.get_cookie("session", domain="localhost").value


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1700,1100")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--force-device-scale-factor=1")
    d = webdriver.Chrome(options=opts)
    d.set_page_load_timeout(120)
    d.set_script_timeout(15)
    return d


def auth(d: webdriver.Chrome, cookie: str) -> None:
    d.get(BASE + "/auth/login")
    d.delete_all_cookies()
    d.add_cookie({"name": "session", "value": cookie, "path": "/"})


def mask_fio(d: webdriver.Chrome) -> None:
    """Доп. страховка: заменить ФИО в DOM перед скрином."""
    try:
        d.execute_script(
            """
            const anon = arguments[0];
            const needles = ['Новикова Елена Юрьевна', 'Новикова'];
            document.querySelectorAll('span.me-4.fs-4').forEach(el => {
              el.textContent = anon;
            });
            const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            const nodes = [];
            while (walk.nextNode()) nodes.push(walk.currentNode);
            for (const n of nodes) {
              let t = n.nodeValue;
              if (!t) continue;
              for (const needle of needles) {
                if (t.includes(needle)) {
                  t = t.split(needle).join(anon);
                }
              }
              n.nodeValue = t;
            }
            document.querySelectorAll('.toast,.alert,.modal-backdrop').forEach(e => {
              e.style.display = 'none';
            });
            """,
            ANON,
        )
    except Exception as exc:  # noqa: BLE001
        print("mask warn:", exc)


def shot(d: webdriver.Chrome, stem: str) -> None:
    mask_fio(d)
    d.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.3)
    out = OUT / f"{stem}.png"
    d.save_screenshot(str(out))
    print("OK", stem, out.stat().st_size)


def click_id(d: webdriver.Chrome, element_id: str) -> bool:
    try:
        el = WebDriverWait(d, 8).until(
            EC.presence_of_element_located((By.ID, element_id))
        )
        d.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.1)
        try:
            el.click()
        except ElementClickInterceptedException:
            d.execute_script("arguments[0].click();", el)
        time.sleep(0.5)
        return True
    except TimeoutException:
        print("SKIP", element_id)
        return False


def open_wait(d: webdriver.Chrome, path: str, wait_table: bool = False) -> None:
    d.get(BASE + path)
    WebDriverWait(d, 60).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    if wait_table:
        try:
            WebDriverWait(d, 40).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "table.power-demand-summary-table, #powerDemandSummaryTable, table.table",
                    )
                )
            )
        except TimeoutException:
            pass
    time.sleep(1.2)


def main() -> None:
    old = set_username(ANON)
    d = None
    try:
        cookie = session_cookie()
        d = make_driver()
        auth(d, cookie)

        for stem, path in SIMPLE_PAGES:
            try:
                open_wait(d, path)
                shot(d, stem)
            except Exception as exc:  # noqa: BLE001
                print("FAIL", stem, exc)

        # --- Нагрузки: спец-режимы ---
        open_wait(d, "/power_demand/summary/oes/", wait_table=True)
        for btn in PD_TOGGLES_OES:
            click_id(d, btn)
        shot(d, "07b_pd_summary_oes_all_toggles")
        shot(d, "07c_pd_summary_oes_toolbar")

        open_wait(d, "/power_demand/summary/federal_districts/", wait_table=True)
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdPdSummaryEeToggle",
            "pdPdSummaryChiToggle",
            "pdPdSummaryNtDetailToggle",
        ):
            click_id(d, btn)
        shot(d, "07d_pd_summary_fo_compact")

        open_wait(d, "/power_demand/summary/energy_zones/", wait_table=True)
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdPdSummaryEeToggle",
            "pdPdSummaryChiToggle",
        ):
            click_id(d, btn)
        shot(d, "07e_pd_summary_ez_compact")

        open_wait(d, "/power_demand/ozp_maxima/")
        shot(d, "07f_pd_ozp_maxima")

        open_wait(d, "/power_demand/summary/coeff/oes/", wait_table=True)
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdPdSummaryEeToggle",
            "pdPdSummaryChiToggle",
            "pdPdSummaryNtDetailToggle",
            "pdCoeffMixinColsToggle",
        ):
            click_id(d, btn)
        shot(d, "07g_pd_coeff_oes")

        open_wait(d, "/power_demand/summary/coeff/federal_districts/", wait_table=True)
        for btn in ("pdPdSummaryTerritoryCompactToggle", "pdCoeffMixinColsToggle"):
            click_id(d, btn)
        shot(d, "07h_pd_coeff_fo")

        open_wait(d, "/power_demand/summary/coeff/energy_zones/", wait_table=True)
        for btn in (
            "pdPdSummaryTerritoryCompactToggle",
            "pdCoeffMixinColsToggle",
            "pdPdSummaryChiToggle",
        ):
            click_id(d, btn)
        shot(d, "07i_pd_coeff_ez")

        # --- Спрос: спец-режимы ---
        open_wait(d, "/energy_consumption/summary/oes/", wait_table=True)
        for btn in EC_TOGGLES:
            click_id(d, btn)
        shot(d, "09b_ec_summary_oes_all_toggles")

        open_wait(d, "/energy_consumption/summary/federal_districts/", wait_table=True)
        for btn in (
            "pdEcSummaryTerritoryCompactToggle",
            "pdEcSummaryPerimeterVariantToggle",
            "pdEcSummaryGaesDetailToggle",
            "pdEcSummaryNtDetailToggle",
            "pdEcSummarySiprToggle",
        ):
            click_id(d, btn)
        shot(d, "09c_ec_summary_fo_compact")

        open_wait(d, "/energy_consumption/summary/energy_zones/", wait_table=True)
        for btn in (
            "pdEcSummaryTerritoryCompactToggle",
            "pdEcSummaryGaesDetailToggle",
            "pdEcSummaryNtDetailToggle",
            "pdEcSummaryHideEmptyToggle",
            "pdEcSummarySiprToggle",
        ):
            click_id(d, btn)
        shot(d, "09d_ec_summary_ez_compact")

        open_wait(d, "/energy_consumption/summary/oes/gaes_charge/", wait_table=True)
        for btn in ("pdEcSummaryTerritoryCompactToggle", "filtersToggleBtn"):
            click_id(d, btn)
        shot(d, "09e_ec_gaes_charge")

        open_wait(d, "/energy_consumption/summary_table/start/")
        shot(d, "09f_ec_summary_table_hub")

        open_wait(d, "/energy_consumption/summary_table/oes/", wait_table=True)
        for btn in (
            "pdEcSummaryTerritoryCompactToggle",
            "pdEcSummaryGaesDetailToggle",
            "pdEcSummaryNtDetailToggle",
            "pdEcSummarySiprToggle",
            "pdEcSummaryPerimeterVariantToggle",
        ):
            click_id(d, btn)
        shot(d, "09g_ec_summary_table_oes")

        print("DONE")
    finally:
        if d is not None:
            d.quit()
        set_username(old)


if __name__ == "__main__":
    main()
