# -*- coding: utf-8 -*-
"""Интеграционная проверка создания агрегата пользователем Топливо-редактор/админ."""

from __future__ import annotations

import os
import re
import sys
from html import unescape

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.auth.models.user_model import User
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_access_services import (
    can_fuel_user_add_machine_to_station,
)

STATION_ID = 38138
URL = (
    f"/generation/stations/machine_details/{STATION_ID}/0"
    "?start_year=2024&end_year=2031&rounding_digits=1"
)
STATION_DETAILS_URL = f"/generation/stations/station_details/{STATION_ID}"


def _login_client(client, username: str):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(User.query.filter_by(username=username).first().id)
        sess["_fresh"] = True


def _extract_csrf(html: str, prefix: str) -> str | None:
    pattern = rf'name="{re.escape(prefix)}_csrf_token"[^>]*value="([^"]+)"'
    m = re.search(pattern, html)
    return unescape(m.group(1)) if m else None


def _has_editable_gen_company(html: str) -> bool:
    return 'id="id_gen_company"' in html and 'form-select' in html


def _has_save_button(html: str) -> bool:
    return "Сохранить" in html and 'type="submit"' in html


def _has_readonly_mode(html: str) -> bool:
    return "Режим просмотра" in html


def _has_edit_mode(html: str) -> bool:
    return "Режим редактирования" in html


def _flash_messages(html: str) -> list[str]:
    return re.findall(
        r'class="alert alert-danger[^"]*"[^>]*>\s*(.*?)\s*<button',
        html,
        flags=re.DOTALL,
    )


def _build_post_from_get(html: str, start_year: int, end_year: int, overrides: dict | None = None):
    overrides = overrides or {}
    data = {}
    for prefix in ("main", "adv", "pgu"):
        token = _extract_csrf(html, prefix)
        if token:
            data[f"{prefix}_csrf_token"] = token

    # Минимальный набор полей из GET-формы (hidden + selects defaults)
    for name, value in re.findall(
        r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"',
        html,
    ):
        if name not in data and not name.endswith("_orig"):
            data[name] = value

    for name in re.findall(r'<select[^>]+name="([^"]+)"', html):
        if name not in data:
            data[name] = "0"

    for year in range(start_year, end_year + 1):
        idx = year - start_year
        data.setdefault(f"adv_powers-{idx}-year", str(year))
        data.setdefault(f"adv_powers-{idx}-p_ust", "0")
        data.setdefault(f"adv_powers-{idx}-p_ogr", "0")
        data.setdefault(f"adv_powers-{idx}-p_rasp", "0")
        data.setdefault(f"adv_tes_types-{idx}-year", str(year))
        data.setdefault(f"adv_tes_types-{idx}-tes_type", "0")
        data.setdefault(f"adv_fuels-{idx}-year", str(year))
        data.setdefault(f"adv_fuels-{idx}-fuel_type", "0")
        data.setdefault(f"adv_machine_names-{idx}-year", str(year))
        data.setdefault(f"adv_machine_names-{idx}-year_name", "")

    data.update(overrides)
    return data


