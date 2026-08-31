# -*- coding: utf-8 -*-
"""Починить блок mock JSON gentypes в Word (убрать дубли абзацев)."""
from __future__ import annotations

import sys

from docx import Document
from docx.oxml.ns import qn

sys.stdout.reconfigure(encoding="utf-8")

DST = r"z:\НИО-10\АРМ ГС\JSON\Перечень_показателей_json_станции_агрегаты.docx"

MOCK_JSON = """{
    "dataset": "gentypes_info",
    "database_version": 46,
    "version": 46,
    "comment": "",
    "rows": [
        {
            "Год": 2032,
            "Зона": "1 синхронная зона",
            "Потребление, млрд. кВт•ч": 1000,
            "Максимальная мощность, МВт": 300000,
            "Максимум потребления мощности, МВт": 2000,
            "Экспорт мощности, МВт": 100,
            "Ограничения, МВт": 200,
            "Вводы мощности после прохождения максимума, МВт": 100,
            "Переток мощности в смежные энергосистемы (выдача (-), прием (+))": 100,
            "Потребление электрической энергии на производственные нужды ГАЭС в насосном режиме, МВт": 100,
            "Экспорт электрической энергии, млрд. кВт•ч": 200.32,
            "Прогнозируемые объемы капитальных вложений, млрд руб.": 100,
            "Число часов использования максимума потребления мощности (без учета потребления электрической энергии на производственные нужды ГАЭС в насосном режиме), ч/год": 100.0,
            "Дата и время прохождения максимума потребления мощности, дд.мм чч:мм": "05.06 13:20",
            "Среднесуточная ТНВ, °С": -10,
            "Потребление мощности на час прохождения максимума потребления мощности ЕЭС России, МВт": 100
        }
    ]
}"""


def main() -> None:
    doc = Document(DST)
    body = doc.element.body
    paras = list(doc.paragraphs)

    start_idx = None
    end_idx = None
    for i, p in enumerate(paras):
        if p.text.strip() == "gentypes_info":
            start_idx = i + 1
        if start_idx is not None and i >= start_idx:
            if p.text.strip().startswith("generation_objects"):
                end_idx = i
                break
    if start_idx is None or end_idx is None:
        raise SystemExit(f"block not found start={start_idx} end={end_idx}")

    # Keep first paragraph after heading for JSON; remove the rest until generation_objects
    first = paras[start_idx]
    first.text = MOCK_JSON
    for p in paras[start_idx + 1 : end_idx]:
        el = p._element
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)

    doc.save(DST)
    print("cleaned mock block", start_idx, end_idx)


if __name__ == "__main__":
    main()
