# -*- coding: utf-8 -*-
"""
Описание программного комплекса АРМ «Генеральная схема»
(по модулям, со скриншотами; без привязки к ТЗ / приемке этапа).

Стиль оформления – шаблон НИР НИО-10 (как у отчета Этапа 1).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm

ROOT = Path(r"c:\arm_gs\reports")
sys.path.insert(0, str(ROOT))

import generate_stage1_report as src  # noqa: E402
import generate_stage1_report_nir as nir  # noqa: E402

# Шаблон со стилями 7.32: берем из готового отчета Этапа 1 (если Z: недоступен –
# исходный файл 2025 г.), иначе из каталога отчетов НИР 2025.
def _resolve_template() -> Path:
    local = ROOT / "Отчет_Этап1_АРМ_ГС-2026_выполненные_работы.docx"
    if local.exists():
        return local
    folder = Path(r"Z:\НИО-10\АРМ ГС\Отчеты НИР\2025 год")
    if folder.exists():
        found = sorted(p for p in folder.glob("*.docx") if not p.name.startswith("~$"))
        if found:
            return found[0]
    z2026 = Path(r"Z:\НИО-10\АРМ ГС\Отчеты НИР\2026 год") / "Отчет_Этап 1_АРМ_ГС-2026.docx"
    if z2026.exists():
        return z2026
    raise FileNotFoundError(
        "Не найден шаблон DOCX со стилями НИР (локальный отчет Этапа 1 или Z:\\…\\2025 год)."
    )


TEMPLATE = _resolve_template()

OUT_PATHS = [
    ROOT / "Описание_АРМ_ГС_текущая_реализация.docx",
    Path(r"Z:\НИО-10\АРМ ГС\Отчеты НИР\2026 год")
    / "Описание_АРМ_ГС_текущая_реализация.docx",
    Path(r"Z:\НИО-10\АРМ ГС\ТЗ на 2026 год")
    / "Описание_АРМ_ГС_текущая_реализация.docx",
]

# Подразделы главы модуля – описание реализации, не соответствие ТЗ
DESC_SECTION_TITLES = [
    "Назначение модуля",
    "Состав данных и архитектура",
    "Реализованный функционал",
    "Пользовательский интерфейс и сценарии работы",
    "Обмен данными и связи с другими модулями",
]

PROJECT_NAME = (
    "Разработка программного комплекса АРМ «Генеральная схема» "
    "в части реализации полнофункционального программного решения"
)

DOC_TITLE = (
    "ОПИСАНИЕ ПРОГРАММНОГО КОМПЛЕКСА АРМ «ГЕНЕРАЛЬНАЯ СХЕМА»: "
    "СОСТАВ МОДУЛЕЙ И ТЕКУЩАЯ РЕАЛИЗАЦИЯ"
)

KEYWORDS = (
    "АРМ ГЕНЕРАЛЬНАЯ СХЕМА, МОДУЛИ, СПРАВОЧНИКИ, ГЕНЕРАЦИЯ, НАГРУЗКИ, СПРОС, "
    "БАЛАНСЫ ЭЛЕКТРОЭНЕРГИИ И МОЩНОСТИ, ТОПЛИВО, ЭЛЕКТРОЕМКОСТЬ, "
    "ВЫХОДНЫЕ ДОКУМЕНТЫ, ВЕРСИОНИРОВАНИЕ ДАННЫХ, ПРОГРАММНЫЙ КОМПЛЕКС."
)

REFERAT_TEXT = (
    "Приведено описание программного комплекса АРМ «Генеральная схема» "
    "в составе реализованных на сегодняшний день модулей: инфраструктура "
    "и версии БД, «Справочники», «Генерация», «Нагрузки», «Спрос», "
    "«Балансы электроэнергии и мощности», «Топливо», «Электроемкость» "
    "(с контуром «Экономика»), передача данных и выходные материалы. "
    "Для каждого модуля даны назначение, состав функций, интерфейс и "
    "экранные формы."
)

INTRO = [
    "Настоящий документ содержит описание программного комплекса "
    "АРМ «Генеральная схема» в том виде, в котором он реализован и "
    "доступен пользователям на сегодняшний день.",
    "Комплекс предназначен для ведения данных и выполнения расчетно-"
    "аналитических процедур, используемых при подготовке материалов "
    "генеральной схемы размещения объектов электроэнергетики. Работа "
    "организована в виде веб-приложения (стек Flask) с хранением данных "
    "в СУБД PostgreSQL; прикладные сведения ведутся в разрезе версий "
    "базы данных и с разграничением прав доступа.",
    "Ниже по главам описаны модули комплекса: назначение, состав данных, "
    "реализованный функционал, пользовательский интерфейс и связи с "
    "другими модулями. Изложение сопровождается экранными формами "
    "текущей реализации.",
]

CONCLUSION = [
    "Программный комплекс АРМ «Генеральная схема» на сегодняшний день "
    "включает инфраструктурный контур (версии БД, пользователи и роли, "
    "журналы) и прикладные модули «Справочники», «Генерация», «Нагрузки», "
    "«Спрос», «Балансы электроэнергии и мощности», «Топливо», "
    "«Электроемкость» (совместно с контуром «Экономика»), а также средства "
    "передачи данных и подготовки выходных материалов.",
    "Модули обеспечивают ввод и корректировку данных в выбранной версии БД, "
    "табличный обмен, расчетные процедуры (в том числе топливный контур "
    "«Коэфф → Распред → Топливо») и передачу объектов генерации во внешний "
    "контур АРМ «Экономика».",
    "Отдельные элементы интерфейса, отмеченные в главах как развитие "
    "(например, площадки ТЭС, электроемкость по субъектам РФ, обратный "
    "канал обмена), в текущей поставке не завершены и не входят в "
    "описываемый рабочий контур.",
]

KNOWN_LIMITS = [
    "Ниже перечислены элементы, которые в интерфейсе или архитектуре "
    "предусмотрены, но на сегодняшний день не входят в завершенный "
    "рабочий контур:",
    "перспективные площадки ТЭС на хабе «Генерация» – заготовка;",
    "электроемкость по субъектам РФ – пункт развития на стартовой "
    "странице долгосрочного прогноза;",
    "обратный канал обмена с АРМ «Экономика» (квитанции приема, "
    "разрешение конфликтов версий) – не реализован; действует прямой "
    "канал передачи станций и агрегатов;",
    "расширенный промышленный контур информационной безопасности "
    "(TLS/ГОСТ на периметре, регламент целостности с автоблокировкой, "
    "анализ уязвимостей обновлений, аппаратные ключи и контейнеры) – "
    "вне текущего описания базовой реализации.",
]


def _ru_module(text: str) -> str:
    """Подсистема → модуль в пользовательских формулировках."""
    repl = (
        ("подсистема «", "модуль «"),
        ("Подсистема «", "Модуль «"),
        ("подсистемы «", "модуля «"),
        ("Подсистемы «", "Модуля «"),
        ("подсистемой «", "модулем «"),
        ("подсистем ", "модулей "),
        ("подсистемы ", "модули "),
        ("смежными подсистемами", "смежными модулями"),
        ("смежных подсистем", "смежных модулей"),
        ("прикладных подсистем", "прикладных модулей"),
        ("Этапа 1", "текущей реализации"),
        ("этапа 1", "текущей реализации"),
        ("по Этапу 1", "в текущей реализации"),
        ("в рамках Этапа 1", "в текущей реализации"),
        ("на Этапе 1", "на сегодняшний день"),
        ("Этап 1", "текущая поставка"),
    )
    out = text
    for a, b in repl:
        out = out.replace(a, b)
    return out


def _paras(mod: dict, key: str) -> list[str]:
    return [_ru_module(p) for p in mod.get(key, [])]


def adapt_module(mod: dict[str, list[str]]) -> dict[str, list[str]]:
    """Собрать описательные разделы из текстов отчета."""
    purpose = _paras(
        mod, "Назначение модуля и место в архитектуре АРМ «Генеральная схема»"
    )
    arch = _paras(mod, "Архитектура решения и структура данных")
    func = _paras(mod, "Реализованный функционал")
    ui = _paras(mod, "Пользовательский интерфейс и сценарии работы")
    ie = _paras(mod, "Импорт, экспорт и формирование выходных материалов")
    integ = _paras(mod, "Интеграция со смежными подсистемами")
    results = _paras(mod, "Результаты выполнения работ по модулю")

    exchange = ie + integ
    if results:
        exchange = exchange + [
            "Текущее состояние модуля. " + results[0]
            if not results[0].startswith("Текущее")
            else results[0]
        ] + results[1:]

    return {
        "Назначение модуля": purpose,
        "Состав данных и архитектура": arch,
        "Реализованный функционал": func,
        "Пользовательский интерфейс и сценарии работы": ui,
        "Обмен данными и связи с другими модулями": exchange,
    }


def adapt_bullets(bullets: dict[str, list[str]] | None) -> dict[str, list[str]]:
    if not bullets:
        return {}
    out: dict[str, list[str]] = {}
    for k, items in bullets.items():
        key = "Реализованный функционал" if "функционал" in k.lower() else k
        out[key] = [_ru_module(x) for x in items]
    return out


def _fix_captions(
    figures: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    return [(stem, _ru_module(cap)) for stem, cap in figures]


def update_title_page_desc(doc: Document) -> None:
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

    nir.replace_unique_row_text(table, 7, PROJECT_NAME)
    nir.replace_unique_row_text(table, 8, DOC_TITLE)
    nir.replace_unique_row_text(
        table,
        9,
        "(описание текущей реализации)\n\n\n"
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


def update_referat_desc(doc: Document, n_figures: int, n_pages: int | None = None) -> None:
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
                    f"Документ {pages_token} с., 1 кн., 0 табл., {n_figures} рис., 2 прил.",
                )
            elif updated == 1:
                nir.set_paragraph_text(para, KEYWORDS)
            elif updated == 2:
                nir.set_paragraph_text(para, REFERAT_TEXT)
            updated += 1
            if updated >= 3:
                break


def write_desc_chapter(
    doc: Document,
    title: str,
    sections: dict[str, list[str]],
    bullets: dict[str, list[str]] | None,
    figures: list[tuple[str, str]],
    fig_counter: nir.FigureCounter,
    *,
    chapter_key: str | None = None,
) -> None:
    """Глава модуля с описательными подразделами (логика рисунков – как в NIR)."""
    # Переиспользуем NIR-главу, временно подменив SECTION_TITLES
    old = list(src.SECTION_TITLES)
    try:
        src.SECTION_TITLES[:] = DESC_SECTION_TITLES  # type: ignore[index]
        # SECTION_TITLES is a list – replace contents
    except Exception:
        pass
    # Safer: call internal loop ourselves copying nir.write_module_chapter logic
    # with DESC_SECTION_TITLES – monkeypatch list:
    src.SECTION_TITLES.clear()
    src.SECTION_TITLES.extend(DESC_SECTION_TITLES)
    try:
        nir.write_module_chapter(
            doc,
            title,
            sections,
            bullets,
            _fix_captions(figures),
            fig_counter,
            chapter_key=chapter_key,
        )
    finally:
        src.SECTION_TITLES.clear()
        src.SECTION_TITLES.extend(old)


def build() -> list[str]:
    work = ROOT / "_sys_desc_work.docx"
    shutil.copy2(TEMPLATE, work)
    doc = Document(str(work))
    figs = nir.FigureCounter()

    update_title_page_desc(doc)
    unique_stems = {
        stem for items in nir.CHAPTER_FIGURES.values() for stem, _ in items
    }
    update_referat_desc(doc, n_figures=len(unique_stems))

    nir.delete_body_after(doc, keep_until_idx=39)
    nir.ensure_blank_after_template_headings(doc)

    chapters = [
        (
            "infra",
            "Модуль инфраструктуры и версий базы данных",
            adapt_module(src.INFRA),
            adapt_bullets(src.INFRA_BULLETS),
        ),
        (
            "refdata",
            "Модуль «Справочники»",
            adapt_module(src.REFDATA),
            adapt_bullets(src.REFDATA_BULLETS),
        ),
        (
            "generation",
            "Модуль «Генерация»",
            adapt_module(src.GENERATION),
            adapt_bullets(src.GENERATION_BULLETS),
        ),
        (
            "loads",
            "Модуль «Нагрузки»",
            adapt_module(src.POWER_DEMAND),
            adapt_bullets(src.POWER_DEMAND_BULLETS),
        ),
        (
            "demand",
            "Модуль «Спрос»",
            adapt_module(src.ENERGY_CONSUMPTION),
            adapt_bullets(src.ENERGY_CONSUMPTION_BULLETS),
        ),
        (
            "balance",
            "Модуль «Балансы электроэнергии и мощности»",
            adapt_module(src.ENERGY_BALANCE),
            adapt_bullets(src.ENERGY_BALANCE_BULLETS),
        ),
        (
            "fuel",
            "Модуль «Топливо»",
            adapt_module(src.FUEL),
            adapt_bullets(src.FUEL_BULLETS),
        ),
        (
            "ei",
            "Модуль «Электроемкость» и контур «Экономика»",
            adapt_module(src.ELECTRICAL_INTENSITY),
            adapt_bullets(src.ELECTRICAL_INTENSITY_BULLETS),
        ),
        (
            "docs",
            "Модуль передачи данных и выходных документов",
            adapt_module(src.OUTPUT_DOCS),
            adapt_bullets(src.OUTPUT_DOCS_BULLETS),
        ),
    ]

    # Содержание
    nir.add_page_break(doc)
    nir.add_styled(doc, "СОДЕРЖАНИЕ", nir.STYLE_STRUCT_HIDDEN)
    toc = [
        "Перечень сокращений и обозначений",
        "Введение",
    ]
    for i, (_, title, _, _) in enumerate(chapters, start=1):
        toc.append(f"{i} {title}")
    toc.extend(
        [
            "Ограничения текущей версии",
            "Заключение",
            "Приложение А Состав разделов описания модуля",
            "Приложение Б Логика расчетного модуля трех кнопок "
            "«Коэфф», «Распред», «Топливо»",
        ]
    )
    for item in toc:
        nir.add_styled(doc, item, nir.STYLE_BODY)

    # Сокращения
    nir.add_page_break(doc)
    nir.add_styled(doc, "ПЕРЕЧЕНЬ СОКРАЩЕНИЙ И ОБОЗНАЧЕНИЙ", nir.STYLE_STRUCT_TOC)
    nir.add_styled(
        doc,
        "В настоящих материалах применяют следующие сокращения и обозначения:",
        nir.STYLE_BODY,
    )
    for abbr, meaning in nir.ABBREVIATIONS:
        nir.add_styled(doc, f"{abbr} – {meaning};", nir.STYLE_BODY)

    # Введение
    nir.add_page_break(doc)
    nir.add_styled(doc, "Введение", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, INTRO)
    nir.add_styled(
        doc,
        "Общий вид стартовой страницы АРМ «Генеральная схема» с группировкой "
        "модулей представлен на рисунке ниже.",
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
            f"На рисунке {n0} представлена главная страница АРМ с разделами "
            "«Энергоресурсы и балансы», «Потребление», «Прогноз и территории» "
            "и «Нормативно-справочная информация».",
            nir.STYLE_BODY,
        )

    for key, title, sections, bullets in chapters:
        nir.add_page_break(doc)
        write_desc_chapter(
            doc,
            title,
            sections,
            bullets,
            nir.CHAPTER_FIGURES.get(key, []),
            figs,
            chapter_key=key,
        )

    # Ограничения (технические, без ТЗ)
    nir.add_page_break(doc)
    nir.add_styled(doc, "Ограничения текущей версии", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, KNOWN_LIMITS)

    # Заключение
    nir.add_page_break(doc)
    nir.add_styled(doc, "Заключение", nir.STYLE_STRUCT_TOC)
    nir.add_body_paras(doc, CONCLUSION)
    nir.add_styled(
        doc,
        f"Экранные формы модулей приведены на рисунках 1–{figs.n}.",
        nir.STYLE_BODY,
    )

    # Приложение А
    nir.add_page_break(doc)
    nir.add_styled(doc, "ПРИЛОЖЕНИЕ А", nir.STYLE_STRUCT_TOC)
    nir.add_styled(doc, "Состав разделов описания модуля", nir.STYLE_BODY)
    nir.add_styled(
        doc,
        "Главы по модулям изложены в следующем порядке разделов:",
        nir.STYLE_BODY,
    )
    nir.add_bullets(
        doc,
        [f"{t};" for t in DESC_SECTION_TITLES[:-1]]
        + [DESC_SECTION_TITLES[-1] + "."],
    )

    # Приложение Б
    nir.add_page_break(doc)
    nir.add_styled(doc, "ПРИЛОЖЕНИЕ Б", nir.STYLE_STRUCT_TOC)
    nir.add_styled(
        doc,
        "Логика расчетного модуля трех кнопок «Коэфф», «Распред», «Топливо»",
        nir.STYLE_BODY,
    )
    nir.add_body_paras(doc, nir.APPENDIX_B)
    nir.add_styled(doc, "Подготовка к расчету", nir.STYLE_H2)
    nir.add_body_paras(doc, nir.APPENDIX_B_PREP)
    nir.add_styled(doc, "Кнопка «Коэфф»", nir.STYLE_H2)
    nir.add_body_paras(doc, nir.APPENDIX_B_COEFF)
    nir.add_styled(doc, "Кнопка «Распред»", nir.STYLE_H2)
    nir.add_body_paras(doc, nir.APPENDIX_B_DIST)
    nir.add_styled(doc, "Кнопка «Топливо»", nir.STYLE_H2)
    nir.add_body_paras(doc, nir.APPENDIX_B_FUEL)
    nir.add_styled(doc, "Соответствие Access и АРМ", nir.STYLE_H2)
    nir.add_body_paras(doc, nir.APPENDIX_B_MAP)
    if getattr(nir, "APPENDIX_B_EXAMPLE", None):
        nir.add_styled(doc, "Численный пример расчета", nir.STYLE_H2)
        nir.add_body_paras(doc, nir.APPENDIX_B_EXAMPLE)
    nir.add_styled(
        doc,
        "Источник: выжимка reports/_fuel_three_buttons_extract.txt; оригинал "
        "«access_three_buttons.docx» (материалы «БД Топливо» НИО-10); "
        "реализация сервисов app/fuel/services/calculation.",
        nir.STYLE_BODY,
    )

    n_pages = nir.estimate_page_count(doc, figs.n)
    for para in doc.paragraphs:
        if para.text.startswith("Документ ") and " с.," in para.text:
            nir.set_paragraph_text(
                para,
                f"Документ {n_pages} с., 1 кн., 0 табл., {figs.n} рис., 2 прил.",
            )
            break

    nir.sanitize_document_artifacts(doc)

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
    print(f"FIGURES_INSERTED={figs.n}")
    print(f"PAGES_EST={n_pages}")
    return saved


if __name__ == "__main__":
    for p in build():
        print(p)
