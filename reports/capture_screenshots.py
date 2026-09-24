# -*- coding: utf-8 -*-
"""Скриншоты ключевых страниц АРМ ГС для отчёта Этапа 1."""

from __future__ import annotations

import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app import create_app

BASE = "http://127.0.0.1:5000"
OUT = Path(r"c:\arm_gs\reports\screenshots")
OUT.mkdir(parents=True, exist_ok=True)

# (file_stem, path, caption, chapter_key, wait_css_optional)
PAGES = [
    ("01_home", "/", "Главная страница АРМ «Генеральная схема»", "infra", ".home-outline"),
    (
        "02_db_versions",
        "/generation/stations/database_versions",
        "Управление версиями базы данных",
        "infra",
        None,
    ),
    ("03_refdata", "/refdata/", "Подсистема «Справочники» (стартовая страница)", "refdata", None),
    (
        "04_generation",
        "/generation/",
        "Подсистема «Генерация» (стартовая страница)",
        "generation",
        None,
    ),
    (
        "05_stations",
        "/generation/stations/station_list",
        "Реестр электростанций модуля «Генерация»",
        "generation",
        None,
    ),
    (
        "05b_station_card",
        "/generation/stations/station_details/35592",
        "Карточка электростанции",
        "generation",
        None,
    ),
    (
        "05c_machine_card",
        "/generation/stations/machine_details/35592/84536",
        "Карточка агрегата",
        "generation",
        None,
    ),
    (
        "03b_refdata_fuels",
        "/refdata/fuel",
        "Пример справочника видов топлива",
        "refdata",
        None,
    ),
    (
        "06_power_demand",
        "/power_demand/",
        "Подсистема «Нагрузки» (стартовая страница)",
        "loads",
        None,
    ),
    (
        "07_power_demand_summary",
        "/power_demand/summary/oes/",
        "Сводная таблица нагрузок по ОЭС",
        "loads",
        None,
    ),
    (
        "08_energy_consumption",
        "/energy_consumption/",
        "Подсистема «Спрос» (стартовая страница)",
        "demand",
        None,
    ),
    (
        "09_energy_consumption_summary",
        "/energy_consumption/summary/oes/",
        "Сводная таблица спроса (потребления ЭЭ) по ОЭС",
        "demand",
        None,
    ),
    (
        "10_energy_balance",
        "/energy_balance/",
        "Подсистема «Балансы электроэнергии и мощности»",
        "balance",
        None,
    ),
    (
        "11_ee_generation",
        "/energy_balance/ee_generation/",
        "Раздел выработки электрической энергии",
        "balance",
        None,
    ),
    (
        "12_power_balance",
        "/energy_balance/power_balance/",
        "Раздел балансов мощности",
        "balance",
        None,
    ),
    ("13_fuel", "/fuel/", "Подсистема «Топливо» (стартовая страница)", "fuel", None),
    (
        "14_fuel_calculation",
        "/fuel/calculation",
        "Расчётный контур модуля «Топливо»",
        "fuel",
        None,
    ),
    (
        "15_electrical_intensity",
        "/energy_consumption/electrical_intensity_start/",
        "Подсистема «Электроёмкость» (долгосрочный прогноз потребления)",
        "ei",
        None,
    ),
    (
        "16_electrical_intensity_fo",
        "/electrical_intensity/electrical_intensity_fo/",
        "Таблица электроёмкости по федеральным округам",
        "ei",
        None,
    ),
    (
        "17_output_documents",
        "/output_documents_transfer",
        "Передача данных для выходных документов",
        "docs",
        None,
    ),
]


def make_session_cookie() -> str:
    app = create_app()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_user_id"] = "1"
            sess["_fresh"] = True
        client.get("/")
        cookie = client.get_cookie("session", domain="localhost")
        if cookie is None:
            # fallback: any session cookie
            for c in client._cookies.values():  # type: ignore[attr-defined]
                if getattr(c, "key", None) == "session":
                    return c.value
            raise RuntimeError("session cookie not found")
        return cookie.value


def build_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1600,1000")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--force-device-scale-factor=1")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    return driver


def inject_auth(driver: webdriver.Chrome, session_value: str) -> None:
    driver.get(BASE + "/auth/login")
    time.sleep(0.5)
    driver.delete_all_cookies()
    driver.add_cookie(
        {
            "name": "session",
            "value": session_value,
            "path": "/",
        }
    )


def shot(driver: webdriver.Chrome, stem: str, path: str, wait_css: str | None) -> Path:
    url = BASE + path
    driver.get(url)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    if wait_css:
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
            )
        except Exception:
            pass
    time.sleep(1.2)
    # hide flash/toasts if any
    driver.execute_script(
        """
        document.querySelectorAll('.toast, .alert, .modal-backdrop').forEach(e => e.style.display='none');
        """
    )
    out = OUT / f"{stem}.png"
    driver.save_screenshot(str(out))
    return out


def main() -> None:
    print("Creating session cookie...")
    session_value = make_session_cookie()
    print("Cookie OK", session_value[:16], "...")
    driver = build_driver()
    try:
        inject_auth(driver, session_value)
        # verify auth
        driver.get(BASE + "/")
        time.sleep(1)
        html = driver.page_source
        if "home-outline" not in html and "/auth/login" in driver.current_url:
            raise RuntimeError("Auth failed – redirected to login")
        print("Auth OK, current:", driver.current_url)
        meta = []
        for stem, path, caption, chapter, wait_css in PAGES:
            try:
                out = shot(driver, stem, path, wait_css)
                print("OK", stem, out.stat().st_size, path)
                meta.append((stem, path, caption, chapter, str(out)))
            except Exception as exc:  # noqa: BLE001
                print("FAIL", stem, path, exc)
        # write manifest
        lines = ["stem\tchapter\tcaption\tpath\tfile"]
        for stem, path, caption, chapter, f in meta:
            lines.append(f"{stem}\t{chapter}\t{caption}\t{path}\t{f}")
        (OUT / "manifest.tsv").write_text("\n".join(lines), encoding="utf-8")
        print("Saved", len(meta), "screenshots")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
