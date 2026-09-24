# -*- coding: utf-8 -*-
"""
Описание программного комплекса АРМ «Генеральная схема» (как есть).

Документ по канонам описания программных продуктов:
общие сведения → состав и архитектура → среда → данные и доступ →
функциональные модули → информационное взаимодействие → ограничения.

Оформление – корпоративный шаблон НИР НИО-10 (стили 7.32).
"""

from __future__ import annotations

import shutil
import sys
import unicodedata
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"c:\arm_gs\reports")
sys.path.insert(0, str(ROOT))

import arm_product_description_content as txt  # noqa: E402
import arm_product_description_prose as prose  # noqa: E402
import arm_product_module_details as module_details  # noqa: E402
import arm_product_module_ui as module_ui  # noqa: E402
import arm_product_technical_spec as spec  # noqa: E402
import generate_stage1_report_nir as nir  # noqa: E402

Z_ARM = Path(r"Z:\НИО-10\АРМ ГС")
OUT_DIR = Z_ARM / "02. Отчеты НИР" / "2026 год"
OUT_NAME = "Описание_программного_комплекса_АРМ_Генеральная_схема.docx"


def _resolve_template() -> Path:
    candidates = [
        OUT_DIR / "Отчет_Этап 1_АРМ_ГС-2026.docx",
        OUT_DIR / "Отчет_Этап 1_АРМ_ГС-2026_редакция.docx",
        ROOT / "Отчет_Этап1_АРМ_ГС-2026_выполненные_работы.docx",
        Z_ARM / "Отчеты НИР" / "2026 год" / "Отчет_Этап 1_АРМ_ГС-2026.docx",
    ]
    for p in candidates:
        if p.exists() and not p.name.startswith("~$"):
            return p
    folder_2025 = Z_ARM / "02. Отчеты НИР" / "2025 год"
    if not folder_2025.exists():
        folder_2025 = Z_ARM / "Отчеты НИР" / "2025 год"
    if folder_2025.exists():
        found = sorted(
            p for p in folder_2025.glob("*.docx") if not p.name.startswith("~$")
        )
        if found:
            return found[0]
    raise FileNotFoundError("Не найден DOCX-шаблон со стилями НИР 7.32.")


TEMPLATE = _resolve_template()

OUT_PATHS = [
    OUT_DIR / OUT_NAME,
    ROOT / OUT_NAME,
]

PROJECT_NAME = (
    "Программный комплекс АРМ «Генеральная схема» "
    "(автоматизированное рабочее место подготовки материалов "
    "генеральной схемы размещения объектов электроэнергетики)"
)

DOC_TITLE = (
    "ОПИСАНИЕ ПРОГРАММНОГО КОМПЛЕКСА АРМ «ГЕНЕРАЛЬНАЯ СХЕМА» "
    "(СОСТАВ, ФУНКЦИИ И ТЕКУЩАЯ РЕАЛИЗАЦИЯ)"
)

KEYWORDS = (
    "АРМ ГЕНЕРАЛЬНАЯ СХЕМА, ОПИСАНИЕ ПРОГРАММНОГО ПРОДУКТА, "
    "МОДУЛИ, СПРАВОЧНИКИ, ГЕНЕРАЦИЯ, НАГРУЗКИ, СПРОС, "
    "БАЛАНСЫ ЭЛЕКТРОЭНЕРГИИ И МОЩНОСТИ, ТОПЛИВО, "
    "ЭЛЕКТРОЕМКОСТЬ, ЭКОНОМИКА, ВЕРСИОНИРОВАНИЕ ДАННЫХ, "
    "ВЕБ-ПРИЛОЖЕНИЕ, POSTGRESQL."
)

REFERAT_TEXT = txt.REFERAT_TEXT
INTRODUCTION = txt.INTRODUCTION
GENERAL = txt.GENERAL
USERS = txt.USERS
USERS_AFTER = txt.USERS_AFTER
ARCHITECTURE = txt.ARCHITECTURE
MODULES_LIST = txt.MODULES_LIST
ARCHITECTURE_AFTER = txt.ARCHITECTURE_AFTER
TECH_ENV = txt.TECH_ENV
DATA_ACCESS = txt.DATA_ACCESS
MODULE_INTRO = txt.MODULE_INTRO
MODULE_CHAPTERS = module_ui.inject_ui(
    module_details.inject_details(prose.inject_detailed(txt.MODULE_CHAPTERS))
)
INTERACTION = txt.INTERACTION
LIMITS = txt.LIMITS
LIMIT_ITEMS = txt.LIMIT_ITEMS
CONCLUSION = txt.CONCLUSION

