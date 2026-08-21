#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сравнение сводки ОЭС под двумя учётками на msk-arm-gs01."""
from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request
from html import unescape

BASE = "http://msk-arm-gs01.ntcees.ru"
USERS = (
    ("test-fuel@example.com", "123"),
    ("novikova-eyu@ntcees.ru", "123"),
)


def fetch(email: str, password: str) -> str:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    login_html = opener.open(f"{BASE}/auth/login", timeout=30).read().decode("utf-8", "replace")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login_html)
    data = {"email": email, "password": password}
    if m:
        data["csrf_token"] = m.group(1)
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=urllib.parse.urlencode(data).encode(),
        method="POST",
    )
    opener.open(req, timeout=30).read()
    return opener.open(f"{BASE}/energy_consumption/summary/oes/", timeout=120).read().decode(
        "utf-8", "replace"
    )


def plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return unescape(re.sub(r"\s+", " ", text))


def extract(html: str) -> dict:
    text = plain(html)
    out: dict = {"email_in_page": None, "version": None, "rows": {}}
    em = re.search(r"[\w.+-]+@[\w.-]+", text)
    # version selected option
    vm = re.search(
        r'<select[^>]*id="[^"]*version[^"]*"[^>]*>([\s\S]*?)</select>',
        html,
        flags=re.I,
    )
    if not vm:
        vm = re.search(
            r'name="[^"]*version[^"]*"[^>]*>([\s\S]*?)</select>',
            html,
            flags=re.I,
        )
    selected = re.findall(
        r'<option[^>]*selected[^>]*>([^<]+)</option>|<option[^>]*selected[^>]*value="([^"]*)"',
        html,
        flags=re.I,
    )
    # broader: selected options near СиПР / version
    sel_opts = re.findall(
        r'<option[^>]*selected[^>]*>(.*?)</option>',
        html,
        flags=re.I | re.S,
    )
    out["selected_options"] = [re.sub(r"\s+", " ", unescape(x)).strip() for x in sel_opts[:15]]
    out["has_can_edit_inputs"] = 'class="form-control form-control-lg text-center fuel-param-input"' in html
    out["formula_derived_count"] = html.count("pd_ec_formula_derived") + html.count(
        "Расчётная строка"
    )
    for label in (
        "Первая синхронная зона с НТ с зарядом ГАЭС",
        "Первая синхронная зона с НТ без заряда ГАЭС",
        "Первая синхронная зона без НТ с зарядом ГАЭС",
        "Первая синхронная зона без НТ без заряда ГАЭС",
    ):
        i = text.find(label)
        nums = re.findall(r"\d(?:\s?\d){2,}(?:,\d+)?", text[i : i + 700]) if i >= 0 else []
        # decade end usually indices ~8,9 for 2016-2025
        out["rows"][label] = nums[8:12] if len(nums) >= 12 else nums
    out["wrong_1108723"] = "1 108 723,9" in text
    out["right_1108710"] = "1 108 710" in text
    out["wrong_1085509"] = "1 085 509,9" in text
    out["right_1085496"] = "1 085 496" in text
    # user display name
    um = re.search(r"(Новикова|test-fuel|Test)[^<]{0,40}", html)
    out["user_hint"] = unescape(um.group(0)).strip() if um else None
    return out


def main() -> None:
    for email, password in USERS:
        print("=" * 72)
        print(email)
        try:
            html = fetch(email, password)
        except Exception as e:
            print("FETCH ERROR:", e)
            continue
        info = extract(html)
        print("len", len(html))
        print("user_hint", info["user_hint"])
        print("selected_options", info["selected_options"])
        print("editable_inputs", info["has_can_edit_inputs"])
        print("formula_hint_count", info["formula_derived_count"])
        print("wrong_1108723", info["wrong_1108723"], "right_1108710", info["right_1108710"])
        print("wrong_1085509", info["wrong_1085509"], "right_1085496", info["right_1085496"])
        for label, nums in info["rows"].items():
            short = label.replace("Первая синхронная зона ", "")
            print(f"  {short}: {nums}")


if __name__ == "__main__":
    main()
