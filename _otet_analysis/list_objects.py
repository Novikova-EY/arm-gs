# -*- coding: utf-8 -*-
import csv
from pathlib import Path

out = Path(r"c:\arm_gs\_otet_analysis")
rows = list(csv.DictReader((out / "tables_schema.csv").open(encoding="utf-8-sig")))
print("total", len(rows))
keys = [
    "перспект",
    "расчет",
    "расчёт",
    "прогноз",
    "параметр",
    "топлив",
    "calc",
    "персп",
    "удельн",
    "коэфф",
    "коэф",
    "btp",
    "otp",
    "ewtp",
    "ved",
]
print("=== MATCHED ===")
for r in sorted(rows, key=lambda x: (x["TABLE_TYPE"], x["TABLE_NAME"])):
    n = r["TABLE_NAME"].lower()
    if any(k in n for k in keys):
        print(f"{r['TABLE_TYPE']}\t{r['TABLE_NAME']}")

print("\n=== ALL TABLES ===")
for r in sorted(rows, key=lambda x: x["TABLE_NAME"]):
    if r["TABLE_TYPE"] == "TABLE":
        print(r["TABLE_NAME"])

print("\n=== ALL VIEWS ===")
for r in sorted(rows, key=lambda x: x["TABLE_NAME"]):
    if r["TABLE_TYPE"] == "VIEW":
        print(r["TABLE_NAME"])

for name in ("forms.txt", "modules.txt", "macros.txt", "reports.txt"):
    p = out / name
    if p.exists():
        print(f"\n=== {name} ===")
        print(p.read_text(encoding="utf-8"))
