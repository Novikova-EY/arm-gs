# -*- coding: utf-8 -*-
"""Extract VBA code sections and key form captions from Access SaveAsText exports."""
from pathlib import Path
import re

vba = Path(r"c:\arm_gs\_otet_analysis\vba")
out = Path(r"c:\arm_gs\_otet_analysis\extracted")
out.mkdir(exist_ok=True)

def read_access_text(p: Path) -> str:
    raw = p.read_bytes()
    if raw[:2] == b"\xff\xfe":
        return raw.decode("utf-16")
    if raw[:2] == b"\xfe\xff":
        return raw.decode("utf-16-be")
    # try utf-16-le without BOM
    try:
        t = raw.decode("utf-16-le")
        if "Version =" in t or "Begin Form" in t or "Attribute" in t:
            return t
    except Exception:
        pass
    for enc in ("utf-8", "cp1251"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", errors="replace")

key_forms = [
    "form_Редактирование_отчетных_данных.txt",
    "form_Редактирование_типовых_удельных.txt",
    "form_Типовые_удельные_расходы.txt",
    "form_Выбор_варианта.txt",
    "form_Список_вариантов.txt",
    "form_Составные-станции.txt",
    "form_Станции_отчет.txt",
    "form_Итог.txt",
    "form_Натура.txt",
    "form_Редактирование_натуры.txt",
    "form_Справка.txt",
    "form_Форма1.txt",
    "form_9-ПС.txt",
]

for name in key_forms:
    p = vba / name
    if not p.exists():
        print("MISSING", name)
        continue
    text = read_access_text(p)
    # extract CodeBehindForm section
    m = re.search(r"CodeBehindForm\s*(.*)\Z", text, re.S | re.I)
    code = m.group(1) if m else ""
    # also captions / buttons of interest
    captions = re.findall(r'Caption\s*=\s*"([^"]{2,80})"', text)
    captions = [c for c in captions if any(k in c.lower() for k in (
        "расч", "счет", "удель", "типов", "вариант", "персп", "отчет", "натур",
        "топлив", "итог", "формул", "коэф", "станц", "откры", "закры", "сохра",
        "обнов", "копи", "удал", "добав", "фильтр", "справ"
    )) or len(c) > 3]
    safe = name.replace("form_", "").replace(".txt", "")
    (out / f"{safe}_code.bas").write_text(code, encoding="utf-8")
    (out / f"{safe}_captions.txt").write_text("\n".join(dict.fromkeys(captions)), encoding="utf-8")
    print(f"{safe}: code_chars={len(code)} captions={len(captions)}")
    for c in captions[:30]:
        print("  CAP:", c)

# dump module again as clean utf-8
mod = vba / "mod_Модуль1.txt"
(out / "Модуль1.bas").write_text(read_access_text(mod), encoding="utf-8")

# list query files with Russian names related to calc
qdir = Path(r"c:\arm_gs\_otet_analysis\queries")
print("\n=== Interesting queries ===")
for p in sorted(qdir.glob("*.sql")):
    n = p.stem.lower()
    if any(k in n for k in ("расч", "удель", "персп", "btp", "eotp", "ewtp", "формул", "типов", "коэфф", "ved", "цена", "топлив")):
        sql = p.read_text(encoding="utf-8", errors="replace")
        print(f"\n## {p.stem}")
        print(sql[:1200])
