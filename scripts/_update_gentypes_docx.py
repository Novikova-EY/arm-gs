# -*- coding: utf-8 -*-
"""Обновить gentypes в Перечень_показателей_json_станции_агрегаты.docx."""
from __future__ import annotations

import sys

from docx import Document

sys.stdout.reconfigure(encoding="utf-8")

DST = r"z:\НИО-10\АРМ ГС\JSON\Перечень_показателей_json_станции_агрегаты.docx"

# (показатель, комментарий, источник в БД / страница)
GENTYPES_ROWS: list[tuple[str, str, str]] = [
    (
        "Год",
        "Годы: от (текущий − 5) включительно до конца расчётного периода СиПР / Генеральной схемы "
        "(как на /refdata/: текущий год «оценка», границы планирования версии).",
        "gs_sys_years.number\n"
        "YearFeature «текущий (оценка)» + YearService (расчётный период СиПР/ГС)",
    ),
    (
        "Зона",
        "ЕЭС России, все синхронные зоны (СЗ) и все ОЭС текущей версии. "
        "Не включаются «не указано» и «Новые территории».",
        "Листы как на /energy_balance/power_balance/\n"
        "(ЕЭС / СЗ / ОЭС из справочников энергосистем версии)",
    ),
    (
        "Потребление, млрд. кВт•ч",
        "Ключ как в mock. В АРМ/БД значение в млн кВт·ч (единицы в имени ключа не пересчитываем).",
        "Страница /energy_balance/ee_balance/\n"
        "нагрузка потребления по зоне×году",
    ),
    (
        "Максимальная мощность, МВт",
        "В mock — «максимальная»; по смыслу АРМ — установленная мощность электростанций зоны "
        "(как строка на балансе мощности). Для ЕЭС/1 СЗ — сумма по составу ЕЭС (с правилами листа).",
        "Страница /energy_balance/power_balance/\n"
        "установленная мощность (вводы по типам генерации)",
    ),
    (
        "Максимум потребления мощности, МВт",
        "Максимум потребления мощности зоны на балансе мощности.",
        "Страница /energy_balance/power_balance/\n"
        "gs_pd_*_demand_params.max_power_mw (через loaders баланса мощности)",
    ),
    (
        "Экспорт мощности, МВт",
        "Экспорт мощности по зоне×году.",
        "Страница /energy_balance/power_balance/\n"
        "экспорт мощности зоны",
    ),
    (
        "Ограничения, МВт",
        "Ограничения установленной мощности.",
        "Страница /energy_balance/power_balance/\n"
        "constraints установленной мощности",
    ),
    (
        "Вводы мощности после прохождения максимума, МВт",
        "Вводы после прохождения максимума (Q4 / commissioning_after_max).",
        "Страница /energy_balance/power_balance/\n"
        "commissioning_after_max",
    ),
    (
        "Переток мощности в смежные энергосистемы (выдача (-), прием (+))",
        "Сальдо пользовательских перетоков: приём (+), выдача (−).",
        "Страница /energy_balance/power_balance/\n"
        "пользовательские перетоки (custom flows)",
    ),
    (
        "Потребление электрической энергии на производственные нужды ГАЭС "
        "в насосном режиме, МВт",
        "Ключ mock — МВт; в БД charge_consumption в млн кВт·ч. Сумма по станциям территории зоны.",
        "Страница /energy_balance/ee_balance/ (смысл показателя)\n"
        "gs_gen_station_gaes_charge_consumptions.charge_consumption",
    ),
    (
        "Экспорт электрической энергии, млрд. кВт•ч",
        "Ключ как в mock. В АРМ/БД — млн кВт·ч.",
        "Страница /energy_balance/ee_balance/\n"
        "экспорт ЭЭ зоны",
    ),
    (
        "Прогнозируемые объемы капитальных вложений, млрд руб.",
        "В АРМ Генерации нет источника → всегда 0 (модуль Экономика).",
        "нет в АРМ ГС (заглушка 0)",
    ),
    (
        "Число часов использования максимума потребления мощности "
        "(без учета потребления электрической энергии на производственные нужды "
        "ГАЭС в насосном режиме), ч/год",
        "Как на сводке нагрузок: (потребление − ГАЭС) / максимум × 1000. "
        "Если максимум = 0 → 0.",
        "Страница /power_demand/summary/oes/\n"
        "расчёт ЧЧИУМ по потреблению, ГАЭС и максимуму",
    ),
    (
        "Дата и время прохождения максимума потребления мощности, дд.мм чч:мм",
        "Формат «дд.мм чч:мм». Если даты нет → 0.",
        "Страница /power_demand/summary/oes/\n"
        "gs_pd_*_demand_params.peak_datetime",
    ),
    (
        "Среднесуточная ТНВ, °С",
        "Из параметров нагрузки зоны (те же поля, что на сводке ОЭС/СЗ/ЕЭС). "
        "Страница /power_demand/ozp_maxima/ в АРМ содержит только максимум ОЗП — "
        "в mock-ключе gentypes этого показателя нет.",
        "Параметры нагрузки (сводка PD)\n"
        "gs_pd_*_demand_params.avg_daily_air_temp_c",
    ),
    (
        "Потребление мощности на час прохождения максимума потребления мощности "
        "ЕЭС России, МВт",
        "combined_on_ees из параметров нагрузки. Для зон без поля → 0.",
        "Параметры нагрузки (сводка PD)\n"
        "gs_pd_*_demand_params.combined_on_ees",
    ),
]

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


