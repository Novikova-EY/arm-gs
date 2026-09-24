# -*- coding: utf-8 -*-
"""Inspect Excel mockup sheets, dropdowns and fuel-name colors."""
from __future__ import annotations

import json
from pathlib import Path

import win32com.client as win32

SRC = Path(r"z:\НИО-10\АРМ ГС\Шаблоны для АРМ ГС\9. Экология\Макет\Расчетный модуль")
files = list(SRC.glob("*.xls"))
print("FILES:")
for f in files:
    print(" ", f.name)

xls = next(p for p in files if "действ" in p.name.lower() or "натур" in p.name.lower() or p.suffix.lower() == ".xls")
print("USING", xls)

excel = win32.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
wb = excel.Workbooks.Open(str(xls), ReadOnly=True)
try:
    print("SHEETS:")
    for i, sh in enumerate(wb.Worksheets, 1):
        print(f"  {i}. {sh.Name}")

    target = None
    for sh in wb.Worksheets:
        name = str(sh.Name)
        if "справоч" in name.lower() or "хар" in name.lower():
            print("CANDIDATE", name)
            target = sh
            if "справоч" in name.lower():
                break
    if target is None:
        target = wb.Worksheets(1)
    print("TARGET", target.Name)

    used = target.UsedRange
    nrows = used.Rows.Count
    ncols = used.Columns.Count
    print("USED", nrows, ncols, "start", used.Row, used.Column)

    headers = []
    for r in range(1, min(6, nrows + 1)):
        row = []
        for c in range(1, min(ncols, 25) + 1):
            val = target.Cells(r, c).Text
            row.append(val)
        headers.append(row)
        print("ROW", r, row)

    # Data validation on first 80 rows, first 20 cols
    validations = []
    colors = []
    for r in range(1, min(nrows, 90) + 1):
        cell_a = target.Cells(r, 1)
        fill = cell_a.Interior.Color
        fontc = cell_a.Font.Color
        colors.append({
            "r": r,
            "text": cell_a.Text,
            "fill": fill,
            "font": fontc,
            "pattern": cell_a.Interior.Pattern,
        })
        for c in range(1, min(ncols, 22) + 1):
            cell = target.Cells(r, c)
            try:
                dv = cell.Validation
                formula1 = dv.Formula1
                typ = dv.Type
                if formula1:
                    validations.append({
                        "r": r,
                        "c": c,
                        "header": target.Cells(1, c).Text or target.Cells(2, c).Text,
                        "type": typ,
                        "formula": formula1,
                        "value": cell.Text,
                    })
            except Exception:
                pass

    print("VALIDATIONS unique:")
    seen = set()
    for v in validations:
        key = (v["c"], v["formula"], v["type"])
        if key in seen:
            continue
        seen.add(key)
        print(v)

    print("COLORS (non-default fills):")
    for item in colors:
        if item["fill"] not in (16777215, 0, 16777215.0) and item["text"]:
            print(item)

    # dump last columns headers
    print("ALL HEADERS COLS:")
    for c in range(1, ncols + 1):
        vals = [target.Cells(r, c).Text for r in range(1, min(5, nrows) + 1)]
        print(c, vals)
finally:
    wb.Close(False)
    excel.Quit()
