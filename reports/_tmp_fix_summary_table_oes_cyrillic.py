# -*- coding: utf-8 -*-
"""Restore Cyrillic in summary_table_*_body.html from sibling templates."""

from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path

PAGES = Path(r"c:\arm_gs\app\templates\energy_consumption\pages")
ROOT_EC = Path(r"c:\arm_gs\app\templates\energy_consumption")

# Prefer non-gaes sources so visible labels stay correct.
SOURCE_ORDER = [
    PAGES / "summary_oes_body.html",
    PAGES / "summary_fo_body.html",
    PAGES / "summary_ez_body.html",
    PAGES / "summary_table_hub_body.html",
    ROOT_EC / "energy_consumption_summary_body.html",
    PAGES / "summary_table_oes_gaes_charge_body.html",
    PAGES / "summary_table_fo_gaes_charge_body.html",
    PAGES / "summary_table_ez_gaes_charge_body.html",
]

TARGETS = {
    PAGES / "summary_table_oes_body.html": 0,  # prefer summary_oes
    PAGES / "summary_table_fo_body.html": 1,
    PAGES / "summary_table_ez_body.html": 2,
}

SOFT_DROP = re.compile(
    r"[\u0400-\u04FF\uFFFD«»“”\"––−…?\s]+|"
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"
)


def soft_key(s: str) -> str:
    return SOFT_DROP.sub("", s)


def fix_file(path: Path, preferred_source_index: int) -> None:
    bak = path.with_suffix(path.suffix + ".bak_cyr")
    if bak.exists():
        text_in = bak.read_text(encoding="utf-8")
    else:
        text_in = path.read_text(encoding="utf-8")
        bak.write_text(text_in, encoding="utf-8", newline="")

    bad_lines = text_in.splitlines(True)
    sources = []
    for p in SOURCE_ORDER:
        if p.exists():
            sources.append(p.read_text(encoding="utf-8").splitlines(True))

    idx: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for si, lines in enumerate(sources):
        for i, line in enumerate(lines):
            idx[soft_key(line)].append((si, i, line))

    fixed: list[str] = []
    ok = miss = clean = 0
    for bi, bl in enumerate(bad_lines):
        if "\ufffd" not in bl and "??" not in bl:
            fixed.append(bl)
            clean += 1
            continue
        cands = idx.get(soft_key(bl), [])
        if not cands:
            fixed.append(bl)
            miss += 1
            continue
        # Prefer preferred source, then lower source index, then nearer line.
        cands_sorted = sorted(
            cands,
            key=lambda t: (
                0 if t[0] == preferred_source_index else 1,
                t[0],
                abs(t[1] - bi),
            ),
        )
        fixed.append(cands_sorted[0][2])
        ok += 1

    out = "".join(fixed)
    # Hand-fix remaining comment / unique lines still containing FFFD.
    hand = {
        "{# \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd /summary_table/oes/ \ufffd \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd\ufffd \ufffd\ufffd\ufffd\ufffd\ufffd. #}\n":
        "{# Отдельный контур сводной /summary_table/oes/ – корень и ОЭС без детализации ниже уровня ОЭС. #}\n",
    }
    # Generic: replace any first-line comment for each target variant
    out_lines = out.splitlines(True)
    if out_lines and "\ufffd" in out_lines[0] and out_lines[0].startswith("{#"):
        name = path.name
        if "oes" in name:
            out_lines[0] = (
                "{# Отдельный контур сводной /summary_table/oes/ "
                "– корень и ОЭС без детализации ниже уровня ОЭС. #}\n"
            )
        elif "fo" in name:
            out_lines[0] = (
                "{# Отдельный контур сводной /summary_table/federal_districts/. #}\n"
            )
        elif "ez" in name:
            out_lines[0] = (
                "{# Отдельный контур сводной /summary_table/energy_zones/. #}\n"
            )
    out = "".join(out_lines)

    path.write_text(out, encoding="utf-8", newline="")
    left = out.count("\ufffd")
    print(
        f"{path.name}: replaced={ok} miss={miss} clean={clean} fffd_left={left} "
        f"Фильтры={'да' if 'Фильтры' in out else 'нет'} "
        f"Сохранить={'да' if 'Сохранить' in out else 'нет'}"
    )
    if left:
        # show a few remaining
        n = 0
        for i, line in enumerate(out.splitlines(), 1):
            if "\ufffd" in line:
                print(f"  still {i}: {line[:100]}")
                n += 1
                if n >= 8:
                    break


def main() -> None:
    for path, pref in TARGETS.items():
        if path.exists():
            fix_file(path, pref)


if __name__ == "__main__":
    main()
