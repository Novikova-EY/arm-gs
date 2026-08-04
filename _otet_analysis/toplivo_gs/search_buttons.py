# -*- coding: utf-8 -*-
from pathlib import Path
import re

vba = Path(r"c:\arm_gs\_otet_analysis\toplivo_gs\vba")
out = Path(r"c:\arm_gs\_otet_analysis\toplivo_gs\extracted")
out.mkdir(exist_ok=True)

def read_access_text(p: Path) -> str:
    raw = p.read_bytes()
    if raw[:2] == b"\xff\xfe":
        return raw.decode("utf-16")
    try:
        t = raw.decode("utf-16-le")
        if "Version =" in t or "Begin Form" in t or "Attribute" in t or "CodeBehindForm" in t:
            return t
    except Exception:
        pass
    for enc in ("utf-8", "cp1251"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", errors="replace")

keywords = ["коэфф", "распред", "топливо", "ераспред", "етек", "схема", "статистик", "огранич", "счет"]

hits = []
for p in sorted(vba.glob("*.txt")):
    text = read_access_text(p)
    low = text.lower()
    caps = re.findall(r'Caption\s*=\s*"([^"]+)"', text)
    matched_kw = [k for k in keywords if k in low]
    matched_cap = [c for c in caps if any(k in c.lower() for k in keywords + ["коэф", "расч", "топл", "стат", "огран"])]
    if matched_kw or matched_cap or "расчет" in p.name.lower() or p.name.lower().startswith("form_w") or p.stem in (
        "form_W", "form_U", "form_Dop", "form_topl", "form_Q", "form_Расчет", "mod_Модуль1"
    ):
        m = re.search(r"CodeBehindForm\s*(.*)\Z", text, re.S | re.I)
        code = m.group(1) if m else text if p.name.startswith("mod_") else ""
        safe = p.stem
        if code.strip():
            (out / f"{safe}_code.bas").write_text(code, encoding="utf-8")
        (out / f"{safe}_captions.txt").write_text("\n".join(dict.fromkeys(caps)), encoding="utf-8")
        hits.append((p.name, matched_kw, matched_cap[:20], len(code)))

print("HITS:")
for h in hits:
    print(h[0], "kw=", h[1], "caps=", h[2], "code=", h[3])

# Also dump full module
mod = list(vba.glob("mod_*.txt"))
for p in mod:
    (out / (p.stem + ".bas")).write_text(read_access_text(p), encoding="utf-8")
    print("module dumped", p.name, "len", p.stat().st_size)
