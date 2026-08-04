# -*- coding: utf-8 -*-
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, r"c:\arm_gs\_otet_analysis\sipr_check")
from validate_access_logic import (  # noqa
    D,
    latest_by_key,
    load_tsv,
    nearly,
    parse_formtxt_access,
)

DIR = Path(r"c:\arm_gs\_otet_analysis\sipr_check")
st_cur = load_tsv(DIR / "st_oes3_2031.csv")
form_all = load_tsv(DIR / "form_oes3.csv")
dop_all = load_tsv(DIR / "dop_oes3_2031.csv")
form_best = latest_by_key(form_all, ("numb1120", "v"), "year", 2031)
dop_by = {str(r.get("numb1")): r for r in dop_all}
out = []

for st in st_cur:
    if str(st["NUMB1120"]) == "108":
        out.append(
            "ST108 "
            + str({k: st.get(k) for k in ["NAME", "NUST", "NR", "E", "H", "HFIX", "OBOR", "EWTP", "B"]})
        )

ok_access = ok_arm = n = 0
fails = []
for st in st_cur:
    n1120 = str(st["NUMB1120"])
    v = str(st.get("v") or "0")
    form = form_best.get((n1120, v)) or form_best.get((n1120, "0"))
    if not form or not form.get("formtxt"):
        continue
    main, extra, used, _ = parse_formtxt_access(form["formtxt"], D(st["B"]), {}, {})
    gaz_acc = D(main.get("gaz"))
    if "gazpp" in used:
        gaz_acc = gaz_acc + D(extra.get("gazpp"))
    gaz_arm = D(extra.get("gaz_prir")) + D(extra.get("gazpp")) + D(main.get("gaz"))
    if "gaz_prir" in used or "gazpp" in used or "gaz" in main:
        n += 1
        stored = D(st.get("GAZ"))
        m_acc = nearly(stored, gaz_acc)
        m_arm = nearly(stored, gaz_arm)
        ok_access += int(m_acc)
        ok_arm += int(m_arm)
        if not m_arm:
            fails.append((n1120, float(stored), float(gaz_acc), float(gaz_arm), form["formtxt"][:70], float(abs(stored - gaz_arm))))

out.append(f"gaz stations={n} access_match={ok_access} arm_groups_match={ok_arm}")
for f in sorted(fails, key=lambda x: x[-1], reverse=True)[:12]:
    out.append("FAIL " + str(f))

# B vs GAZ+MAZUT+... for stations
bal_ok = bal_n = 0
for st in st_cur:
    b = D(st["B"])
    if b <= 0:
        continue
    fuels = D(st["GAZ"]) + D(st["MAZUT"]) + D(st["PROCH"]) + D(st["UGOL"])
    # plus other main coals if any
    for k in ("PECH", "KUZN", "KAN", "URAL"):
        fuels += D(st.get(k))
    bal_n += 1
    if nearly(b, fuels) or abs(b - fuels) / b < Decimal("0.001"):
        bal_ok += 1
    else:
        if abs(b - fuels) > 1:
            out.append(f"BAL {st['NUMB1120']} B={b} fuels={fuels} d={b-fuels}")

out.append(f"fuel balance vs B: {bal_ok}/{bal_n}")

# count HFIX
hfix_n = sum(1 for st in st_cur if str(st.get("HFIX") or "").strip() in ("1", "1.0"))
out.append(f"hfix count={hfix_n}")

Path(DIR / "fuel_diag.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