def set_cell_text(cell, text: str) -> None:
    paras = cell.paragraphs
    lines = text.split("\n") if text else [""]
    for p in paras[1:]:
        p._element.getparent().remove(p._element)
    first = cell.paragraphs[0]
    for r in list(first.runs):
        r._element.getparent().remove(r._element)
    first.text = lines[0]
    for line in lines[1:]:
        cell.add_paragraph(line)


def ensure_cols(table, n: int) -> None:
    while len(table.columns) < n:
        table.add_column(width=table.columns[-1].width)


def main() -> None:
    doc = Document(DST)

    # Update / replace gentypes mock JSON paragraph block: find "gentypes_info" heading
    # then following paragraphs until generation_objects
    replacing = False
    json_done = False
    for p in doc.paragraphs:
        t = p.text.strip()
        if t == "gentypes_info":
            replacing = True
            continue
        if replacing and not json_done:
            if t.startswith("generation_objects"):
                replacing = False
                continue
            if t.startswith("{") or t.startswith('"') or t.startswith("}") or t.startswith("[") or "Год" in t or "Зона" in t or t in ("{", "}", "[", "],", "}", "},") or t.startswith('"dataset"') or not t:
                # clear old mock lines; put full JSON into first JSON-ish para once
                if not json_done and (t.startswith("{") or '"dataset"' in t or t == "{"):
                    p.text = MOCK_JSON
                    json_done = True
                elif json_done:
                    p.text = ""
                continue

    table = doc.tables[0]
    # Ensure 3 columns: Показатель | Комментарий | Источник
    ensure_cols(table, 3)
    hdr = table.rows[0].cells
    set_cell_text(hdr[0], "Показатель из mock")
    set_cell_text(hdr[1], "Комментарий / проблема передачи")
    set_cell_text(hdr[2], "Источник в БД / страница АРМ")

    # Shrink or grow data rows
    needed = 1 + len(GENTYPES_ROWS)
    while len(table.rows) > needed:
        tr = table.rows[-1]._tr
        tr.getparent().remove(tr)
    while len(table.rows) < needed:
        table.add_row()

    for i, (name, comment, source) in enumerate(GENTYPES_ROWS, start=1):
        cells = table.rows[i].cells
        set_cell_text(cells[0], name)
        set_cell_text(cells[1], comment)
        set_cell_text(cells[2], source)

    doc.save(DST)
    print("saved", DST, "rows", len(table.rows))


if __name__ == "__main__":
    main()
