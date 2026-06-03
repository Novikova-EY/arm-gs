# -*- coding: utf-8 -*-
"""Справочник текстов формул (иконка «i») для сводок модуля «Нагрузки»."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

PAGE_OES = "oes"
PAGE_FO = "fo"
PAGE_EZ = "ez"
PAGE_COEFF_OES = "coeff_oes"
PAGE_COEFF_FO = "coeff_fo"
PAGE_COEFF_EZ = "coeff_ez"

ALL_MAX_PAGES = frozenset({PAGE_OES, PAGE_FO, PAGE_EZ})
ALL_COEFF_PAGES = frozenset({PAGE_COEFF_OES, PAGE_COEFF_FO, PAGE_COEFF_EZ})
ALL_SUMMARY_PAGES = ALL_MAX_PAGES | ALL_COEFF_PAGES

PAGE_LABELS: dict[str, str] = {
    PAGE_OES: "Максимумы по энергосистемам (/summary/oes/)",
    PAGE_FO: "Максимумы по федеральным округам (/summary/federal-districts/)",
    PAGE_EZ: "Максимумы по энергозонам (/summary/energy-zones/)",
    PAGE_COEFF_OES: "Коэффициенты по энергосистемам (/summary/coeff/oes/)",
    PAGE_COEFF_FO: "Коэффициенты по ФО (/summary/coeff/federal-districts/)",
    PAGE_COEFF_EZ: "Коэффициенты по энергозонам (/summary/coeff/energy-zones/)",
}


@dataclass(frozen=True)
class PdSummaryFormulaDef:
    key: str
    pages: frozenset[str]
    aggregation_level: str
    cell_name: str
    default_text: str

    def page_label_lines(self) -> tuple[str, ...]:
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
) -> PdSummaryFormulaDef:
    return PdSummaryFormulaDef(
        key=key,
        pages=pages or ALL_SUMMARY_PAGES,
        aggregation_level=aggregation_level,
        cell_name=cell_name,
        default_text=default_text.strip(),
    )


PD_SUMMARY_FORMULA_REGISTRY: tuple[PdSummaryFormulaDef, ...] = (
    _def(
        "coeff_res_oes_k",
        pages=ALL_COEFF_PAGES,
        aggregation_level="РЭС",
        cell_name="k (совмещённый на ОЭС)",
        default_text="k = Совмещенный на ОЭС / Максимальное потребление мощности",
    ),
    _def(
        "coeff_res_ees_k",
        pages=ALL_COEFF_PAGES,
        aggregation_level="РЭС",
        cell_name="k (совмещённый на ЕЭС)",
        default_text="k = Совмещенный на ЕЭС / Максимальное потребление мощности",
    ),
    _def(
        "oes_ues_calc_max_oes_mw",
        pages=frozenset({PAGE_OES, PAGE_COEFF_OES}),
        aggregation_level="ОЭС / РЭС",
        cell_name="Расчетный максимум ОЭС, МВт",
        default_text=(
            "Расчетный максимум ОЭС, МВт = сумма значений «Совмещенный на ОЭС, МВт» "
            "всех РЭС данной ОЭС"
        ),
    ),
    _def(
        "oes_ues_calc_combined_ees_mw",
        pages=frozenset({PAGE_OES, PAGE_COEFF_OES}),
        aggregation_level="ОЭС / РЭС",
        cell_name="Расчетный совмещенный на ЕЭС, МВт",
        default_text=(
            "Расчетный совмещенный на ЕЭС, МВт = сумма значений «Совмещенный на ЕЭС, МВт» "
            "всех РЭС данной ОЭС"
        ),
    ),
    _def(
        "oes_ees_russia_calc_max_via_oes",
        pages=frozenset({PAGE_OES, PAGE_EZ, PAGE_COEFF_OES, PAGE_COEFF_EZ}),
        aggregation_level="ЕЭС России",
        cell_name="Расчетный максимум ЕЭС (через ОЭС), МВт",
        default_text=(
            "Расчетный максимум ЕЭС (через ОЭС), МВт = сумма значений «Совмещенный на ЕЭС, МВт» "
            "по всем ОЭС"
        ),
    ),
    _def(
        "oes_ees_russia_calc_max_via_es",
        pages=frozenset({PAGE_OES, PAGE_COEFF_OES}),
        aggregation_level="ЕЭС России",
        cell_name="Расчетный максимум ЕЭС (через ЭС), МВт",
        default_text=(
            "Расчетный максимум ЕЭС (через ЭС), МВт = сумма значений «Совмещенный на ЕЭС, МВт» "
            "всех РЭС данной ОЭС"
        ),
    ),
    _def(
        "oes_ees_russia_calc_max",
        pages=frozenset({PAGE_OES, PAGE_EZ, PAGE_COEFF_OES, PAGE_COEFF_EZ}),
        aggregation_level="ЕЭС России",
        cell_name="Расчетный максимум ЕЭС России, МВт",
        default_text=(
            "Расчетный максимум ЕЭС России, МВт = сумма значений «Совмещенный на ЕЭС, МВт» "
            "всех энергозон"
        ),
    ),
    _def(
        "fo_calc_max_mw",
        pages=frozenset({PAGE_FO, PAGE_COEFF_FO}),
        aggregation_level="Федеральный округ",
        cell_name="Расчетный максимум ФО, МВт",
        default_text=(
            "Расчетный максимум ФО, МВт = сумма значений «Совмещенный на ФО, МВт» "
            "всех РЭС, входящих в данный ФО"
        ),
    ),
    _def(
        "fo_calc_combined_on_cz_mw",
        pages=frozenset({PAGE_FO, PAGE_COEFF_FO}),
        aggregation_level="Федеральный округ",
        cell_name="Расчетный совмещенный на ЦЗ России, МВт",
        default_text=(
            "Расчетный совмещенный на ЦЗ России, МВт = сумма значений «Совмещенный на ЦЗ России, МВт» "
            "всех РЭС, входящих в данный ФО"
        ),
    ),
    _def(
        "ez_calc_max_mw",
        pages=frozenset({PAGE_EZ, PAGE_COEFF_EZ}),
        aggregation_level="Энергозона",
        cell_name="Расчетный максимум энергозоны, МВт",
        default_text=(
            "Расчетный максимум энергозоны, МВт = сумма значений «Совмещенный на энергозону, МВт» "
            "всех РЭС, входящих в данную энергозону"
        ),
    ),
    _def(
        "sa_calc_max_mw",
        pages=frozenset({PAGE_OES, PAGE_EZ, PAGE_COEFF_OES, PAGE_COEFF_EZ}),
        aggregation_level="Синхронная зона",
        cell_name="Расчетный максимум синхронной зоны, МВт",
        default_text=(
            "Расчетный максимум синхронной зоны, МВт = сумма значений «Совмещенный на ЕЭС, МВт» "
            "всех РЭС, входящих в данную синхронную зону"
        ),
    ),
    _def(
        "sa_verify_combined_ees",
        pages=frozenset({PAGE_OES}),
        aggregation_level="Синхронная зона",
        cell_name="Проверка для совмещенного максимума на ЕЭС, МВт",
        default_text=(
            "Проверка для совмещенного максимума на ЕЭС, МВт = Расчетный максимум синхронной зоны, МВт "
            "− Максимальное потребление мощности, МВт"
        ),
    ),
    _def(
        "coeff_k_ues_calc_max_oes",
        pages=frozenset({PAGE_COEFF_OES}),
        aggregation_level="ОЭС",
        cell_name="k (расчётный максимум ОЭС)",
        default_text="k = Расчетный максимум ОЭС / Максимальное потребление мощности ОЭС",
    ),
    _def(
        "coeff_k_ues_combined_ees",
        pages=frozenset({PAGE_COEFF_OES}),
        aggregation_level="ОЭС",
        cell_name="k (совмещённый на ЕЭС)",
        default_text="k = Совмещенный на ЕЭС / Максимальное потребление мощности ОЭС",
    ),
    _def(
        "coeff_k_ues_calc_combined_ees",
        pages=frozenset({PAGE_COEFF_OES}),
        aggregation_level="ОЭС",
        cell_name="k (расчётный совмещённый на ЕЭС)",
        default_text="k = Расчетный совмещенный на ЕЭС / Максимальное потребление мощности ОЭС",
    ),
    _def(
        "coeff_k_calculated_max_ees_via_oes",
        pages=frozenset({PAGE_COEFF_OES, PAGE_COEFF_EZ}),
        aggregation_level="Показатель",
        cell_name="k (расчётный максимум ЕЭС через ОЭС)",
        default_text="k = Расчетный максимум ЕЭС (через ОЭС) / Максимальное потребление мощности",
    ),
    _def(
        "coeff_k_calculated_max_ees_via_es",
        pages=frozenset({PAGE_COEFF_OES}),
        aggregation_level="Показатель",
        cell_name="k (расчётный максимум ЕЭС через ЭС)",
        default_text="k = Расчетный максимум ЕЭС (через ЭС) / Максимальное потребление мощности",
    ),
    _def(
        "coeff_k_formula_default_suffix",
        pages=ALL_COEFF_PAGES,
        aggregation_level="Показатель (динамический k)",
        cell_name="Суффикс формулы k",
        default_text=" / Максимальное потребление мощности, МВт",
    ),
    _def(
        "coeff_f_gs10",
        pages=ALL_COEFF_PAGES,
        aggregation_level="Столбец «Расчётный коэффициент совмещения»",
        cell_name="для ГС (10 лет)",
        default_text=(
            "Среднее арифметическое коэффициентов k по годам отчётного периода "
            "(10 лет: N−9…N, N — базовый год)"
        ),
    ),
    _def(
        "coeff_f_gs10trim",
        pages=ALL_COEFF_PAGES,
        aggregation_level="Столбец «Расчётный коэффициент совмещения»",
        cell_name="для ГС (10 лет без min и max)",
        default_text=(
            "По годам отчётного периода (N−9…N): из значений k исключаются одно минимальное "
            "и одно максимальное, для остальных вычисляется среднее"
        ),
    ),
    _def(
        "coeff_f_gs5",
        pages=ALL_COEFF_PAGES,
        aggregation_level="Столбец «Расчётный коэффициент совмещения»",
        cell_name="для СиПР (5 лет)",
        default_text=(
            "Среднее арифметическое коэффициентов k по пяти годам N−4…N "
            "(N — базовый год отчётного периода)"
        ),
    ),
    _def(
        "coeff_f_sample",
        pages=ALL_COEFF_PAGES,
        aggregation_level="Столбец «Расчётный коэффициент совмещения»",
        cell_name="Выборка",
        default_text=(
            "Среднее арифметическое коэффициентов k по годам, отмеченным в выпадающем списке "
            "выборки (чекбоксы)"
        ),
    ),
    _def(
        "fo_cz_calc_max",
        pages=frozenset({PAGE_FO, PAGE_COEFF_FO}),
        aggregation_level="ЦЗ России",
        cell_name="Расчетный максимум ЦЗ России, МВт",
        default_text=(
            "Расчетный максимум ЦЗ России, МВт = "
            "Σ(«Совмещенный ФО на ЦЗ России, МВт») по всем федеральным округам."
        ),
    ),
    _def(
        "fo_coeff_cz_total_sum_fo_max",
        pages=frozenset({PAGE_COEFF_FO}),
        aggregation_level="ЦЗ России",
        cell_name="Сумма максимумов потребления ФО, МВт",
        default_text=(
            "Сумма значений «Максимальное потребление мощности, МВт» по строкам федеральных округов "
            "и по строкам региональных энергосистем, отображаемым в таблице (без строки «ЦЗ России»). "
            "Учитываются максимумы и на уровне ФО, и на уровне РЭС под округами."
        ),
    ),
    _def(
        "fo_coeff_cz_total_sum_res_combined_cz",
        pages=frozenset({PAGE_COEFF_FO}),
        aggregation_level="ЦЗ России",
        cell_name="Сумма совмещенных на ЦЗ России максимумов РЭС, МВт",
        default_text=(
            "Сумма значений «Совмещенный на ЦЗ России, МВт» по всем строкам региональных энергосистем, "
            "показанным в таблице под соответствующими федеральными округами."
        ),
    ),
    _def(
        "fo_coeff_cz_total_imbalance",
        pages=frozenset({PAGE_COEFF_FO}),
        aggregation_level="ЦЗ России",
        cell_name="Небаланс, МВт",
        default_text=(
            "Разность между «Максимальное потребление мощности, МВт» для сущности «ЦЗ России» "
            "и суммой совмещённых на ЦЗ России максимумов региональных энергосистем "
            "(предыдущая строка блока)."
        ),
    ),
)

_REGISTRY_BY_KEY: dict[str, PdSummaryFormulaDef] = {d.key: d for d in PD_SUMMARY_FORMULA_REGISTRY}


def get_formula_def(formula_key: str) -> PdSummaryFormulaDef | None:
    return _REGISTRY_BY_KEY.get(formula_key)


def iter_formula_defs(*, page: str | None = None) -> Iterable[PdSummaryFormulaDef]:
    for item in PD_SUMMARY_FORMULA_REGISTRY:
        if page is None or page in item.pages:
            yield item


def default_text_to_formula_key() -> dict[str, str]:
    out: dict[str, str] = {}
    for item in PD_SUMMARY_FORMULA_REGISTRY:
        out.setdefault(item.default_text, item.key)
    return out