SPEC_TABLE_COUNT = 13
TABLE_COUNT_ACTUAL = 0

EXTRA_ABBREVIATIONS = [
    ("API", "программный интерфейс приложения (Application Programming Interface)"),
    ("EARS", "структурированный синтаксис формулирования требований (Easy Approach to Requirements Syntax)"),
    ("FR", "функциональное требование (Functional Requirement)"),
    ("ГИС ТЭК", "государственная информационная система топливно-энергетического комплекса"),
    ("HTTP", "протокол передачи гипертекста (Hypertext Transfer Protocol)"),
    ("ISO/IEC/IEEE 29148", "международный стандарт процессов и содержания инженерии требований"),
    ("JSON", "текстовый формат обмена структурированными данными (JavaScript Object Notation)"),
    ("КОММОД", "конкурентный отбор мощности проектов модернизации генерирующих объектов"),
    ("КОМ НГО", "конкурентный отбор мощности новых генерирующих объектов"),
    ("НГО", "новый генерирующий объект"),
    ("НТ", "новые территории (обозначение варианта периметра расчета)"),
    ("NFR", "нефункциональное требование (Non-Functional Requirement)"),
    ("ПГ", "парниковые газы"),
    ("ПГУ", "парогазовая установка"),
    ("RFC 7807", "стандарт представления сведений об ошибках HTTP API"),
    ("RPO", "допустимая точка потери данных при восстановлении (Recovery Point Objective)"),
    ("RTO", "допустимое время восстановления сервиса (Recovery Time Objective)"),
    ("СЗ", "синхронная зона"),
    ("ТИТЭС", "территориально изолированная технологическая электроэнергетическая система"),
    ("ЦЗ", "ценовая зона"),
    ("ЕГО", "единица генерирующего оборудования"),
    ("ЗВ", "загрязняющие вещества"),
]

ALL_ABBREVIATIONS = sorted(
    {abbr: meaning for abbr, meaning in [*nir.ABBREVIATIONS, *EXTRA_ABBREVIATIONS]}.items(),
    key=lambda item: item[0],
)

TABLE_CAPTIONS = [
    "Перечень сокращений и обозначений",
    "Глоссарий терминов",
    "Жизненный цикл версии базы данных",
    "Матрица ролей и прав доступа",
    "Заинтересованные стороны программного комплекса",
    "Основные классы сущностей концептуальной модели данных",
    "Функциональные требования к текущему поведению АРМ",
    "Нефункциональные требования и целевые показатели",
    "Технические ограничения текущего решения",
    "Внешние и эксплуатационные зависимости",
    "Допущения спецификации",
    "Минимальный набор тестовых сценариев",
    "Матрица трассируемости требований и тестовых сценариев",
]


def update_title_page(doc: Document) -> None:
    table = doc.tables[0]
    row = table.rows[5]
    seen: set[int] = set()
    target = None
    for cell in row.cells:
        cid = id(cell._tc)
        if cid in seen:
            continue
        seen.add(cid)
        if "Антонов" in cell.text or "____" in cell.text:
            target = cell
    if target is None:
        uniq = []
        seen.clear()
        for cell in row.cells:
            cid = id(cell._tc)
            if cid in seen:
                continue
            seen.add(cid)
            uniq.append(cell)
        target = uniq[-1] if uniq else None
    if target is not None:
        nir.set_cell_text(
            target,
            "__________________ П.С. Антонов\n«___» _____________ 2026 г.",
        )

    nir.replace_unique_row_text(table, 6, "ОПИСАНИЕ ПРОГРАММНОГО ПРОДУКТА")
    nir.replace_unique_row_text(table, 7, PROJECT_NAME)
    nir.replace_unique_row_text(table, 8, DOC_TITLE)
    nir.replace_unique_row_text(
        table,
        9,
        "(описание программного комплекса)\n\n\n"
        "Дирекция по развитию энергосистем\n"
        "Отдел генерации и прогнозирования спроса\n"
        "на электрическую энергию и мощность (НИО-10)\n"
        "2026\n",
    )
    for para in doc.paragraphs:
        t = para.text.replace("\xa0", " ")
        if t.startswith("Санкт-Петербург"):
            nir.set_paragraph_text(para, "Санкт-Петербург 2026")
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if t.startswith("©"):
            nir.set_paragraph_text(para, "© АО «НТЦ ЕЭС», 2026")
            para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Унифицировать обозначение Н.А. Беляева на титуле и в списке исполнителей.
    if len(doc.tables) > 1 and len(doc.tables[1].rows) >= 2:
        executor_table = doc.tables[1]
        nir.set_cell_text(
            executor_table.rows[0].cells[0],
            "Руководитель рабочей группы,\n"
            "начальник отдела генерации и прогнозирования спроса "
            "на электрическую энергию и мощность (НИО-10), "
            "канд. техн. наук",
        )
        nir.set_cell_text(executor_table.rows[0].cells[2], "Н.А. Беляев")
        nir.set_cell_text(
            executor_table.rows[1].cells[2],
            "(общее научное руководство, введение, заключение)",
        )
        for row_index in (4, 7, 10, 13):
            if row_index < len(executor_table.rows):
                nir.set_cell_text(
                    executor_table.rows[row_index].cells[2],
                    "(материалы описания программного комплекса)",
                )


