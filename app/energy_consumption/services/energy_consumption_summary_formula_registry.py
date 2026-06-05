# -*- coding: utf-8 -*-
"""Справочник текстов формул (иконка «i») для сводок потребления ЭЭ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.energy_consumption.long_term_consumption.services.electrical_intensity_constants import (
    EI_POP_CALCULATED_FORMULA_TOOLTIP,
    EI_POP_COEFFICIENT_A_COMPUTED_FORMULA_TOOLTIP,
    EI_POP_COEFFICIENT_A_FORMULA_TOOLTIP,
    EI_POP_COEFFICIENT_X_FORMULA_TOOLTIP,
    EI_POP_DELTA_FORMULA_TOOLTIP,
    EI_POP_GRAPH_POINT_FORMULA_TOOLTIP,
    EI_POP_PER_CAPITA_FORMULA_TOOLTIP,
    EI_POP_REF_ACCUM_MONETARY_INCOME_FORMULA_TOOLTIP,
    EI_POP_REF_HOUSEHOLD_CONSUMPTION_FORMULA_TOOLTIP,
    EI_POP_REF_POPULATION_FORMULA_TOOLTIP,
    POP_REF_ROW_LABEL_BY_KIND,
    POP_ROW_LABEL_BY_KIND,
    REF_ROW_ACCUM_MONETARY_INCOME,
    REF_ROW_HOUSEHOLD_CONSUMPTION,
    REF_ROW_POPULATION,
    ROW_KIND_CALCULATED,
    ROW_KIND_DELTA,
    ROW_KIND_GRAPH_POINT,
    ROW_KIND_INTENSITY,
)

PAGE_SUMMARY_TABLE = "summary_table"
PAGE_OES = "oes"
PAGE_FO = "fo"
PAGE_EZ = "ez"
PAGE_OES_GAES_CHARGE = "oes_gaes_charge"
PAGE_ELECTRICAL_INTENSITY = "electrical_intensity"

ALL_SUMMARY_PAGES = frozenset(
    {
        PAGE_SUMMARY_TABLE,
        PAGE_OES,
        PAGE_FO,
        PAGE_EZ,
        PAGE_OES_GAES_CHARGE,
    }
)

PAGE_LABELS: dict[str, str] = {
    PAGE_SUMMARY_TABLE: "Сводная таблица (/summary-table/)",
    PAGE_OES: "По энергосистемам (/summary/oes/)",
    PAGE_FO: "По федеральным округам (/summary/federal-districts/)",
    PAGE_EZ: "По энергозонам (/summary/energy-zones/)",
    PAGE_OES_GAES_CHARGE: "ГАЭС на заряд (/summary/oes/gaes-charge/)",
    PAGE_ELECTRICAL_INTENSITY: "Электроёмкость (/energy_consumption/electrical-intensity/)",
}


@dataclass(frozen=True)
class EcSummaryFormulaDef:
    key: str
    pages: frozenset[str]
    aggregation_level: str
    cell_name: str
    default_text: str

    def page_label_lines(self) -> tuple[str, ...]:
        """Подписи страниц по одной на строку (для столбца «Страница»)."""
        if self.pages == ALL_SUMMARY_PAGES:
            return ("Все перечисленные сводки",)
        ordered = [PAGE_LABELS[p] for p in sorted(self.pages)]
        lines: list[str] = []
        for i, label in enumerate(ordered):
            lines.append(label + ";" if i < len(ordered) - 1 else label)
        return tuple(lines)

    def page_labels(self) -> str:
        return "\n".join(self.page_label_lines())


def _def(
    key: str,
    *,
    pages: frozenset[str] | None = None,
    aggregation_level: str,
    cell_name: str,
    default_text: str,
) -> EcSummaryFormulaDef:
    return EcSummaryFormulaDef(
        key=key,
        pages=pages or ALL_SUMMARY_PAGES,
        aggregation_level=aggregation_level,
        cell_name=cell_name,
        default_text=default_text.strip(),
    )


EC_SUMMARY_FORMULA_REGISTRY: tuple[EcSummaryFormulaDef, ...] = (
    _def(
        "yoy_growth",
        aggregation_level="Показатель (строка таблицы)",
        cell_name="Годовой темп прироста, %",
        default_text=(
            "Годовой темп прироста, % = (потребление ЭЭ за текущий год / "
            "потребление ЭЭ за предыдущий год) × 100 − 100"
        ),
    ),
    _def(
        "sipr_yoy_growth",
        aggregation_level="Показатель (строка таблицы)",
        cell_name="Годовой темп прироста (СиПР), %",
        default_text=(
            "Годовой темп прироста (СиПР), % = (потребление ЭЭ за текущий год / "
            "потребление ЭЭ за предыдущий год) × 100 − 100"
        ),
    ),
    _def(
        "sipr_abs_growth",
        aggregation_level="Показатель (строка таблицы)",
        cell_name="Абсолютный прирост потребления (СиПР), млн кВт·ч",
        default_text=(
            "Абсолютный прирост потребления электрической энергии (СиПР) = "
            "потребление электроэнергии (СиПР) этого года — потребление "
            "электроэнергии (СиПР) прошлого года, млн кВт·ч"
        ),
    ),
    _def(
        "verify_for_ues",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ОЭС",
        default_text=(
            "Проверка для ОЭС = потребление ЭЭ по ОЭС - сумма потребление ЭЭ "
            "по всем РЭС данной ОЭС"
        ),
    ),
    _def(
        "verify_for_fo",
        pages=frozenset({PAGE_FO, PAGE_SUMMARY_TABLE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ФО",
        default_text=(
            "Проверка для ФО = потребление ЭЭ по ФО − сумма потребления ЭЭ "
            "по всем РЭС данного ФО (строки О-1 не учитываются)"
        ),
    ),
    _def(
        "verify_for_res",
        pages=frozenset({PAGE_OES, PAGE_FO, PAGE_EZ, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для РЭС",
        default_text=(
            "Проверка для РЭС = потребление ЭЭ РЭС - сумма потребления "
            "всех субъектов РФ этой РЭС"
        ),
    ),
    _def(
        "verify_for_tites_res_eu",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ЭС (ТИТЭС)",
        default_text=(
            "Проверка для ЭС = потребление ЭЭ ЭС − сумма потребления ЭЭ "
            "энергорайонов без варианта o1, входящих в ЭС"
        ),
    ),
    _def(
        "verify_for_tites_aggregate",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ТИТЭС",
        default_text=(
            "Проверка для ТИТЭС = потребление ТИТЭС − сумма потребления ЭЭ "
            "всех энергорайонов, входящих в ТИТЭС, − Западный энергорайон − "
            "Центральный энергорайон Республики Саха (Якутия) "
            "(строки с вариантом О-1 не учитываются; западный и центральный "
            "энергорайоны ЭС Республики Саха (Якутия) учитываются только "
            "до 2019 года включительно)"
        ),
    ),
    _def(
        "verify_ees_with_nt",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ЕЭС России с НТ",
        default_text=(
            "Проверка для ЕЭС России с НТ = потребление ЭЭ ЕЭС России с НТ - "
            "сумма потребления всех ОЭС (с НТ)"
        ),
    ),
    _def(
        "verify_ees_without_nt",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ЕЭС России без НТ",
        default_text=(
            "Проверка для ЕЭС России без НТ = потребление ЭЭ ЕЭС России без НТ "
            "сумма потребления всех ОЭС (без НТ)"
        ),
    ),
    _def(
        "verify_south_with_nt",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ОЭС Юга с НТ",
        default_text=(
            "Проверка для ОЭС Юга с НТ = потребление ЭЭ ОЭС Юга (с НТ) – "
            "сумма потребления всех РЭС ОЭС Юга - потребление ЭЭ Новыми территориями"
        ),
    ),
    _def(
        "verify_south_without_nt",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ОЭС Юга без НТ",
        default_text=(
            "Проверка для ОЭС Юга без НТ = потребление ЭЭ ОЭС Юга (без НТ) – "
            "сумма потребления всех РЭС ОЭС Юга; для 2016 года и ранее из суммы "
            "РЭС исключается ЭС Республики Крым и г. Севастополя"
        ),
    ),
    _def(
        "ez_mln",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="Энергозона",
        cell_name="Потребление ЭЭ энергозоны, млн кВт·ч",
        default_text=(
            "Потребление ЭЭ энергозоны, млн кВт·ч = сумма потребления ЭЭ "
            "всех РЭС, входящих в эту энергозону"
        ),
    ),
    _def(
        "ez_sipr",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="Энергозона",
        cell_name="Потребление ЭЭ энергозоны (СиПР), млн кВт·ч",
        default_text=(
            "Потребление ЭЭ энергозоны (СиПР), млн кВт·ч = сумма потребления "
            "ЭЭ (СиПР) всех РЭС, входящим в эту энергозону"
        ),
    ),
    _def(
        "fo_mln",
        pages=frozenset({PAGE_FO, PAGE_SUMMARY_TABLE}),
        aggregation_level="Федеральный округ",
        cell_name="Потребление ЭЭ по ФО, млн кВт·ч",
        default_text=(
            "Потребление ЭЭ по ФО, млн кВт·ч = сумма потребления ЭЭ всех РЭС, "
            "входящих в данный ФО"
        ),
    ),
    _def(
        "fo_sipr",
        pages=frozenset({PAGE_FO, PAGE_SUMMARY_TABLE}),
        aggregation_level="Федеральный округ",
        cell_name="Потребление ЭЭ по ФО (СиПР), млн кВт·ч",
        default_text=(
            "Потребление ЭЭ по ФО (СиПР), млн кВт·ч = сумма потребления ЭЭ (СиПР) "
            "всех РЭС, входящих в данный ФО"
        ),
    ),
    _def(
        "fo_formula_aggregate",
        pages=frozenset({PAGE_FO, PAGE_SUMMARY_TABLE}),
        aggregation_level="Федеральный округ",
        cell_name="Потребление по ФО (расчётная строка)",
        default_text="Потребление по ФО = сумма потребления ЭЭ всех РЭС, входящих в данный ФО",
    ),
    _def(
        "south_fo_with_nt",
        pages=frozenset({PAGE_FO, PAGE_SUMMARY_TABLE}),
        aggregation_level="Федеральный округ",
        cell_name="Южный ФО (+НТ)",
        default_text=(
            "Потребление по Южному ФО (+НТ) = сумма потребления ЭЭ всех РЭС, "
            "входящих в Южный ФО, + сумма по блоку «Новые территории»"
        ),
    ),
    _def(
        "fo_gaes_adj_sum_res",
        aggregation_level="Без заряда ГАЭС",
        cell_name="Потребление ФО без заряда ГАЭС",
        default_text=(
            "Потребление электрической энергии без заряда ГАЭС, млн кВт·ч = "
            "Потребление ФО − заряд ГАЭС"
        ),
    ),
    _def(
        "rd_gaes_adj",
        aggregation_level="Без заряда ГАЭС",
        cell_name="Субъект РФ без заряда ГАЭС",
        default_text=(
            "Потребление электрической энергии без заряда ГАЭС, млн кВт·ч = "
            "Потребление субъекта РФ − заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_fd_oes",
        aggregation_level="Без заряда ГАЭС",
        cell_name="ФО / ОЭС (общая формула)",
        default_text=(
            "Потребление электрической энергии без заряда ГАЭС, млн кВт·ч = "
            "Потребление с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_ez",
        aggregation_level="Без заряда ГАЭС",
        cell_name="Энергозона",
        default_text=(
            "Потребление электрической энергии без заряда ГАЭС, млн кВт·ч = "
            "Потребление с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_ees_russia_ez",
        aggregation_level="Без заряда ГАЭС",
        cell_name="ЕЭС России (энергозоны)",
        default_text=(
            "Потребление электрической энергии без заряда ГАЭС, млн кВт·ч = "
            "Потребление с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_ees_russia_with_nt",
        aggregation_level="Без заряда ГАЭС",
        cell_name="ЕЭС России с НТ",
        default_text=(
            "Потребление ЕЭС России с НТ без заряда ГАЭС, млн кВт·ч = "
            "Потребление ЕЭС России с НТ с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_ees_russia_without_nt",
        aggregation_level="Без заряда ГАЭС",
        cell_name="ЕЭС России без НТ",
        default_text=(
            "Потребление ЕЭС России без НТ без заряда ГАЭС, млн кВт·ч = "
            "Потребление ЕЭС России без НТ с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_sa",
        aggregation_level="Без заряда ГАЭС",
        cell_name="Синхронная зона",
        default_text=(
            "Потребление электрической энергии без заряда ГАЭС, млн кВт·ч = "
            "Потребление с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_generic",
        aggregation_level="Без заряда ГАЭС",
        cell_name="Общая строка",
        default_text=(
            "Потребление электрической энергии без заряда ГАЭС, млн кВт·ч = "
            "Потребление с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_first_sa_with_nt_without_gaes",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ с НТ без заряда ГАЭС",
        default_text=(
            "Первая синхронная зона с НТ без заряда ГАЭС, млн кВт·ч = "
            "Первая синхронная зона с НТ с зарядом ГАЭС - заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_first_sa_with_nt_without_kaliningrad_without_gaes",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ с НТ без заряда ГАЭС (без ЭС Калининграда)",
        default_text=(
            "Первая синхронная зона с НТ без заряда ГАЭС (без ЭС Калининградской области), "
            "млн кВт·ч = Первая синхронная зона с НТ с зарядом ГАЭС "
            "(с ЭС Калининградской области) − заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_first_sa_without_nt_kaliningrad_without_gaes",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ без НТ без заряда ГАЭС (с ЭС Калининграда)",
        default_text=(
            "Первая синхронная зона без НТ без заряда ГАЭС (с ЭС Калининградской области) = "
            "Первая синхронная зона без НТ с зарядом ГАЭС (с ЭС Калининградской области) - "
            "заряд ГАЭС"
        ),
    ),
    _def(
        "gaes_adj_first_sa_without_nt_without_kaliningrad_without_gaes",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ без НТ без заряда ГАЭС (без ЭС Калининграда)",
        default_text=(
            "Первая синхронная зона без НТ без заряда ГАЭС (без ЭС Калининградской области) = "
            "Первая синхронная зона без НТ с зарядом ГАЭС (без ЭС Калининградской области) − "
            "заряд ГАЭС"
        ),
    ),
    _def(
        "first_sa_with_nt_with_gaes",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ с НТ с зарядом ГАЭС",
        default_text=(
            "Первая синхронная зона с НТ с зарядом ГАЭС (с ЭС Калининградской области), "
            "млн кВт·ч = сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
            "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области) + заряд ГАЭС + "
            "потребление ЭЭ Новыми территориями"
        ),
    ),
    _def(
        "first_sa_with_nt_with_gaes_with_kaliningrad_py",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ с НТ с зарядом ГАЭС (расчёт, Python)",
        default_text=(
            "Потребление Первая синхронная зона с НТ с зарядом ГАЭС (с ЭС Калининградской области), "
            "млн кВт·ч = сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
            "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области) + "
            "заряд ГАЭС + "
            "потребление ЭЭ Новыми территориями"
        ),
    ),
    _def(
        "first_sa_without_nt_without_kaliningrad_with_gaes",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ без НТ с зарядом ГАЭС",
        default_text=(
            "Первая синхронная зона без НТ с зарядом ГАЭС (без ЭС Калининградской области), "
            "млн кВт·ч = сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
            "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области, ОЭС Юга и ОЭС Центра "
            "с зарядом ГAЭС), без ОЭС Востока и ОЭС «Новые территории» − "
            "потребление ЭС Калининградской области"
        ),
    ),
    _def(
        "first_sa_with_nt_without_gaes_without_kaliningrad",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ с НТ без заряда ГАЭС (без ЭС Калининграда)",
        default_text=(
            "Потребление Первая синхронная зона с НТ без заряда ГАЭС "
            "(без ЭС Калининградской области), млн кВт·ч = "
            "Первая синхронная зона с НТ с зарядом ГАЭС (с ЭС Калининградской области) − "
            "заряд ГАЭС"
        ),
    ),
    _def(
        "first_sa_without_nt_with_gaes_without_kaliningrad",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ без НТ с зарядом ГАЭС",
        default_text=(
            "Потребление Первая синхронная зона без НТ с зарядом ГАЭС "
            "(без ЭС Калининградской области), млн кВт·ч = "
            "сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
            "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области, ОЭС Юга и ОЭС Центра "
            "с зарядом ГАЭС), без ОЭС Востока и ОЭС «Новые территории» − "
            "потребление ЭС Калининградской области"
        ),
    ),
    _def(
        "first_sa_without_nt_without_gaes_with_kaliningrad",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ без НТ без заряда ГАЭС (с ЭС Калининграда)",
        default_text=(
            "Потребление Первая синхронная зона без НТ без заряда ГАЭС "
            "(с ЭС Калининградской области), млн кВт·ч = "
            "Первая синхронная зона без НТ с зарядом ГАЭС (с ЭС Калининградской области) − "
            "заряд ГАЭС"
        ),
    ),
    _def(
        "first_sa_without_nt_without_gaes_without_kaliningrad",
        aggregation_level="Синхронная зона",
        cell_name="Первая СЗ без НТ без заряда ГАЭС (без ЭС Калининграда)",
        default_text=(
            "Потребление Первая синхронная зона без НТ без заряда ГАЭС "
            "(без ЭС Калининградской области), млн кВт·ч = "
            "Первая синхронная зона без НТ с зарядом ГАЭС (без ЭС Калининградской области) − "
            "заряд ГАЭС"
        ),
    ),
    _def(
        "ees_russia_ez_with_nt",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="ЕЭС России",
        cell_name="Потребление ЕЭС России с НТ",
        default_text=(
            "Потребление ЕЭС России с НТ, млн кВт·ч = сумма потребления ЭЭ всех ОЭС + "
            "потребление ЭЭ Новыми территориями"
        ),
    ),
    _def(
        "oes_ees_russia_without_nt_mln",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="ЕЭС России",
        cell_name="Потребление ЕЭС России, млн кВт·ч",
        default_text="Потребление ЕЭС России, млн кВт·ч = сумма потребления ЭЭ всех ОЭС",
    ),
    _def(
        "oes_ees_russia_with_nt_mln",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="ЕЭС России",
        cell_name="Потребление ЕЭС России с НТ, млн кВт·ч",
        default_text=(
            "Потребление ЕЭС России с НТ, млн кВт·ч = сумма потребления ЭЭ всех ОЭС + "
            "потребление ЭЭ Новыми территориями"
        ),
    ),
    _def(
        "oes_tites_mln",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="ТИТЭС",
        cell_name="Потребление ТИТЭС, млн кВт·ч",
        default_text=(
            "Потребление ТИТЭС, млн кВт·ч = сумма потребления ЭЭ всех энергорайонов, "
            "входящих в ТИТЭС, + Западный и Центральный энергорайоны ЭС Республики Саха "
            "(Якутия) (строки с вариантом О-1 не учитываются). "
            "Западный и Центральный энергорайоны ЭС Республики Саха (Якутия) учитываются "
            "только до 2019 года включительно"
        ),
    ),
    _def(
        "tites_oes_aggregate",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="ТИТЭС",
        cell_name="Потребление ТИТЭС (расчёт)",
        default_text=(
            "Потребление ТИТЭС, млн кВт·ч = сумма потребления ЭЭ всех энергорайонов, "
            "входящих в ТИТЭС, + Западный и Центральный энергорайоны ЭС Республики Саха "
            "(Якутия) (строки с вариантом О-1 не учитываются). "
            "Западный и Центральный энергорайоны ЭС Республики Саха (Якутия) учитываются "
            "только до 2019 года включительно"
        ),
    ),
    _def(
        "nt_under_south",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Новые территории",
        cell_name="Потребление «Новые территории»",
        default_text=(
            "Потребление «Новые территории», млн кВт·ч = "
            "сумма потребления ЭЭ всех субъектов РФ, входящих в блок «Новые территории»"
        ),
    ),
    _def(
        "ees_russia_without_nt_with_gaes",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="ЕЭС России",
        cell_name="ЕЭС России без НТ с зарядом ГАЭС",
        default_text=(
            "Потребление ЭЭС России без НТ с зарядом ГАЭС, млн кВт·ч = "
            "Первая синхронная зона без НТ с зарядом ГАЭС (с ЭС Калининградской области) + "
            "Вторая синхронная зона + "
            "ТИТЭС"
        ),
    ),
    _def(
        "ees_russia_with_nt_with_gaes",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="ЕЭС России",
        cell_name="ЕЭС России с НТ с зарядом ГАЭС",
        default_text=(
            "Потребление ЭЭС России с НТ с зарядом ГАЭС, млн кВт·ч = "
            "Первая синхронная зона с НТ с зарядом ГАЭС + "
            "Вторая синхронная зона + "
            "Синхронная зона Калининградской области + "
            "ТИТЭС + "
            "потребление ЭЭ Новыми территориями"
        ),
    ),
    _def(
        "second_sa_from_ues_east",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Синхронная зона",
        cell_name="Вторая синхронная зона",
        default_text="Потребление Вторая синхронная зона, млн кВт·ч = ОЭС Востока",
    ),
    _def(
        "kaliningrad_sa_from_es",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Синхронная зона",
        cell_name="Синхронная зона Калининградской области",
        default_text=(
            "Потребление Синхронная зона Калининградской области, млн кВт·ч = "
            "ЭС Калининградской области"
        ),
    ),
    _def(
        "east_energy_zone",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="Энергозона",
        cell_name="Энергозона Востока",
        default_text=(
            "Энергозона Востока = ЭС Амурской области + ЭС Приморского края + "
            "ЭС Хабаровского края и Еврейской АО + ЭС Республики Саха (Якутия) + "
            "Западный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно) + "
            "Центральный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно) + "
            "ЭС Камчатского края (О-1) + ЭС Чукотского АО (О-1) + "
            "ЭС Сахалинской области (О-1) + ЭС Магаданской области (О-1) + "
            "Изолированый энергорайон Республики Саха (Якутия) (О-1) + "
            "Николаевский энергорайон Хабаровского края (О-1)"
        ),
    ),
    _def(
        "cz_russia_with_nt",
        pages=frozenset({PAGE_SUMMARY_TABLE, PAGE_OES}),
        aggregation_level="Централизованные зоны",
        cell_name="ЦЗ России с НТ",
        default_text=(
            "Потребление ЦЗ России с НТ, млн кВт·ч = "
            "ОЭС Северо-Запада + ОЭС Центра с зарядом ГАЭС + ОЭС Средней Волги + "
            "ОЭС Юга с НТ с зарядом ГАЭС + ОЭС Урала + "
            "Энергозона Сибири + Энергозона Востока"
        ),
    ),
    _def(
        "cz_russia_without_nt",
        pages=frozenset({PAGE_SUMMARY_TABLE, PAGE_OES}),
        aggregation_level="Централизованные зоны",
        cell_name="ЦЗ России без НТ",
        default_text=(
            "Потребление ЦЗ России без НТ, млн кВт·ч = "
            "ОЭС Северо-Запада + ОЭС Центра с зарядом ГАЭС + ОЭС Средней Волги + "
            "ОЭС Юга без НТ с зарядом ГАЭС + ОЭС Урала + "
            "Энергозона Сибири + Энергозона Востока (с 2022 г.)"
        ),
    ),
    _def(
        "summary_table_cz_nt_reference",
        pages=frozenset({PAGE_SUMMARY_TABLE}),
        aggregation_level="Централизованные зоны",
        cell_name="СПРАВОЧНО. Новые территории",
        default_text=(
            "Потребление «Справочно. Новые территории», млн кВт·ч = "
            "ЦЗ России с НТ − ЦЗ России без НТ (с 2024 г.)"
        ),
    ),
    _def(
        "summary_table_decentralized_zone",
        pages=frozenset({PAGE_SUMMARY_TABLE}),
        aggregation_level="Россия",
        cell_name="Децентрализованная зона",
        default_text=(
            "Потребление «Децентрализованная зона», млн кВт·ч = "
            "Россия с НТ × 1000 − ЭЭС России без НТ с зарядом ГАЭС"
        ),
    ),
    _def(
        "chersky_reference_transfer",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE}),
        aggregation_level="Переток",
        cell_name="СПРАВОЧНО. Переток в пос. Черский",
        default_text=(
            "Переток в пос. Черский = ЭС Чукотского АО (О-1) − сумма входящих энергорайонов "
            "ЭС Чукотского АО (О-1)"
        ),
    ),
    _def(
        "chaun_bilibino_without_chersky",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE}),
        aggregation_level="Переток",
        cell_name="СПРАВОЧНО. Чаун-Билибинский энергорайон",
        default_text=(
            "СПРАВОЧНО. Чаун-Билибинский энергорайон без перетока в пос. Черский "
            "(Республика Саха (Якутия)) = "
            "Чаун-Билибинский энергорайон + "
            "СПРАВОЧНО. Переток в пос. Черский (Республика Саха (Якутия))"
        ),
    ),
    _def(
        "ez_res_sum_verification",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="Проверка",
        cell_name="Проверка для энергозоны",
        default_text=(
            "Проверка для энергозоны = потребление ЭЭ по энергозоне − "
            "сумма потребления ЭЭ по всем РЭС данной энергозоны "
            "(строки О-1 не учитываются)"
        ),
    ),
    _def(
        "oes_res_without_gaes_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка РЭС без заряда ГАЭС",
        default_text="Проверка потребления РЭС без заряда ГАЭС",
    ),
    _def(
        "tites_res_energy_unit_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка энергорайона ТИТЭС",
        default_text="Проверка для энергорайона в составе ТИТЭС",
    ),
    _def(
        "tites_oes_aggregate_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка для ТИТЭС (агрегат)",
        default_text=(
            "Проверка для ТИТЭС = потребление ТИТЭС − "
            "сумма потребления ЭЭ всех энергорайонов, входящих в ТИТЭС, − "
            "Западный энергорайон − Центральный энергорайон Республики Саха (Якутия) "
            "(строки с вариантом О-1 не учитываются; западный и центральный "
            "энергорайоны ЭС Республики Саха (Якутия) учитываются только "
            "до 2019 года включительно)"
        ),
    ),
    _def(
        "oes_res_with_gaes_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка РЭС с зарядом ГАЭС",
        default_text=(
            "Проверка = потребление ЭЭ РЭС с зарядом ГАЭС − "
            "сумма потребления ЭЭ субъектов РФ, входящих в РЭС "
            "(для субъектов с зарядом ГАЭС — значение «с зарядом ГАЭС»)"
        ),
    ),
    _def(
        "east_energy_zone_o1_parent_verification",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="Проверка",
        cell_name="Проверка для Энергозоны Востока",
        default_text=(
            "Энергозона Востока = Энергозона Востока − ЭС Камчатского края О-1 − "
            "ЭС Магаданской области О-1 − ЭС Сахалинской области О-1 − "
            "ЭС Чукотского АО О-1 − "
            "Изолированый энергорайон Республики Саха (Якутия) О-1 − "
            "Николаевский энергорайон Хабаровского края О-1 + "
            "ЭС Амурской области + ЭС Приморского края + "
            "ЭС Хабаровского края и Еврейской АО + ЭС Республики Саха (Якутия) + "
            "Западный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно) + "
            "Центральный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно)"
        ),
    ),
    _def(
        "east_ez_o1_res_energy_unit_verification",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="Проверка",
        cell_name="Проверка РЭС (О-1), энергозона Востока",
        default_text=(
            "Проверка = потребление ЭЭ РЭС (О-1) − "
            "сумма потребления ЭЭ энергорайонов (О-1), входящих в РЭС"
        ),
    ),
    _def(
        "chukotka_o1_res_energy_unit_verification",
        pages=frozenset({PAGE_EZ, PAGE_SUMMARY_TABLE}),
        aggregation_level="Проверка",
        cell_name="Проверка РЭС Чукотка (О-1)",
        default_text=(
            "Проверка = потребление ЭЭ РЭС (О-1) − "
            "сумма потребления ЭЭ энергорайонов (О-1), входящих в РЭС; "
            "вместо «Чаун-Билибинский энергорайон» — "
            "«СПРАВОЧНО. Чаун-Билибинский энергорайон без перетока в пос. Черский "
            "(Республика Саха (Якутия))» (О-1)"
        ),
    ),
    _def(
        "ees_russia_with_nt_gaes_kaliningrad_split_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка ЕЭС России с НТ с зарядом ГАЭС",
        default_text=(
            "Проверка = ЕЭС России с НТ с зарядом ГАЭС − "
            "(Первая синхронная зона с НТ с зарядом ГАЭС + "
            "Вторая синхронная зона) − "
            "Синхронная зона Калининградской области"
        ),
    ),
    _def(
        "ees_russia_without_nt_gaes_kaliningrad_split_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка ЕЭС России без НТ с зарядом ГАЭС",
        default_text=(
            "Проверка = ЕЭС России без НТ с зарядом ГАЭС − "
            "Первая синхронная зона без НТ с зарядом ГАЭС (без ЭС Калининградской области) − "
            "Вторая синхронная зона − "
            "Синхронная зона Калининградской области"
        ),
    ),
    _def(
        "first_sa_without_nt_gaes_without_kaliningrad_ues_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка первой СЗ без НТ с ГАЭС (без Калининграда)",
        default_text=(
            "Проверка = Первая синхронная зона без НТ с зарядом ГАЭС "
            "(без ЭС Калининградской области) − "
            "(сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
            "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области и ОЭС Юга с зарядом ГАЭС), "
            "без ОЭС Востока − потребление ЭС Калининградской области)"
        ),
    ),
    _def(
        "first_sa_without_nt_gaes_with_kaliningrad_ues_verification",
        pages=frozenset({PAGE_OES, PAGE_SUMMARY_TABLE, PAGE_OES_GAES_CHARGE}),
        aggregation_level="Проверка",
        cell_name="Проверка первой СЗ без НТ с ГАЭС (с Калининградом)",
        default_text=(
            "Проверка = Первая синхронная зона без НТ с зарядом ГАЭС "
            "(с ЭС Калининградской области) − "
            "сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
            "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области), без ОЭС Востока "
        ),
    ),
    _def(
        "ei_intensity",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Строка таблицы",
        cell_name="Электроемкость",
        default_text=(
            "Электроёмкость, кВт·ч/тыс. руб., по каждому году (не позже года "
            "с признаком «текущий» включительно) = Потребление ээ / Выпуск продукции × 1000 "
            "(потребление — млн кВт·ч, выпуск — млн руб.)."
        ),
    ),
    _def(
        "ei_graph_point",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Строка таблицы",
        cell_name="Характерные точки графика",
        default_text=(
            "Характерные точки графика по каждому году (не позже года с признаком «текущий» "
            "включительно) = LOG(Электроёмкость_Y / Электроёмкость_{Y−1}; "
            "Накопленные инвестиции_Y / Накопленные инвестиции_{Y−1}) "
            "(электроёмкость — кВт·ч/тыс. руб. из потребления и выпуска; "
            "накопленные инвестиции — млн руб.)."
        ),
    ),
    _def(
        "ei_calculated",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Строка таблицы",
        cell_name="Электроемкость (расчетная)",
        default_text=(
            "Электроёмкость (расчётная), кВт·ч/тыс. руб., по каждому году (не позже года "
            "с признаком «текущий» включительно) = коэффициент A × "
            "(Инвестиции в основной капитал)^коэффициент X "
            "(инвестиции — млн руб.)."
        ),
    ),
    _def(
        "ei_delta",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Строка таблицы",
        cell_name="Δ для электроемкости",
        default_text=(
            "Δ для электроёмкости по каждому году (не позже года с признаком «текущий» "
            "включительно) = Электроёмкость − Электроёмкость (расчётная), "
            "кВт·ч/тыс. руб."
        ),
    ),
    _def(
        "ei_coefficient_a",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Коэффициент",
        cell_name="Коэффициент A",
        default_text=(
            "Коэффициент A вводится вручную; используется для строки «Электроёмкость (расчётная)» "
            "и линии «Расчётная» на графике."
        ),
    ),
    _def(
        "ei_coefficient_a_computed",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Коэффициент",
        cell_name="Коэффициент Арасч.",
        default_text=(
            "«Арасч.» = EXP(СРЗНАЧ( LN(Yi) − X × LN(Ii) ) ), "
            "где Yi — фактическая электроёмкость, Ii — накопленные инвестиции по годам "
            "2010…N (N — год с признаком «текущий»), X — коэффициент X; "
            "LN и EXP — натуральный логарифм и экспонента (как в Excel); "
            "годы с неполными или неположительными Yi, Ii в среднее не входят — "
            "только подсказка, в расчёт строки не входит."
        ),
    ),
    _def(
        "ei_coefficient_x",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Коэффициент",
        cell_name="Коэффициент X",
        default_text=(
            "Коэффициент X = среднее арифметическое значений строки «Характерные точки графика» "
            "по годам 2010…N включительно (N — год с признаком «текущий»; "
            "пустые ячейки в среднее не входят)."
        ),
    ),
    _def(
        "ei_industrial_product_output",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Промышленное производство (ФО)",
        cell_name="Выпуск продукции",
        default_text=(
            "Выпуск продукции = Обрабатывающие производства + Добывающие производства + "
            "Производство и распределение электроэнергии, газа и воды "
            "(сумма строк «Выпуск продукции» по указанным ВЭД), млн руб."
        ),
    ),
    _def(
        "ei_industrial_consumption",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Промышленное производство (ФО)",
        cell_name="Потребление ээ",
        default_text=(
            "Потребление ээ = Обрабатывающие производства + Добывающие производства + "
            "Производство и распределение электроэнергии, газа и воды "
            "(сумма строк «Потребление ээ» по указанным ВЭД), млн кВт·ч."
        ),
    ),
    _def(
        "ei_industrial_accum_fixed_capital",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Промышленное производство (ФО)",
        cell_name="Накопленные инвестиции в основной капитал",
        default_text=(
            "Накопленные инвестиции в основной капитал = Обрабатывающие производства + "
            "Добывающие производства + Производство и распределение электроэнергии, "
            "газа и воды (сумма строк «Накопленные инвестиции в основной капитал» "
            "по указанным ВЭД), млн руб."
        ),
    ),
    _def(
        "ei_fd_total_vrp",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Всего (ФО)",
        cell_name="ВРП",
        default_text=(
            "ВРП = сумма строк «Выпуск продукции» по всем ВЭД федерального округа, млн руб."
        ),
    ),
    _def(
        "ei_fd_total_consumption",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Всего (ФО)",
        cell_name="Потребление ээ",
        default_text=(
            "Потребление ээ = Потребление ээ ВЭД + Потери в сетях + С.н. электростанций "
            "(сумма соответствующих строк блока «Всего»), млрд кВт·ч."
        ),
    ),
    _def(
        "ei_fd_total_ved_consumption",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Всего (ФО)",
        cell_name="Потребление ээ ВЭД",
        default_text=(
            "Потребление ээ ВЭД = сумма строк «Потребление ээ» по всем ВЭД федерального "
            "округа / 1000, млрд кВт·ч."
        ),
    ),
    _def(
        "ei_fd_total_network_losses",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Всего (ФО)",
        cell_name="Потери в сетях",
        default_text=(
            "Потери в сетях = значение строки «Потери в сетях» со страницы «Потребление ЭЭ по ВЭД» "
            "для соответствующего федерального округа / 1000, млрд кВт·ч."
        ),
    ),
    _def(
        "ei_fd_total_power_station",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Всего (ФО)",
        cell_name="С.н. электростанций",
        default_text=(
            "С.н. электростанций = значение строки «С.н. электростанций» со страницы "
            "«Потребление ЭЭ по ВЭД» для соответствующего федерального округа / 1000, "
            "млрд кВт·ч."
        ),
    ),
    _def(
        "ei_fd_total_accum_fixed_capital",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Всего (ФО)",
        cell_name="Накопленные инвестиции в основной капитал",
        default_text=(
            "Накопленные инвестиции в основной капитал = сумма строк "
            "«Накопленные инвестиции в основной капитал» по всем ВЭД федерального "
            "округа, млн руб."
        ),
    ),
    _def(
        "ei_pop_ref_population",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name=POP_REF_ROW_LABEL_BY_KIND[REF_ROW_POPULATION],
        default_text=EI_POP_REF_POPULATION_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_ref_household_consumption",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name=POP_REF_ROW_LABEL_BY_KIND[REF_ROW_HOUSEHOLD_CONSUMPTION],
        default_text=EI_POP_REF_HOUSEHOLD_CONSUMPTION_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_ref_accum_monetary_income",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name=POP_REF_ROW_LABEL_BY_KIND[REF_ROW_ACCUM_MONETARY_INCOME],
        default_text=EI_POP_REF_ACCUM_MONETARY_INCOME_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_per_capita",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name=POP_ROW_LABEL_BY_KIND[ROW_KIND_INTENSITY],
        default_text=EI_POP_PER_CAPITA_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_graph_point",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name=POP_ROW_LABEL_BY_KIND[ROW_KIND_GRAPH_POINT],
        default_text=EI_POP_GRAPH_POINT_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_calculated",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name=POP_ROW_LABEL_BY_KIND[ROW_KIND_CALCULATED],
        default_text=EI_POP_CALCULATED_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_delta",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name=POP_ROW_LABEL_BY_KIND[ROW_KIND_DELTA],
        default_text=EI_POP_DELTA_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_coefficient_a",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name="Коэффициент A",
        default_text=EI_POP_COEFFICIENT_A_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_coefficient_a_computed",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name="Коэффициент Арасч.",
        default_text=EI_POP_COEFFICIENT_A_COMPUTED_FORMULA_TOOLTIP,
    ),
    _def(
        "ei_pop_coefficient_x",
        pages=frozenset({PAGE_ELECTRICAL_INTENSITY}),
        aggregation_level="Население (ФО)",
        cell_name="Коэффициент X",
        default_text=EI_POP_COEFFICIENT_X_FORMULA_TOOLTIP,
    ),
)

_REGISTRY_BY_KEY: dict[str, EcSummaryFormulaDef] = {d.key: d for d in EC_SUMMARY_FORMULA_REGISTRY}


def get_formula_def(formula_key: str) -> EcSummaryFormulaDef | None:
    return _REGISTRY_BY_KEY.get(formula_key)


def iter_formula_defs(*, page: str | None = None) -> Iterable[EcSummaryFormulaDef]:
    for item in EC_SUMMARY_FORMULA_REGISTRY:
        if page is None or page in item.pages:
            yield item


def default_text_to_formula_key() -> dict[str, str]:
    out: dict[str, str] = {}
    for item in EC_SUMMARY_FORMULA_REGISTRY:
        out.setdefault(item.default_text, item.key)
    return out
