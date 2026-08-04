# -*- coding: utf-8 -*-
from pathlib import Path
import re
from html import unescape

html = Path(r"c:/arm_gs/_otet_analysis/sipr_check/calc_page.html").read_text(
    encoding="utf-8", errors="replace"
)
icons = list(re.finditer(r"<i[^>]*bi-info-circle[^>]*>", html, re.I))
print("info icons", len(icons))
lines = []
for m in icons:
    tag = m.group(0)
    title_m = re.search(r'title="([^"]*)"', tag)
    tip = unescape(title_m.group(1)) if title_m else "(no title)"
    start = max(0, m.start() - 300)
    ctx = re.sub(r"<[^>]+>", " ", html[start : m.end()])
    ctx = re.sub(r"\s+", " ", ctx).strip()[-140:]
    lines.append(f"CTX: {ctx}\nTIP: {tip}\n")
Path(r"c:/arm_gs/_otet_analysis/sipr_check/calc_page_tips.txt").write_text(
    "\n".join(lines), encoding="utf-8"
)
print("wrote tips", len(lines))
# also title= on filter checkbox
for m in re.finditer(r'title="([^"]{20,})"', html):
    t = unescape(m.group(1))
    if "Аналог" in t or "hn" in t or "kobl" in t or "ЧЧИУМ" in t:
        print("EXTRA:", t[:200])