def update_referat(doc: Document, n_figures: int, n_pages: int | None = None) -> None:
    found = False
    updated = 0
    pages_token = str(n_pages) if n_pages else "__"
    for para in doc.paragraphs:
        if para.text.strip() == "РЕФЕРАТ":
            found = True
            continue
        if not found:
            continue
        if para.style and para.style.name == nir.STYLE_BODY and para.text.strip():
            if updated == 0:
                nir.set_paragraph_text(
                    para,
                    f"Документ {pages_token} с., 1 кн., {SPEC_TABLE_COUNT} табл., "
                    f"{n_figures} рис., "
                    f"0 прил.",
                )
            elif updated == 1:
                nir.set_paragraph_text(para, KEYWORDS)
            elif updated == 2:
                nir.set_paragraph_text(para, REFERAT_TEXT)
            updated += 1
            if updated >= 3:
                break


def _add_h2_block(doc: Document, title: str, paras: list[str]) -> None:
    nir.add_styled(doc, title, nir.STYLE_H2)
    nir.add_body_paras(doc, paras)


def _add_table(
    doc: Document,
    headers: list[str],
    rows: list[tuple[str, ...]],
    *,
    caption: str,
    font_size: float = 9.0,
) -> None:
    """Добавить компактную таблицу спецификации в стиле документа."""
    global TABLE_COUNT_ACTUAL
    TABLE_COUNT_ACTUAL += 1
    cap = nir.add_styled(
        doc,
        f"Таблица {TABLE_COUNT_ACTUAL} — {caption}",
        nir.STYLE_BODY,
    )
    for run in cap.runs:
        run.bold = True
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for col, text in enumerate(headers):
        cell = table.rows[0].cells[col]
        nir.set_cell_text(cell, text)
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for values in rows:
        cells = table.add_row().cells
        for col, value in enumerate(values):
            nir.set_cell_text(cells[col], str(value))
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(0)
                for run in para.runs:
                    run.font.name = "Times New Roman"
                    run._element.get_or_add_rPr().rFonts.set(
                        qn("w:eastAsia"), "Times New Roman"
                    )
                    run.font.size = Pt(font_size)
    doc.add_paragraph()


def _disable_automatic_heading_numbering(doc: Document) -> None:
    """Отключить нумерацию шаблона; номера разделов задаются явно."""
    style = doc.styles[nir.STYLE_H2]
    p_pr = style._element.get_or_add_pPr()
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is not None:
        p_pr.remove(num_pr)


