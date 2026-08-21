#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import http.cookiejar
import re
import urllib.parse
import urllib.request
from html import unescape

BASE = "http://msk-arm-gs01.ntcees.ru"


def fetch(email: str) -> str:
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    login = op.open(BASE + "/auth/login", timeout=30).read().decode("utf-8", "replace")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login)
    data = {"email": email, "password": "123"}
    if m:
        data["csrf_token"] = m.group(1)
    req = urllib.request.Request(
        BASE + "/auth/login",
        data=urllib.parse.urlencode(data).encode(),
        method="POST",
    )
    op.open(req, timeout=30).read()
    return op.open(
        BASE + "/energy_consumption/summary/oes/", timeout=120
    ).read().decode("utf-8", "replace")


def main() -> None:
    for email in ("test-fuel@example.com", "novikova-eyu@ntcees.ru"):
        html = fetch(email)
        i = html.find("Версия БД")
        snippet = unescape(re.sub(r"<[^>]+>", " ", html[i : i + 800]))
        snippet = re.sub(r"\s+", " ", snippet)
        print("=" * 60)
        print(email)
        print("snippet:", snippet[:300])
        # selected version in dropdowns that contain СиПР
        for m in re.finditer(
            r"<select[^>]*>([\s\S]*?)</select>", html, flags=re.I
        ):
            block = m.group(1)
            if "СиПР" in block or "ТОПЛИВО" in block or "version" in block.lower():
                sel = re.findall(
                    r'<option[^>]*selected[^>]*>(.*?)</option>',
                    block,
                    flags=re.I | re.S,
                )
                opts = re.findall(r"<option[^>]*>(.*?)</option>", block, flags=re.I | re.S)
                print(
                    "select with SIPR selected=",
                    [re.sub(r"\s+", " ", unescape(x)).strip() for x in sel],
                )
                print(
                    "all opts sample=",
                    [re.sub(r"\s+", " ", unescape(x)).strip() for x in opts[:8]],
                )
        print("wrong", "1 108 723,9" in html, "right", "1 108 710" in html)


if __name__ == "__main__":
    main()
