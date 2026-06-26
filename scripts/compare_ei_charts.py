# -*- coding: utf-8 -*-
"""Сравнение scatter-графиков электроёмкости: Excel vs страница."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EXCEL_PATH = ROOT / "app/СВОД 2024 год/02.06.26 Расчет электроемкости. Таблица 1.xlsx"
FD_RANGES = {
    "СЗФО": (51, 144),
    "ЦФО": (144, 237),
    "ЮФО": (237, 330),
    "ПФО": (330, 423),
    "СКФО": (423, 516),
    "УФО": (516, 609),
    "СФО": (609, 702),
    "ДФО": (702, 837),
}
YEARS = list(range(2010, 2043))


def year_col(year: int) -> int:
    return 4 + (year - 2010)


def _cell(ws, r: int, c: int):
    return ws.cell(r, c).value


def parse_excel_fd_charts(ws, start_row: int, end_row: int) -> list[dict]:
    charts: list[dict] = []
    current_ved: str | None = None
    r = start_row
    while r < end_row:
        a = _cell(ws, r, 1)
        b = str(_cell(ws, r, 2) or "").strip()
        if a and not _cell(ws, r, 2):
            current_ved = str(a).strip()
        if b.startswith("Накопленные Инвестиции") or b.startswith("Накопленные денежные"):
            accum = {y: _cell(ws, r, year_col(y)) for y in YEARS}
            intensity = None
            calc = None
            coef_a = None
            coef_x = None
            ved_label = current_ved
            for r3 in range(max(start_row, r - 10), r):
                b3 = str(_cell(ws, r3, 2) or "").strip()
                if b3 == "А=":
                    coef_a = _cell(ws, r3, 3)
                elif b3 == "Х=":
                    coef_x = _cell(ws, r3, 3)
                a3 = _cell(ws, r3, 1)
                if a3 and not _cell(ws, r3, 2):
                    ved_label = str(a3).strip()
            r2 = r + 1
            while r2 < min(r + 6, end_row):
                b2 = str(_cell(ws, r2, 2) or "").strip()
                if b2.startswith("Электроемкость") and "РАСЧЕТ" not in b2.upper() and intensity is None:
                    intensity = {y: _cell(ws, r2, year_col(y)) for y in YEARS}
                elif "РАСЧЕТ" in b2.upper():
                    calc = {y: _cell(ws, r2, year_col(y)) for y in YEARS}
                    break
                elif b2.startswith("Накопленные"):
                    break
                r2 += 1
            if intensity:
                charts.append(
                    {
                        "ved": ved_label,
                        "coef_a": coef_a,
                        "coef_x": coef_x,
                        "accum": accum,
                        "intensity": intensity,
                        "calc": calc,
                        "row": r,
                    }
                )
            r = r2 if calc else r + 1
            continue
        r += 1
    return charts


def _norm_fd_name(name: str) -> str:
    s = (name or "").strip().upper()
    for ch in ("ФЕДЕРАЛЬНЫЙ ОКРУГ", "ФО", ".", ","):
        s = s.replace(ch, "")
    s = " ".join(s.split())
    return s


def _match_fd_name(page_name: str, excel_keys: list[str]) -> str | None:
    pn = _norm_fd_name(page_name)
    for key in excel_keys:
        if _norm_fd_name(key) == pn or key.upper() in pn or pn in key.upper():
            return key
    # short codes
    mapping = {
        "СЕВЕРОЗАПАД": "СЗФО",
        "ЦЕНТРАЛЬН": "ЦФО",
        "ЮЖН": "ЮФО",
        "ПРИВОЛЖ": "ПФО",
        "СЕВЕРОКАВКАЗ": "СКФО",
        "УРАЛ": "УФО",
        "СИБИР": "СФО",
        "ДАЛЬН": "ДФО",
    }
    for frag, code in mapping.items():
        if frag in pn:
            return code
    return None


def _f(v, rd=4):
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f):
            return None
        return round(f, rd)
    except (TypeError, ValueError):
        return None


def _diff(a, b, tol=0.05):
    fa, fb = _f(a), _f(b)
    if fa is None and fb is None:
        return None
    if fa is None or fb is None:
        return float("inf")
    return abs(fa - fb)


def get_page_charts():
    from run import app
    from app.electrical_intensity.services.electrical_intensity_page_services import (
        parse_electrical_intensity_page_kwargs,
    )
    from app.electrical_intensity.services.electrical_intensity_services import (
        build_electrical_intensity_page_context,
    )

    url = "/electrical_intensity_fo/?rounding_digits=1&start_year=2010&end_year=2042"
    with app.app_context():
        with app.test_request_context(url):
            from flask import g, session

            session["current_db_version"] = 20
            g.current_db_version = 20
            kw = parse_electrical_intensity_page_kwargs(rounding_digits=1)
            for k in (
                "data_start_year",
                "data_end_year",
                "lt_ei_initial_visible_years",
                "lt_ei_year_seg_state",
            ):
                kw.pop(k, None)
            ctx = build_electrical_intensity_page_context(**kw)
    result = {}
    for block in ctx.get("territory_blocks") or []:
        if block.get("territory_kind") != "fd":
            continue
        name = block.get("abbr") or block.get("label") or ""
        sections = []
        for s in block.get("ved_sections") or []:
            sc = s.get("scatter_chart")
            if not sc:
                continue
            sections.append(
                {
                    "ved_name": s.get("ved_name"),
                    "ved_id": s.get("ved_id"),
                    "coef_a": s.get("coefficient_a_manual") or s.get("coefficient_a"),
                    "coef_a_computed": s.get("coefficient_a_computed"),
                    "coef_x": s.get("coefficient_x"),
                    "chart": sc,
                }
            )
        summary = block.get("fd_summary") or {}
        summary_chart = summary.get("scatter_chart")
        if summary_chart:
            sections.insert(
                0,
                {
                    "ved_name": "Свод ФО (ВРП/итого)",
                    "ved_id": "summary",
                    "coef_a": summary.get("coefficient_a_manual")
                    or summary.get("coefficient_a"),
                    "coef_a_computed": summary.get("coefficient_a_computed"),
                    "coef_x": summary.get("coefficient_x"),
                    "chart": summary_chart,
                },
            )
        result[name] = sections
    return result, ctx.get("ei_current_year")


def compare():
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb.active
    excel_by_fd = {
        fd: parse_excel_fd_charts(ws, lo, hi) for fd, (lo, hi) in FD_RANGES.items()
    }
    page_by_fd, current_year = get_page_charts()

    print(f"Текущий год на странице: {current_year}")
    print("=" * 80)

    total_mismatches = 0
    total_compared = 0

    for page_fd_name, page_sections in sorted(page_by_fd.items()):
        excel_fd = _match_fd_name(page_fd_name, list(FD_RANGES))
        if not excel_fd:
            print(f"\n[!] Не найден ФО в Excel для: {page_fd_name}")
            continue
        excel_charts = excel_by_fd.get(excel_fd, [])
        print(f"\n### {page_fd_name} ({excel_fd}) — графиков: страница {len(page_sections)}, Excel {len(excel_charts)}")

        for pi, ps in enumerate(page_sections):
            ec = excel_charts[pi] if pi < len(excel_charts) else None
            ved = ps["ved_name"]
            sc = ps["chart"]
            print(f"\n  [{pi+1}] {ved} (ved_id={ps['ved_id']})")
            if ec:
                print(
                    f"      Excel VED: {ec['ved']} | A={_f(ec['coef_a'],2)} X={_f(ec['coef_x'],4)}"
                )
                print(
                    f"      Page  A={_f(ps['coef_a'],2)} Acalc={_f(ps['coef_a_computed'],2)} X={_f(ps['coef_x'],4)}"
                )
                print(
                    f"      Chart A={_f(sc.get('initial_coef_a'),2)} X={_f(sc.get('coef_x'),4)}"
                )
                da = _diff(ec["coef_x"], ps["coef_x"])
                if da and da > 0.01:
                    print(f"      ** расхождение X: Excel vs page = {da:.4f}")
                    total_mismatches += 1
            else:
                print("      [!] Нет соответствующего блока в Excel по индексу")
                total_mismatches += 1
                continue

            for year in YEARS:
                if year > (current_year or 2024) and year <= 2024:
                    pass
                fact = next((p for p in sc.get("fact", []) if p["year"] == year), None)
                calc = next((p for p in sc.get("calc", []) if p["year"] == year), None)
                ex_x = ec["accum"].get(year)
                ex_y = ec["intensity"].get(year)
                ex_calc = (ec["calc"] or {}).get(year) if ec.get("calc") else None

                if ex_x is None and ex_y is None:
                    continue
                total_compared += 1

                mism = []
                if fact:
                    dx = _diff(fact["x"], ex_x, tol=1.0)
                    dy = _diff(fact["y"], ex_y, tol=0.1)
                    if dx and dx > 1.0:
                        mism.append(f"x_fact diff={dx:.2f} (page={_f(fact['x'])}, excel={_f(ex_x)})")
                    if dy and dy > 0.1:
                        mism.append(f"y_fact diff={dy:.3f} (page={_f(fact['y'])}, excel={_f(ex_y)})")
                elif ex_y is not None and (current_year is None or year <= current_year):
                    mism.append(f"нет fact на странице, в Excel y={_f(ex_y)}")

                if calc and ex_calc is not None:
                    dy_calc = _diff(calc["y"], ex_calc, tol=0.1)
                    if dy_calc and dy_calc > 0.1:
                        mism.append(
                            f"y_calc diff={dy_calc:.3f} (page={_f(calc['y'])}, excel={_f(ex_calc)})"
                        )

                if mism and year in (2010, 2015, 2020, 2024) or (mism and year <= (current_year or 2024)):
                    if mism:
                        print(f"      {year}: " + "; ".join(mism))
                        total_mismatches += len(mism)

    print("\n" + "=" * 80)
    print(f"Итого сравнений точек: {total_compared}, расхождений: {total_mismatches}")


if __name__ == "__main__":
    compare()