def _normalize_unicode_and_fonts(doc: Document) -> None:
    """Нормализовать Unicode и исключить подстановку шрифтов/символов."""
    corrections = {
        "MODULb": "МОДУЛЬ",
        "MODYJIb": "МОДУЛЬ",
        "CIPROC": "СПРОС",
        "TOPLIBO": "ТОПЛИВО",
        "Гранцы программыг о продукта": "Границы программного продукта",
        "етогр": "errors",
        "кафлей": "файл",
        "строительные формы": "соответствующие формы",
        "электромкость": "электроемкость",
    }

    def normalize_para(para) -> None:
        raw = para.text
        fixed = unicodedata.normalize("NFC", raw)
        fixed = "".join(ch for ch in fixed if not 0x7F <= ord(ch) <= 0x9F)
        for bad, good in corrections.items():
            fixed = fixed.replace(bad, good)
        if fixed != raw:
            nir.set_paragraph_text(para, fixed)
        for run in para.runs:
            r_pr = run._element.get_or_add_rPr()
            for sym in list(run._element.findall(qn("w:sym"))):
                run._element.remove(sym)
            run.font.name = "Times New Roman"
            fonts = r_pr.get_or_add_rFonts()
            for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
                fonts.set(qn(f"w:{attr}"), "Times New Roman")

    for style_name in (
        nir.STYLE_BODY,
        nir.STYLE_STRUCT_HIDDEN,
        nir.STYLE_STRUCT_TOC,
        nir.STYLE_H1,
        nir.STYLE_H2,
        nir.STYLE_BULLET,
    ):
        style = doc.styles[style_name]
        style.font.name = "Times New Roman"
        style_r_pr = style._element.get_or_add_rPr()
        style_fonts = style_r_pr.get_or_add_rFonts()
        for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
            style_fonts.set(qn(f"w:{attr}"), "Times New Roman")

    for para in doc.paragraphs:
        normalize_para(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    normalize_para(para)


def _add_mermaid_source(doc: Document, lines: list[str]) -> None:
    """Добавить проверяемое текстовое представление концептуальной ERD."""
    for line in lines:
        para = doc.add_paragraph()
        run = para.add_run(line)
        run.font.name = "Courier New"
        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Courier New")
        run.font.size = Pt(9)


def _ensure_architecture_diagram() -> None:
    """Сформировать архитектурную схему в PNG с кириллическими подписями."""
    path = nir.SHOTS / "00_architecture.png"
    width, height = 2400, 1450
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path(r"C:\Windows\Fonts\arial.ttf")
    bold_path = Path(r"C:\Windows\Fonts\arialbd.ttf")
    font = ImageFont.truetype(str(font_path), 40)
    small = ImageFont.truetype(str(font_path), 33)
    bold = ImageFont.truetype(str(bold_path), 43)
    title = ImageFont.truetype(str(bold_path), 52)

    def box(
        xy: tuple[int, int, int, int],
        heading: str,
        lines: list[str],
        fill: str,
    ) -> None:
        draw.rounded_rectangle(xy, radius=24, fill=fill, outline="#284b63", width=5)
        x1, y1, x2, _y2 = xy
        draw.text(((x1 + x2) / 2, y1 + 28), heading, font=bold, fill="#102a43", anchor="ma")
        y = y1 + 95
        for line in lines:
            draw.text(((x1 + x2) / 2, y), line, font=small, fill="#243b53", anchor="ma")
            y += 48

    def arrow(start: tuple[int, int], end: tuple[int, int], label: str = "") -> None:
        draw.line([start, end], fill="#486581", width=7)
        import math

        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        size = 24
        p1 = (
            end[0] - size * math.cos(angle - 0.55),
            end[1] - size * math.sin(angle - 0.55),
        )
        p2 = (
            end[0] - size * math.cos(angle + 0.55),
            end[1] - size * math.sin(angle + 0.55),
        )
        draw.polygon([end, p1, p2], fill="#486581")
        if label:
            draw.text(
                ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 - 18),
                label,
                font=font,
                fill="#334e68",
                anchor="ms",
            )

    draw.text(
        (width / 2, 45),
        "Архитектура программного комплекса АРМ «Генеральная схема»",
        font=title,
        fill="#102a43",
        anchor="ma",
    )
    box((820, 150, 1580, 330), "Клиентский уровень", ["Веб-браузер", "HTML / JavaScript"], "#e8f4fd")
    box(
        (590, 490, 1680, 770),
        "Сервер приложений Flask",
        [
            "аутентификация и роли • версия БД • маршрутизация",
            "предметные сервисы • расчетные процедуры",
            "импорт/экспорт Excel • журналирование",
        ],
        "#eaf7ee",
    )
    box(
        (130, 920, 930, 1240),
        "PostgreSQL",
        [
            "gs_auth • gs_logs • gs_sys • gs_gen",
            "gs_fue • gs_fue_em • gs_pd • gs_ec",
            "gs_bem • gs_ekp • gs_ei • gs_ter • gs_eco",
            "версионные данные и журналы",
        ],
        "#fff4e5",
    )
    box((1110, 930, 1660, 1200), "Redis / файловый режим", ["сессии", "кэш справочных выборок"], "#f6edff")
    box(
        (1740, 490, 2340, 770),
        "Интеграционный уровень",
        ["JSON API", "выгрузки Excel", "каталог наборов данных"],
        "#fff1f2",
    )
    box(
        (1740, 930, 2340, 1200),
        "Внешний контур",
        ["АРМ «Экономика»", "средства выходных документов"],
        "#f0f4f8",
    )
    arrow((1200, 330), (1200, 490), "HTTP")
    arrow((920, 770), (600, 920), "SQL / транзакции")
    arrow((1450, 770), (1385, 930), "сессии / кэш")
    arrow((1680, 630), (1740, 630))
    arrow((2060, 770), (2060, 930), "JSON / Excel")
    draw.text(
        (width / 2, 1360),
        "Все предметные операции выполняются в контексте выбранной версии базы данных",
        font=bold,
        fill="#102a43",
        anchor="ma",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def _add_figures(
    doc: Document,
    figs: nir.FigureCounter,
    fig_key: str,
) -> list[int]:
    nums: list[int] = []
    if not fig_key:
        return nums
    for stem, caption in nir.CHAPTER_FIGURES.get(fig_key, []):
        # «подсистема» → «модуль» в подписях
        cap = (
            caption.replace("подсистемы «", "модуля «")
            .replace("подсистема «", "модуль «")
            .replace("Подсистемы «", "Модуля «")
            .replace("Подсистема «", "Модуль «")
        )
        n = figs.add_figure(doc, stem, cap)
        if n:
            nums.append(n)
    return nums


def build() -> list[str]:
    global TABLE_COUNT_ACTUAL
    TABLE_COUNT_ACTUAL = 0
    work = ROOT / "_arm_product_desc_work.docx"
    shutil.copy2(TEMPLATE, work)
    doc = Document(str(work))
    figs = nir.FigureCounter()
    _disable_automatic_heading_numbering(doc)
    _ensure_architecture_diagram()

    update_title_page(doc)

    # оценка числа уникальных рисунков (без ecology)
    unique_stems = {
        stem
        for key, items in nir.CHAPTER_FIGURES.items()
        for stem, _ in items
    }
    update_referat(doc, n_figures=len(unique_stems) + 1)

    nir.delete_body_after(doc, keep_until_idx=39)
    nir.ensure_blank_after_template_headings(doc)

    # ----- Содержание -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "СОДЕРЖАНИЕ", nir.STYLE_STRUCT_HIDDEN)
    toc = [
        "Перечень таблиц",
        "Перечень сокращений и обозначений",
        "Глоссарий терминов",
        "Введение",
        "1 Общие сведения",
        "2 Состав и архитектура комплекса",
        "3 Среда функционирования",
        "4 Организация данных и разграничение доступа",
        "5 Описание функциональных модулей",
    ]
    for i, (_, title, _, _) in enumerate(MODULE_CHAPTERS, start=1):
        toc.append(f"5.{i} {title}")
    toc.extend(
        [
            "6 Информационное взаимодействие",
            "7 Ограничения текущей реализации",
            "8 Формализованная спецификация текущего поведения",
            "9 Рекомендации по развитию",
            "Предметный указатель",
            "Заключение",
        ]
    )
    for item in toc:
        nir.add_styled(doc, item, nir.STYLE_BODY)

    # ----- Перечень таблиц -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "ПЕРЕЧЕНЬ ТАБЛИЦ", nir.STYLE_STRUCT_TOC)
    for number, caption in enumerate(TABLE_CAPTIONS, start=1):
        nir.add_styled(doc, f"Таблица {number} — {caption}", nir.STYLE_BODY)

    # ----- Сокращения -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ", nir.STYLE_STRUCT_TOC)
    nir.add_styled(
        doc,
        "В настоящем описании применяют следующие сокращения и обозначения.",
        nir.STYLE_BODY,
    )
    _add_table(
        doc,
        ["Сокращение", "Расшифровка"],
        ALL_ABBREVIATIONS,
        caption="Перечень сокращений и обозначений",
        font_size=9.0,
    )

    # ----- Глоссарий -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "ГЛОССАРИЙ ТЕРМИНОВ", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(
        doc,
        [
            "Глоссарий фиксирует значение терминов в контексте настоящего "
            "документа и программного комплекса АРМ «Генеральная схема».",
        ],
    )
    _add_table(
        doc,
        ["Термин", "Определение"],
        spec.GLOSSARY,
        caption="Глоссарий терминов",
    )

    # ----- Введение -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "Введение", nir.STYLE_STRUCT_TOC)
    for paragraph in INTRODUCTION:
        if paragraph.startswith("• "):
            nir.add_styled(doc, paragraph[2:], nir.STYLE_BULLET)
        else:
            nir.add_styled(doc, paragraph, nir.STYLE_BODY)

    # ----- 1 Общие сведения -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "1 Общие сведения", nir.STYLE_STRUCT_TOC)
    for sec_title, paras in GENERAL.items():
        _add_h2_block(doc, sec_title, paras)
    nir.add_bullets(doc, USERS)
    nir.add_body_paras(doc, USERS_AFTER)

    # ----- 2 Архитектура -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "2 Состав и архитектура комплекса", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, ARCHITECTURE)
    nir.add_bullets(doc, MODULES_LIST)
    nir.add_body_paras(doc, ARCHITECTURE_AFTER)
    nir.add_styled(
        doc,
        "Обобщенная архитектурная схема комплекса представлена на рисунке ниже. "
        "На ней показаны клиентский, серверный, информационный и интеграционный "
        "уровни, а также основные потоки данных.",
        nir.STYLE_BODY,
    )
    architecture_figure = figs.add_figure(
        doc,
        "00_architecture",
        "Обобщенная архитектура программного комплекса АРМ «Генеральная схема»",
    )
    if architecture_figure:
        nir.add_styled(
            doc,
            f"Рисунок {architecture_figure} показывает, что веб-клиент "
            "взаимодействует с сервером Flask по HTTP; сервер обращается к "
            "PostgreSQL, использует Redis либо файловый режим для сессий и "
            "кэша и предоставляет JSON/Excel-интерфейсы внешнему контуру.",
            nir.STYLE_BODY,
        )
    nir.add_styled(
        doc,
        "Общий вид главной страницы комплекса с группировкой модулей "
        "представлен на рисунке ниже. Рисунок иллюстрирует логику "
        "предметной декомпозиции функций и служит исходной точкой "
        "навигации пользователя.",
        nir.STYLE_BODY,
    )
    n0 = figs.add_figure(
        doc,
        "01_home",
        "Главная страница программного комплекса АРМ «Генеральная схема»",
    )
    if n0:
        nir.add_styled(
            doc,
            f"На рисунке {n0} показана стартовая страница АРМ: блоки "
            "«Энергоресурсы и балансы», «Потребление», «Прогноз и территории» "
            "и «Нормативно-справочная информация». Группировка отражает "
            "взаимную связь модулей в составе единой информационной модели.",
            nir.STYLE_BODY,
        )

    # ----- 3 Среда -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "3 Среда функционирования", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, TECH_ENV)

    # ----- 4 Данные и доступ -----
    nir.add_page_break(doc)
    nir.add_styled(
        doc,
        "4 Организация данных и разграничение доступа",
        nir.STYLE_STRUCT_TOC,
    )
    nir.add_body_paras(doc, DATA_ACCESS)
    _add_h2_block(
        doc,
        "4.1 Жизненный цикл версии базы данных",
        [
            "Жизненный цикл версии объединяет административные и предметные "
            "операции от регистрации расчетного среза до сравнения, создания "
            "снимка, восстановления или удаления. Отдельные состояния "
            "«утверждена», «архивная» и «заблокирована» в фактически "
            "подтвержденном контуре не выделены.",
        ],
    )
    _add_table(
        doc,
        ["Стадия", "Фактическое поведение", "Ограничение / право"],
        spec.VERSION_LIFECYCLE,
        caption="Жизненный цикл версии базы данных",
    )
    _add_h2_block(
        doc,
        "4.2 Матрица ролей и прав доступа",
        [
            "Матрица отражает роли и варианты их написания, обнаруженные "
            "в текущей реализации. Права на конкретную операцию определяются "
            "защитой соответствующего маршрута; поэтому таблица не подменяет "
            "проверку декораторов и сервисов при изменении программного кода.",
        ],
    )
    _add_table(
        doc,
        ["Роль", "Область", "Просмотр", "Редактирование", "Особенности"],
        spec.ROLE_MATRIX,
        caption="Матрица ролей и прав доступа",
        font_size=8.0,
    )
    _add_h2_block(
        doc,
        "4.3 Конкурентное редактирование, резервное копирование и безопасность",
        spec.CONCURRENCY_AND_OPERATIONS_AS_IS,
    )

    # ----- 5 Модули -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "5 Описание функциональных модулей", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, MODULE_INTRO)

    for idx, (_key, title, sections, fig_key) in enumerate(MODULE_CHAPTERS, start=1):
        nir.add_page_break(doc)
        nir.add_styled(doc, f"5.{idx} {title}", nir.STYLE_STRUCT_TOC)
        for sec_idx, (sec_title, paras) in enumerate(sections.items(), start=1):
            _add_h2_block(doc, f"5.{idx}.{sec_idx} {sec_title}", paras)
            if sec_title == "Экранные формы":
                nums = _add_figures(doc, figs, fig_key)
                if nums:
                    ref = nir.figure_ref_sentence(
                        nums,
                        "Экранные формы модуля представлены",
                    )
                    if ref:
                        nir.add_styled(doc, ref, nir.STYLE_BODY)

    # ----- 6 Взаимодействие -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "6 Информационное взаимодействие", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, INTERACTION)
    _add_h2_block(
        doc,
        "6.1 Прямой обмен с контуром АРМ «Экономика»",
        spec.EXCHANGE_WITH_ECONOMICS_AS_IS,
    )

    # ----- 7 Ограничения -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "7 Ограничения текущей реализации", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, LIMITS)
    nir.add_bullets(doc, LIMIT_ITEMS)

    # ----- 8 Формализованная спецификация (ISO/IEC/IEEE 29148) -----
    nir.add_page_break(doc)
    nir.add_styled(
        doc,
        "8 Формализованная спецификация текущего поведения",
        nir.STYLE_STRUCT_TOC,
    )
    nir.add_body_paras(doc, spec.SPEC_INTRO)

    _add_h2_block(
        doc,
        "8.1 Границы программного продукта",
        [
            "В область формализованной спецификации включены следующие "
            "действующие компоненты и процессы:",
        ],
    )
    nir.add_bullets(doc, spec.SCOPE_IN)
    nir.add_body_paras(
        doc,
        [
            "За границами области спецификации оставлены следующие возможности. "
            "Для каждого исключения указана причина:",
        ],
    )
    nir.add_bullets(doc, spec.SCOPE_OUT)

    _add_h2_block(
        doc,
        "8.2 Заинтересованные стороны",
        [
            "Заинтересованные стороны определяют цели эксплуатации, правила "
            "сопровождения и критерии оценки текущего поведения комплекса.",
        ],
    )
    _add_table(
        doc,
        ["Код", "Сторона", "Интерес / ответственность"],
        spec.STAKEHOLDERS,
        caption="Заинтересованные стороны программного комплекса",
    )

    _add_h2_block(
        doc,
        "8.3 Критический сквозной пользовательский сценарий",
        [
            "В качестве основного сценария, объединяющего предметные и "
            "инфраструктурные функции, принят полный цикл подготовки "
            "согласованного версионного набора данных.",
        ],
    )
    nir.add_body_paras(doc, spec.PRIMARY_WORKFLOW)

    _add_h2_block(
        doc,
        "8.4 Концептуальная модель данных",
        [
            "Концептуальная модель выделяет классы сущностей, значимые для "
            "сквозного поведения продукта. Физическая модель конкретного "
            "модуля детализируется таблицами соответствующей схемы PostgreSQL.",
        ],
    )
    _add_table(
        doc,
        [
            "Сущность",
            "Ключевые атрибуты",
            "Назначение / связь",
            "Классификация",
            "Хранение",
        ],
        spec.DATA_ENTITIES,
        caption="Основные классы сущностей концептуальной модели данных",
        font_size=8.0,
    )
    nir.add_styled(
        doc,
        "Ниже приведена концептуальная ERD в нотации Mermaid. Она фиксирует "
        "основные отношения и кардинальности без подмены физической схемы БД.",
        nir.STYLE_BODY,
    )
    _add_mermaid_source(doc, spec.MERMAID_ERD)

    _add_h2_block(
        doc,
        "8.5 Функциональные требования к текущему поведению",
        [
            "Функциональные требования сформулированы в синтаксисе EARS. "
            "Каждое требование атомарно идентифицируется, имеет наблюдаемый "
            "критерий приемки, владельца и отметку состояния реализации.",
        ],
    )
    _add_table(
        doc,
        ["ID", "Формулировка требования", "Критерий приемки", "Владелец", "Статус"],
        spec.FUNCTIONAL_REQUIREMENTS,
        caption="Функциональные требования к текущему поведению АРМ",
        font_size=8.0,
    )

    _add_h2_block(
        doc,
        "8.6 Нефункциональные требования",
        [
            "Нефункциональные требования определяют проверяемые ограничения "
            "качества. Метка hard означает блокирующее условие приемки; soft — "
            "целевой уровень, отклонение от которого требует анализа и решения "
            "владельца продукта.",
        ],
    )
    _add_table(
        doc,
        [
            "ID",
            "Формулировка требования",
            "Критерий приемки",
            "Владелец",
            "Тип",
            "Статус",
        ],
        spec.NON_FUNCTIONAL_REQUIREMENTS,
        caption="Нефункциональные требования и целевые показатели",
        font_size=8.0,
    )

    _add_h2_block(
        doc,
        "8.7 Фактическая обработка ошибок",
        spec.ERROR_HANDLING_AS_IS,
    )
    _add_h2_block(
        doc,
        "8.8 Фактический программный интерфейс",
        spec.API_AS_IS,
    )

    _add_h2_block(
        doc,
        "8.9 Ограничения, зависимости и допущения",
        [
            "Ограничения фиксируют неизменяемые характеристики текущего "
            "решения; зависимости — внешние условия функционирования; "
            "допущения явно отделены от требований.",
        ],
    )
    _add_table(
        doc,
        ["ID", "Техническое ограничение"],
        spec.CONSTRAINTS,
        caption="Технические ограничения текущего решения",
    )
    _add_table(
        doc,
        ["ID", "Зависимость"],
        spec.DEPENDENCIES,
        caption="Внешние и эксплуатационные зависимости",
    )
    _add_table(
        doc,
        ["ID", "Допущение", "Владелец", "Состояние", "Срок разрешения"],
        spec.ASSUMPTIONS,
        caption="Допущения спецификации",
    )

    _add_h2_block(
        doc,
        "8.10 Тестовые сценарии",
        [
            "Ниже приведен минимальный набор проверок, покрывающий все "
            "формализованные требования. Детальная программа испытаний может "
            "расширять шаги, сохраняя связь с указанными идентификаторами.",
        ],
    )
    _add_table(
        doc,
        [
            "TC",
            "Требования",
            "Предусловия",
            "Действия",
            "Ожидаемый результат",
            "Тип",
        ],
        spec.TEST_CASES,
        caption="Минимальный набор тестовых сценариев",
        font_size=7.5,
    )

    _add_h2_block(
        doc,
        "8.11 Матрица трассируемости",
        [
            "Матрица подтверждает отсутствие требований, не связанных "
            "с проверкой. Статус «Покрыто» означает наличие хотя бы одного "
            "тестового сценария; он не заменяет протокол фактического испытания.",
        ],
    )
    _add_table(
        doc,
        ["Требование", "Тест", "Критерий / ожидаемый результат", "Покрытие"],
        spec.traceability_rows(),
        caption="Матрица трассируемости требований и тестовых сценариев",
        font_size=8.0,
    )

    # ----- 9 Рекомендации -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "9 Рекомендации по развитию", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(
        doc,
        [
            "В настоящем разделе собраны предложения, которые не являются "
            "описанием действующего поведения. Их отделение от раздела 8 "
            "исключает смешение фактической реализации и целевого состояния.",
        ],
    )
    for title, paragraphs in spec.RECOMMENDATIONS.items():
        _add_h2_block(doc, title, paragraphs)

    # ----- Предметный указатель -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "ПРЕДМЕТНЫЙ УКАЗАТЕЛЬ", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(
        doc,
        [
            "В указателе приведены ссылки на номера разделов документа; "
            "страничные номера уточняются после обновления полей Word.",
        ],
    )
    for entry in spec.SUBJECT_INDEX:
        nir.add_styled(doc, entry, nir.STYLE_BODY)

    # ----- Заключение -----
    nir.add_page_break(doc)
    nir.add_styled(doc, "Заключение", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, CONCLUSION)
    nir.add_styled(
        doc,
        f"Экранные формы приведены на рисунках 1–{figs.n}.",
        nir.STYLE_BODY,
    )

    n_pages = nir.estimate_page_count(doc, figs.n)
    for para in doc.paragraphs:
        if para.text.startswith("Документ ") and " с.," in para.text:
            nir.set_paragraph_text(
                para,
                f"Документ {n_pages} с., 1 кн., {TABLE_COUNT_ACTUAL} табл., "
                f"{figs.n} рис., 0 прил.",
            )
            break

    nir.sanitize_document_artifacts(doc)
    _normalize_unicode_and_fonts(doc)

    saved: list[str] = []
    primary = OUT_PATHS[0]
    primary.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(primary))
    saved.append(str(primary))
    for path in OUT_PATHS[1:]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(primary, path)
            saved.append(str(path))
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: cannot save {path}: {exc}")

    work.unlink(missing_ok=True)
    print(f"TEMPLATE={TEMPLATE}")
    print(f"FIGURES_INSERTED={figs.n}")
    print(f"TABLES_INSERTED={TABLE_COUNT_ACTUAL}")
    print(f"PAGES_EST={n_pages}")
    return saved


if __name__ == "__main__":
    for p in build():
        print(p)
