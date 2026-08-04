# -*- coding: utf-8 -*-
"""Search exported Access objects for prospective fuel calculation logic."""
from pathlib import Path
import re

root = Path(r"c:\arm_gs\_otet_analysis")
vba = root / "vba"
queries = root / "queries"

keywords = [
    "перспект",
    "расчет",
    "расчёт",
    "удельн",
    "типов",
    "вариант",
    "прогноз",
    "btp",
    "eotp",
    "ewtp",
    "коэфф",
    "формул",
    "Calc",
    "расч",
]

# Fix object listing with proper encoding
import csv
rows = list(csv.DictReader((root / "tables_schema.csv").open(encoding="utf-8-sig")))
(root / "tables_utf8.txt").write_text(
    "\n".join(f"{r['TABLE_TYPE']}\t{r['TABLE_NAME']}" for r in sorted(rows, key=lambda x: (x["TABLE_TYPE"], x["TABLE_NAME"]))),
    encoding="utf-8",
)

print("=== TABLES/VIEWS matching keywords ===")
for r in sorted(rows, key=lambda x: (x["TABLE_TYPE"], x["TABLE_NAME"])):
    n = r["TABLE_NAME"].lower()
    if any(k.lower() in n for k in keywords):
        print(f"{r['TABLE_TYPE']}\t{r['TABLE_NAME']}")

print("\n=== VBA/FORM hits ===")
hits = []
for p in sorted(vba.glob("*.txt")):
    try:
        text = p.read_text(encoding="utf-16")
    except UnicodeError:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeError:
            text = p.read_text(encoding="cp1251", errors="replace")
    # Access SaveAsText is often UTF-16 LE
    low = text.lower()
    matched = [k for k in keywords if k.lower() in low]
    if matched:
        # extract CodeBehindForm / module code sections briefly
        code_lines = []
        for i, line in enumerate(text.splitlines()):
            ll = line.lower()
            if any(k.lower() in ll for k in keywords) or any(
                x in ll for x in ("sub ", "function ", "private sub", "public sub", "call ", "doCmd".lower())
            ):
                if any(k.lower() in ll for k in keywords) or "sub " in ll or "function " in ll:
                    code_lines.append(f"{i+1}:{line}")
        hits.append((p.name, matched, code_lines[:80], len(text)))
        print(f"\nFILE {p.name} matches={matched} size={len(text)}")
        for cl in code_lines[:40]:
            print(" ", cl)

print("\n=== QUERY name hits ===")
if queries.exists():
    for p in sorted(queries.glob("*.sql")):
        name = p.stem
        nl = name.lower()
        if any(k.lower() in nl for k in keywords):
            sql = p.read_text(encoding="utf-8", errors="replace")
            print(f"\nQUERY: {name}")
            print(sql[:800])

# Also dump procedure names from procedures.csv
print("\n=== PROCEDURE name hits ===")
procs = list(csv.DictReader((root / "procedures.csv").open(encoding="utf-8-sig")))
for pr in procs:
    n = (pr.get("PROCEDURE_NAME") or "")
    if n.startswith("~"):
        continue
    nl = n.lower()
    if any(k.lower() in nl for k in keywords):
        print(n)
        defn = pr.get("PROCEDURE_DEFINITION") or ""
        print(defn[:500])
        print("---")
