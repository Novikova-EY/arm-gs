# -*- coding: utf-8 -*-
"""Validate Access MDB stored results vs VBA/Python calculation formulas."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

DIR = Path(r"c:\arm_gs\_otet_analysis\sipr_check")
TOL_REL = Decimal("1e-6")
TOL_ABS = Decimal("1e-4")


def D(x) -> Decimal:
    if x is None or x == "":
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    s = str(x).strip().replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def load_tsv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        parts = ln.split("\t")
        if len(parts) < len(headers):
            parts += [""] * (len(headers) - len(parts))
        rows.append({headers[i]: parts[i] for i in range(len(headers))})
    return rows


def nearly(a: Decimal, b: Decimal) -> bool:
    if a == b:
        return True
    diff = abs(a - b)
    if diff <= TOL_ABS:
        return True
    scale = max(abs(a), abs(b), Decimal("1"))
    return diff / scale <= TOL_REL


def latest_by_key(rows: list[dict], key_fields: tuple[str, ...], year_field: str, max_year: int):
    best = {}
    for r in rows:
        y = int(float(r[year_field])) if r.get(year_field) not in ("", None) else None
        if y is None or y > max_year:
            continue
        key = tuple(str(r.get(k, "")) for k in key_fields)
        prev = best.get(key)
        if prev is None or int(float(prev[year_field])) < y:
            best[key] = r
    return best


def parse_formtxt_access(formtxt: str, total_b: Decimal, prior_main: dict, prior_extra: dict):
    """Access-like: pct>=0 percent; pct<0 absolute from prior; residual name gets remainder."""
    UGLI1 = {
        "nazar", "ibor", "berez", "per", "irbei", "kansk", "gusin", "tugn", "okino",
        "azey", "mug", "cher", "jer", "karab", "har", "urt", "tataur", "tarbag", "zab_kam",
        "vork", "intin", "sver", "chel", "kizel", "sosv", "neru", "zyryan", "pyak", "rai",
        "erk", "svo", "bikin", "razdol", "hankai", "bering", "anad", "ekib", "maikub",
        "kuznt", "kuzngd", "kuznss", "kuznun", "gazpp", "koksdom", "prochgaz", "tvproch",
        # ARM-era leaves present in this MDB
        "gaz_prir", "disel", "maztop", "nft_proch", "koks_g", "domen_g", "szh_gaz", "inoe",
        "ogodj", "karag", "karajyra", "teniz", "luch", "tal",
    }
    main = {}
    extra = {}
    used = set()
    residual = None
    remaining = total_b
    if not formtxt or not str(formtxt).strip():
        return main, extra, used, residual

    parts = [p.strip() for p in str(formtxt).split(";") if p.strip()]
    for part in parts:
        lev = False
        if "=" in part:
            raw_name, raw_val = part.split("=", 1)
            name = raw_name.strip().lower()
            if name.startswith("/"):
                lev = True
                name = name[1:].strip().lower()
            pct = D(raw_val)
            if pct >= 0:
                base = remaining if lev else total_b
                value = base * pct / Decimal("100")
            else:
                value = D(prior_extra.get(name) if name in UGLI1 else prior_main.get(name))
            remaining -= value
            used.add(name)
            if name in UGLI1:
                extra[name] = value
            else:
                main[name] = value
        else:
            residual = part.strip().lower()
            used.add(residual)

    if residual:
        if residual in UGLI1:
            extra[residual] = remaining
        else:
            main[residual] = remaining
    return main, extra, used, residual


def energy_from_access(st: dict, ud: dict) -> dict:
    e = D(st.get("E"))
    q = D(st.get("Q"))
    qotr = D(st.get("QOTR"))
    turt = D(st.get("TURT"))
    nust = D(st.get("NUST"))
    y = D(ud.get("y"))
    snk = D(ud.get("snk"))
    sntp = D(ud.get("sntp"))
    bk = D(ud.get("bk"))
    btp = D(ud.get("btp"))
    snbas = D(ud.get("snbas"))
    ksn = D(ud.get("Ksn"))
    bbas = D(ud.get("bbas"))
    kh = D(ud.get("Kh"))
    try:
        ved = int(float(st.get("VED") or 0))
    except Exception:
        ved = 0

    ewtp = qotr * y / Decimal("1000")
    hours_util = (e / nust) / Decimal("8.76") if nust > 0 else Decimal("0")
    if ved in (1, 4) and ksn > 0 and nust > 0:
        sn_eff = snbas - hours_util * ksn
        ekotp = (e - ewtp) * (Decimal("1") - sn_eff / Decimal("100"))
    else:
        ekotp = (e - ewtp) * (Decimal("1") - snk / Decimal("100"))
    etpotp = ewtp * sntp
    eotp = ekotp + etpotp
    if ved in (1, 4) and kh > 0 and nust > 0:
        eust = eotp * (bbas - hours_util * kh) / Decimal("1000")
    else:
        eust = (ekotp * bk + etpotp * btp) / Decimal("1000")
    eurt = eust / eotp * Decimal("1000") if eotp > 0 else Decimal("0")
    tust = q * turt / Decimal("1000")
    b = eust + tust
    return {
        "EWTP": ewtp,
        "EOTP": eotp,
        "EUST": eust,
        "EURT": eurt,
        "TUST": tust,
        "B": b,
    }


def main():
    params = load_tsv(DIR / "params.csv")
    param = next(
        p
        for p in params
        if p.get("name") == "ТЭС Волгаэнерго" and str(p.get("year")).startswith("2031")
    )
    e_target = D(param["e"])
    byear = int(float(param["byear"]))
    cyear = int(float(param["year"]))
    print(f"Param: {param['name']} cyear={cyear} byear={byear} E={e_target} k={param['k']}")

    st_base = load_tsv(DIR / "st_oes3_2024.csv")
    st_cur = load_tsv(DIR / "st_oes3_2031.csv")
    ud_all = load_tsv(DIR / "ud_oes3.csv")
    form_all = load_tsv(DIR / "form_oes3.csv")
    dop_all = load_tsv(DIR / "dop_oes3_2031.csv")

    ud_best = latest_by_key(ud_all, ("numb1120", "v"), "year", cyear)
    form_best = latest_by_key(form_all, ("numb1120", "v"), "year", cyear)
    dop_by_numb1 = {str(r.get("numb1")): r for r in dop_all}

    # --- Коэфф aggregates ---
    bsumnust = bsume = bsumetp = bsumq = bsumqotr = Decimal("0")
    for r in st_base:
        bsumnust += D(r["NUST"])
        bsume += D(r["E"])
        bsumetp += D(r["EWTP"])
        bsumq += D(r["Q"])
        bsumqotr += D(r["QOTR"])

    csumnust = csumetp = csumq = csumqotr = Decimal("0")
    csumnustn = csumnustngt = csumnustnpg = Decimal("0")
    sum_e = Decimal("0")
    skipped_no_ud = 0
    base_by_n1120 = {str(r["NUMB1120"]): r for r in st_base}

    energy_checks = []
    h_checks = []
    fuel_checks = []

    for st in st_cur:
        n1120 = str(st["NUMB1120"])
        v = str(st.get("v") or "0")
        key = (n1120, v)
        ud = ud_best.get(key) or ud_best.get((n1120, "0"))
        if ud is None:
            skipped_no_ud += 1
            continue

        # Access Skip only if no U — here we have U
        base = base_by_n1120.get(n1120)
        base_nust = D(base["NUST"]) if base else Decimal("0")

        calc = energy_from_access(st, ud)
        csumnust += D(st["NUST"])
        if base_nust == 0:
            n_cur = D(st["NUST"])
            csumnustn += n_cur
            oc = int(float(st["OBOR"] or 0)) if st.get("OBOR") not in ("", None) else 0
            if oc in (20, 90):
                csumnustngt += n_cur
            if oc in (21, 91):
                csumnustnpg += n_cur
        csumetp += calc["EWTP"]  # after recalc
        csumq += D(st["Q"])
        csumqotr += D(st["QOTR"])
        sum_e += D(st["E"])

        for field in ("EWTP", "EOTP", "EUST", "EURT", "TUST", "B"):
            stored = D(st.get(field))
            got = calc[field]
            energy_checks.append(
                (nearly(stored, got), n1120, st.get("NAME"), field, stored, got, abs(stored - got))
            )

        # H consistency after distribution: if NUST>0 then H = E/NUST*1000
        nust = D(st["NUST"])
        if nust > 0:
            h_exp = D(st["E"]) / nust * Decimal("1000")
            h_st = D(st["H"])
            h_checks.append((nearly(h_st, h_exp), n1120, st.get("NAME"), h_st, h_exp, abs(h_st - h_exp)))

        # Fuel formtxt consistency (main fields after Access-like parse + gaz+=gazpp / basin flags)
        form = form_best.get(key) or form_best.get((n1120, "0"))
        if form and form.get("formtxt"):
            dop = dop_by_numb1.get(str(st.get("numb1")), {})
            prior_main = {k.lower(): D(st.get(k)) for k in ("GAZ", "MAZUT", "PROCH", "UGOL", "PECH", "KUZN", "KAN", "URAL")}
            # for absolute tokens we'd need prior; for % compare using B stored
            main, extra, used, _ = parse_formtxt_access(
                form["formtxt"], D(st["B"]), prior_main, {k.lower(): D(dop.get(k)) for k in dop}
            )
            # Access gaz += gazpp
            if "gazpp" in used:
                main["gaz"] = D(main.get("gaz")) + D(extra.get("gazpp"))
            # mazut from maztop if ARM-style (Access may leave mazut only if named); compare GAZ/MAZUT if present
            if "maztop" in used and "mazut" not in main:
                # ARM GROUPS mazut; Access without flag wouldn't set mazut from maztop alone
                pass
            for fld, keyn in (("GAZ", "gaz"), ("MAZUT", "mazut"), ("PROCH", "proch")):
                if keyn in main:
                    stored = D(st.get(fld))
                    got = D(main.get(keyn))
                    fuel_checks.append(
                        (nearly(stored, got), n1120, st.get("NAME"), fld, stored, got, form.get("formtxt")[:80], abs(stored - got))
                    )

    ch = e_target / csumnust * Decimal("1000") if csumnust > 0 else Decimal("0")
    hnps, hngt, hnpg = D(param["hnps"]), D(param["hngt"]), D(param["hnpg"])
    knps_exp = hnps / ch if ch > 0 else Decimal("0")
    kngt_exp = hngt / ch if ch > 0 else Decimal("0")
    knpg_exp = hnpg / ch if ch > 0 else Decimal("0")

    print("\n=== Coeff / aggregates ===")
    print(f"base NUST={bsumnust} E={bsume} EWTP={bsumetp}")
    print(f"calc NUST={csumnust} (skipped_no_ud={skipped_no_ud})")
    print(f"sumE stations={sum_e}  E_target={e_target}  abs_delta={abs(sum_e - e_target)}")
    print(f"ch={ch}")
    print(f"knps stored={D(param['knps'])} exp={knps_exp} match={nearly(D(param['knps']), knps_exp)}")
    print(f"kngt stored={D(param['kngt'])} exp={kngt_exp} match={nearly(D(param['kngt']), kngt_exp)}")
    print(f"knpg stored={D(param['knpg'])} exp={knpg_exp} match={nearly(D(param['knpg']), knpg_exp)}")

    def summarize(checks, label):
        ok = sum(1 for c in checks if c[0])
        bad = [c for c in checks if not c[0]]
        print(f"\n=== {label}: {ok}/{len(checks)} match ===")
        bad_sorted = sorted(bad, key=lambda x: x[-1], reverse=True)[:15]
        for c in bad_sorted:
            print(" FAIL", c)
        return ok, len(checks), bad

    e_ok, e_n, e_bad = summarize(energy_checks, "Energy EWTP/EOTP/EUST/EURT/TUST/B")
    h_ok, h_n, h_bad = summarize(h_checks, "H = E/NUST*1000")
    f_ok, f_n, f_bad = summarize(fuel_checks, "Fuel formtxt->GAZ/MAZUT/PROCH")

    ew = [c for c in energy_checks if c[3] == "EWTP"]
    summarize(ew, "EWTP only")

    print("\n=== Distribution convergence ===")
    print(f"abs(sumE - E_target) = {abs(sum_e - e_target)} (Access threshold 0.3)")

    report = DIR / "validation_report.txt"
    lines = [
        f"param={param['name']} year={cyear}",
        f"energy {e_ok}/{e_n}",
        f"H {h_ok}/{h_n}",
        f"fuel_main {f_ok}/{f_n}",
        f"sumE={sum_e} Etarget={e_target} delta={abs(sum_e - e_target)}",
        f"knps match={nearly(D(param['knps']), knps_exp)} kngt={nearly(D(param['kngt']), kngt_exp)} knpg={nearly(D(param['knpg']), knpg_exp)}",
        "",
        "TOP ENERGY FAILS:",
    ]
    for c in sorted(e_bad, key=lambda x: x[-1], reverse=True)[:30]:
        lines.append(str(c))
    lines.append("\nTOP H FAILS:")
    for c in sorted(h_bad, key=lambda x: x[-1], reverse=True)[:20]:
        lines.append(str(c))
    lines.append("\nTOP FUEL FAILS:")
    for c in sorted(f_bad, key=lambda x: x[-1], reverse=True)[:20]:
        lines.append(str(c))
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\nWrote", report)


if __name__ == "__main__":
    main()