def main() -> int:
    app = create_app()
    failures: list[str] = []

    with app.app_context():
        user = User.query.filter_by(username="fuel-test").first()
        if not user:
            print("FAIL: user fuel-test not found")
            return 1
        role_names = {r.name_full for r in user.roles}
        print(f"User: {user.username}, roles: {role_names}")

        station = Station.query.get(STATION_ID)
        if not station:
            print(f"FAIL: station {STATION_ID} not found")
            return 1
        print(f"Station: {station.name}, can_add_machine: {can_fuel_user_add_machine_to_station(user, station)}")

        client = app.test_client()
        _login_client(client, "fuel-test")

        # 1) GET — страница создания агрегата доступна и редактируема
        resp = client.get(URL)
        html = resp.get_data(as_text=True)
        print(f"\n[GET] status={resp.status_code}")
        if resp.status_code != 200:
            failures.append(f"GET expected 200, got {resp.status_code}")
        if _has_readonly_mode(html):
            failures.append("GET: unexpected read-only mode")
        if not _has_edit_mode(html):
            failures.append("GET: missing edit mode indicator")
        if not _has_save_button(html):
            failures.append("GET: Save button missing")
        if not _has_editable_gen_company(html):
            failures.append("GET: gen_company select not editable")
        if 'machine-name-hidden' not in html and 'machine-name-textarea' not in html:
            failures.append("GET: machine name field not present")
        else:
            print("GET: machine name field OK")
        print("GET: edit mode OK" if _has_edit_mode(html) else "GET: edit mode FAIL")

        # 2) POST — пустая форма → flash с конкретными ошибками, поля остаются редактируемыми
        post_empty = _build_post_from_get(html, 2024, 2031, {
            "main_machine_name": "",
            "main_id_gen_company": "0",
            "main_machine_number": "",
        })
        resp_val = client.post(URL, data=post_empty, follow_redirects=True)
        html_val = resp_val.get_data(as_text=True)
        flashes = [re.sub(r"\s+", " ", unescape(f)).strip() for f in _flash_messages(html_val)]
        print(f"\n[POST validation] status={resp_val.status_code}, flashes={flashes}")
        if not flashes:
            failures.append("POST validation: no danger flash messages")
        if not any("Название агрегата" in f or "Организация-собственник" in f for f in flashes):
            failures.append(f"POST validation: expected field-specific flashes, got {flashes}")
        if _has_readonly_mode(html_val):
            failures.append("POST validation: page became read-only after error")
        if not _has_save_button(html_val):
            failures.append("POST validation: Save button missing after error")
        print("POST validation: fields editable OK" if _has_edit_mode(html_val) else "POST validation: edit FAIL")

        # 3) POST — для ДЭС: прямое название без gen_company
        station_type = (station.station_type.name or "").strip().lower() if station.station_type else ""
        if station_type in ("тэс", "гэс", "гаэс"):
            name_overrides = {
                "main_machine_name": "",
                "main_id_gen_company": "0",
                "main_machine_number": "Т-1",
                "adv_machine_names-0-year_name": "Агрегат тест Т-1",
            }
        else:
            name_overrides = {
                "main_machine_name": "Агрегат тест ДЭС",
                "main_id_gen_company": "0",
                "main_machine_number": "ДЭС-1",
            }
        post_name_only = _build_post_from_get(html_val, 2024, 2031, name_overrides)
        resp_val2 = client.post(URL, data=post_name_only, follow_redirects=True)
        html_val2 = resp_val2.get_data(as_text=True)
        flashes2 = [re.sub(r"\s+", " ", unescape(f)).strip() for f in _flash_messages(html_val2)]
        print(f"\n[POST name synced] flashes={flashes2}")
        if any("Организация-собственник" in f for f in flashes2):
            print("POST name synced: gen_company error shown OK")
        else:
            failures.append(f"POST name synced: expected gen_company error, got {flashes2}")
        if any("Название агрегата" in f and "обязательно" in f.lower() for f in flashes2):
            if station_type in ("тэс", "гэс", "гаэс"):
                failures.append("POST name synced: machine_name still required after year name fill")
            else:
                print("POST name only: machine_name filled directly for DES")

        # 4) POST — успешное создание → redirect на machine_id > 0
        def _first_valid_option(html_text: str, select_name: str) -> str:
            block = re.search(
                rf'<select[^>]+name="{re.escape(select_name)}"[^>]*>(.*?)</select>',
                html_text,
                flags=re.DOTALL,
            )
            if not block:
                return "0"
            for val, label in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)', block.group(1)):
                if val and val != "0" and "не указано" not in label.lower():
                    return val
            return "0"

        gen_company_id = _first_valid_option(html_val2, "main_id_gen_company")
        if gen_company_id == "0":
            from app.refdata.models.gen_companies.gen_company_model import GenCompany
            gc = GenCompany.query.filter(GenCompany.name != "не указано").first()
            gen_company_id = str(gc.id) if gc else None

        if not gen_company_id or gen_company_id == "0":
            failures.append("Cannot find gen_company for successful create test")
        else:
            post_ok = _build_post_from_get(html_val2, 2024, 2031, {
                "main_machine_number": "Т-TEST-FUEL",
                "main_id_gen_company": gen_company_id,
                "main_machine_name": "Агрегат тест fuel-test",
                "main_id_condition_type": _first_valid_option(html_val2, "main_id_condition_type"),
                "main_id_energy_area": _first_valid_option(html_val2, "main_id_energy_area"),
                "main_id_tes_machine_type": _first_valid_option(html_val2, "main_id_tes_machine_type"),
                "main_relabing_outcome": "",
            })
            for year_idx in range(2031 - 2024 + 1):
                post_ok[f"adv_tes_types-{year_idx}-tes_type"] = _first_valid_option(
                    html_val2, f"adv_tes_types-{year_idx}-tes_type"
                ) if f"adv_tes_types-{year_idx}-tes_type" in html_val2 else "0"
                post_ok[f"adv_fuels-{year_idx}-fuel_type"] = _first_valid_option(
                    html_val2, f"adv_fuels-{year_idx}-fuel_type"
                ) if f"adv_fuels-{year_idx}-fuel_type" in html_val2 else "0"
            # Для ТЭС/ГЭС/ГАЭС: название из таблицы по годам
            if station_type in ("тэс", "гэс", "гаэс"):
                for year_idx in range(2031 - 2024 + 1):
                    post_ok[f"adv_machine_names-{year_idx}-year_name"] = "Агрегат тест fuel-test"
                post_ok["main_machine_name"] = ""
            print(f"POST create using gen_company={gen_company_id}, energy_area={post_ok.get('main_id_energy_area')}")
            resp_ok = client.post(URL, data=post_ok, follow_redirects=False)
            print(f"\n[POST create] status={resp_ok.status_code}, location={resp_ok.location}")
            if resp_ok.status_code not in (302, 303):
                failures.append(f"POST create: expected redirect, got {resp_ok.status_code}")
                flashes_create = [re.sub(r"\s+", " ", unescape(f)).strip() for f in _flash_messages(resp_ok.get_data(as_text=True))]
                print(f"POST create flashes: {flashes_create}")
            else:
                loc = resp_ok.location or ""
                m_id = re.search(r"/machine_details/\d+/(\d+)", loc)
                if not m_id or m_id.group(1) == "0":
                    failures.append(f"POST create: bad redirect location {loc}")
                else:
                    new_machine_id = int(m_id.group(1))
                    print(f"POST create: new machine_id={new_machine_id}")
                    resp_after = client.get(loc, follow_redirects=True)
                    html_after = resp_after.get_data(as_text=True)
                    success_flashes = re.findall(
                        r'class="alert alert-success[^"]*"[^>]*>\s*(.*?)\s*<button',
                        html_after,
                        flags=re.DOTALL,
                    )
                    if any("успешно создан" in unescape(f).lower() for f in success_flashes):
                        print("POST create: success flash OK")
                    else:
                        failures.append("POST create: missing success flash after redirect")
                    if _has_readonly_mode(html_after) and not _has_edit_mode(html_after):
                        print("POST create: after save — режим просмотра (ожидаемо для fuel-user на существующем агрегате)")
                    elif _has_edit_mode(html_after):
                        print("POST create: after save — режим редактирования")

                    # station_details — кнопка «Добавить агрегат» и переход обратно
                    resp_sd = client.get(STATION_DETAILS_URL)
                    sd_html = resp_sd.get_data(as_text=True)
                    if "Добавить агрегат" not in sd_html:
                        failures.append("station_details: Add machine button missing for fuel user")
                    else:
                        print("station_details: Add machine button OK")

                    # cleanup test machine
                    machine = Machine.query.get(new_machine_id)
                    if machine:
                        db = __import__("app.extensions", fromlist=["db"]).db
                        db.session.delete(machine)
                        db.session.commit()
                        print(f"Cleanup: deleted test machine {new_machine_id}")

    print("\n" + "=" * 60)
    if failures:
        print("FAILED:")
        for f in failures:
            print(" -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
