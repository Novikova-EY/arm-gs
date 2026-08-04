# -*- coding: utf-8 -*-
from pathlib import Path
import sys
from decimal import Decimal

sys.path.insert(0, r"c:\arm_gs\_otet_analysis\sipr_check")
from validate_access_logic import D, latest_by_key, load_tsv, nearly, parse_formtxt_access

DIR = Path(r"c:\arm_gs\_otet_analysis\sipr_check")
st = load_tsv(DIR / "st_oes3_2031.csv")
# Need ISK_GAZ etc - re-export fuller columns? Check what we have
print("cols", list(st[0].keys()))

# Re-check H: maybe E and H from different stages; compare H*NUST/1000 vs E
for row in st:
    if str(row["NUMB1120"]) == "108":
        e = D(row["E"]); h = D(row["H"]); n = D(row["NUST"])
        print("108 E from H", h * n / 1000, "stored E", e, "ewtp*1.04", D(row["EWTP"]) * Decimal("1.04"))

# Full fuel balance if we had more fields - export quickly via existing GAZ etc
form_all = load_tsv(DIR / "form_oes3.csv")
form_best = latest_by_key(form_all, ("numb1120", "v"), "year", 2031)
ok = n = 0
samples = []
for row in st:
    n1120 = str(row["NUMB1120"])
    form = form_best.get((n1120, "0"))
    if not form or not form.get("formtxt"):
        continue
    main, extra, used, _ = parse_formtxt_access(form["formtxt"], D(row["B"]), {}, {})
    # reconstruct expected main fuels ARM-style for common pattern
    gaz = D(extra.get("gaz_prir")) + D(extra.get("gazpp")) + D(main.get("gaz"))
    mazut = D(extra.get("disel")) + D(extra.get("maztop")) + D(extra.get("nft_proch")) + D(main.get("mazut"))
    proch = D(extra.get("koks_g")) + D(extra.get("prochgaz")) + D(extra.get("tvproch"))
    # Access proch style
    if not (used & {"koks_g", "koksdom", "prochgaz", "tvproch"}):
        proch = D(main.get("proch"))
    stored_g, stored_m = D(row["GAZ"]), D(row["MAZUT"])
    n += 1
    g_ok = nearly(stored_g, gaz)
    m_ok = nearly(stored_m, mazut) if ("maztop" in used or "disel" in used or "mazut" in main) else True
    ok += int(g_ok and m_ok)
    if not (g_ok and m_ok):
        samples.append((n1120, form["formtxt"][:50], float(stored_g), float(gaz), float(stored_m), float(mazut)))

print(f"ARM-style gaz/mazut match {ok}/{n}")
for s in samples[:8]:
    print("sample", s)

# How many formtxt use gaz_prir/maztop vs classic gaz=
classic = armish = 0
for form in form_best.values():
    t = (form.get("formtxt") or "").lower()
    if not t:
        continue
    if "gaz_prir" in t or "maztop" in t or "gazpp" in t:
        armish += 1
    if "gaz=" in t or t.startswith("gaz;") or ";gaz;" in f";{t};":
        classic += 1
print("formtxt armish", armish, "classic_gaz_token", classic, "total", len(form_best))
