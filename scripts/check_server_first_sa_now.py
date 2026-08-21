#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request
from html import unescape

BASE = "http://msk-arm-gs01.ntcees.ru"


def main() -> None:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    login_html = opener.open(f"{BASE}/auth/login", timeout=30).read().decode("utf-8", "replace")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login_html)
    data = {"email": "test-fuel@example.com", "password": "123"}
    if m:
        data["csrf_token"] = m.group(1)
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=urllib.parse.urlencode(data).encode(),
        method="POST",
    )
    opener.open(req, timeout=30).read()
    html = opener.open(f"{BASE}/energy_consumption/summary/oes/", timeout=120).read().decode(
        "utf-8", "replace"
    )
    print("len", len(html))
    vm = re.search(r"Версия БД[:\s]*([^<\n]{0,80})", html)
    print("version line:", unescape(vm.group(0)) if vm else "NOT FOUND")

    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(re.sub(r"\s+", " ", text))

    for label in (
        "Первая синхронная зона с НТ с зарядом ГАЭС",
        "Первая синхронная зона с НТ без заряда ГАЭС",
        "Первая синхронная зона без НТ с зарядом ГАЭС",
        "Первая синхронная зона без НТ без заряда ГАЭС",
    ):
        i = text.find(label)
        nums = re.findall(r"\d(?:\s?\d){2,}(?:,\d+)?", text[i : i + 700])
        print(label)
        print("  nums[8:12]:", nums[8:12] if len(nums) >= 12 else nums)

    for k, needle in (
        ("wrong 2025 withNT without", "1 108 723,9"),
        ("right 2025 withNT without", "1 108 710"),
        ("wrong 2025 withoutNT without", "1 085 509,9"),
        ("right 2025 withoutNT without", "1 085 496"),
        ("wrong 2024 withNT without", "1 123 385"),
        ("right 2024 withNT without", "1 123 347"),
    ):
        print(f"{k}: {needle in text}")


if __name__ == "__main__":
    main()
