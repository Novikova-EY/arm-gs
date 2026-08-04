# -*- coding: utf-8 -*-
from pathlib import Path
import subprocess

folder = Path(r"z:\НИО-10\АРМ ГС\БД Топливо")
out = Path(r"c:\arm_gs\_otet_analysis\folder_listing.txt")
lines = []
for p in sorted(folder.rglob("*")):
    if p.is_file() and p.suffix.lower() in {".mdb", ".accdb", ".ldb"}:
        lines.append(f"{p.stat().st_size}\t{p}")
    elif p.is_dir() and p.parent == folder:
        lines.append(f"DIR\t{p.name}")
out.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
