# -*- coding: utf-8 -*-
"""Справочник текстов формул (иконка «i») расчёта по действующим ТЭС."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

PAGE_TOPLIVO = "toplivo"
PAGE_SPR = "spravochnik"
PAGE_CHARS = "khar-topl"
PAGE_COEFF = "koeff"
PAGE_ZOLA = "zola"
PAGE_SERA = "sera"
PAGE_AZOT = "azot"
PAGE_CO = "co"
PAGE_PG = "pg"
PAGE_PG_TJ = "pg-tj"
PAGE_OBEMY = "obemy"
PAGE_ANALYSIS_PG_BEZ_KOT = "analysis-pg-bez-kot"
PAGE_ANALYSIS_PG_VSE = "analysis-pg-vse"
PAGE_ANALYSIS_ZV_BEZ_KOT = "analysis-zv-bez-kot"
PAGE_ANALYSIS_ZV_VSE = "analysis-zv-vse"
PAGE_GIS_TEK_ZV = "gis-tek-zv"

ALL_CALC_PAGES = frozenset(
    {
        PAGE_TOPLIVO,
        PAGE_CHARS,
        PAGE_COEFF,
        PAGE_ZOLA,
        PAGE_SERA,
        PAGE_AZOT,
        PAGE_CO,
        PAGE_PG,
        PAGE_PG_TJ,
        PAGE_OBEMY,
    }
)
EMISSION_PAGES = frozenset(
    {PAGE_ZOLA, PAGE_SERA, PAGE_AZOT, PAGE_CO, PAGE_PG, PAGE_PG_TJ}
)
VOLUME_PAGES = frozenset({PAGE_OBEMY})

PAGE_LABELS: dict[str, str] = {
    PAGE_TOPLIVO: "Данные по модулю Топливо (/ecology/operating_tes/vsego/toplivo/)",
    PAGE_CHARS: "Характеристики (/ecology/operating_tes/vsego/khar-topl/)",
    PAGE_COEFF: "Коэффициенты (/ecology/operating_tes/vsego/koeff/)",
    PAGE_ZOLA: "Зола (/ecology/operating_tes/vsego/zola/)",
    PAGE_SERA: "Сера (/ecology/operating_tes/vsego/sera/)",
    PAGE_AZOT: "Азот (/ecology/operating_tes/vsego/azot/)",
    PAGE_CO: "CO (/ecology/operating_tes/vsego/co/)",
    PAGE_PG: "ПГ (/ecology/operating_tes/vsego/pg/)",
    PAGE_PG_TJ: "ПГ через ТДж (/ecology/operating_tes/vsego/pg-tj/)",
    PAGE_OBEMY: "Объемы (/ecology/operating_tes/vsego/obemy/)",
    PAGE_ANALYSIS_PG_BEZ_KOT: (
        "Парниковые газы (без котельных) (/ecology/analysis/pg-bez-kot/)"
    ),
    PAGE_ANALYSIS_PG_VSE: "Парниковые газы (с котельными) (/ecology/analysis/pg-vse/)",
    PAGE_ANALYSIS_ZV_BEZ_KOT: (
        "Загрязняющие вещества (без котельных) (/ecology/analysis/zv-bez-kot/)"
    ),
    PAGE_ANALYSIS_ZV_VSE: (
        "Загрязняющие вещества (с котельными) (/ecology/analysis/zv-vse/)"
    ),
    PAGE_GIS_TEK_ZV: (
        "Загрязняющие вещества (ЗВ) - отчетные данные (/ecology/gis_tek/pollutants/)"
    ),
}

NEW_TES_PAGE_LABELS: dict[str, str] = {
    key: text.replace("/ecology/operating_tes/", "/ecology/new_tes/")
    for key, text in PAGE_LABELS.items()
    if key in ALL_CALC_PAGES
}
NEW_TES_PAGE_LABELS[PAGE_SPR] = (
    "Нормативы (/ecology/new_tes/vsego/spravochnik/)"
)

# Ключ формулы заголовка страницы (иконка «i» рядом с h2) по slug листа.
SHEET_FORMULA_KEYS: dict[str, str] = {
    "zola": "sheet_zola",
    "sera": "sheet_sera",
    "azot": "sheet_azot",
    "co": "sheet_co",
    "pg": "sheet_pg",
    "pg-tj": "sheet_pg_tj",
    "obemy": "sheet_obemy",
}

NEW_TES_CALC_PAGES = frozenset(
    {
        PAGE_TOPLIVO,
        PAGE_SPR,
        PAGE_ZOLA,
        PAGE_SERA,
        PAGE_AZOT,
        PAGE_CO,
        PAGE_PG,
        PAGE_OBEMY,
    }
)

NT_SHEET_FORMULA_KEYS: dict[str, str] = {
    "spravochnik": "nt_ash_range",
    "zola": "nt_zv_thous",
    "sera": "nt_zv_thous",
    "azot": "nt_zv_thous",
    "co": "nt_zv_tonnes",
    "pg": "nt_pg_mass",
    "obemy": "nt_volume",
}


@dataclass(frozen=True)
class OperatingTesFormulaDef:
    key: str
    pages: frozenset[str]
    aggregation_level: str
    cell_name: str
    default_text: str

    def page_label_lines(self) -> tuple[str, ...]:
        if self.pages == ALL_CALC_PAGES:
            return (
                "Все листы расчёта по действующим ТЭС",
                "Все листы расчёта по новым ТЭС",
            )
        if self.key.startswith("nt_"):
            return tuple(
                NEW_TES_PAGE_LABELS[p]
                for p in sorted(self.pages)
                if p in NEW_TES_PAGE_LABELS
            )
        return tuple(
            PAGE_LABELS[p] if p in PAGE_LABELS else NEW_TES_PAGE_LABELS[p]
            for p in sorted(self.pages)
        )

    def page_labels(self) -> str:
        return "\n".join(self.page_label_lines())


def _def(
    key: str,
    *,
    pages: frozenset[str],
    aggregation_level: str,
    cell_name: str,
    default_text: str,
) -> OperatingTesFormulaDef:
    return OperatingTesFormulaDef(
        key=key,
        pages=pages,
        aggregation_level=aggregation_level,
        cell_name=cell_name,
        default_text=default_text.strip(),
    )


_SUM_MOTKH_TEXT = (
    "ΣМотх = Мотх(Газ) + Мотх(Газ искусственный) + Мотх(Нефтетопливо) "
    "+ Мотх(Торф) + Мотх(Уголь) + Мотх(Прочее топливо). "
    "Сумма рассчитывается отдельно для каждого столбца за выбранный год. "
    "Вложенные виды топлива уже входят в итоги своих групп и повторно не суммируются."
)
_CAPTURE_SCOPE_TEXT = (
    " берется со вкладки «Коэффициенты» за выбранный год: "
    "для «Всего» – территория «Всего», принадлежность «Все»; "
    "для «Станции отрасли» и «Промпредприятия» – территория «Всего» "
    "и соответствующая принадлежность; для ОЭС, ТИТЭС и децентрализованной зоны "
    "– соответствующая территория, принадлежность «Все». "
    "Значение используется как доля единицы."
)


OPERATING_TES_FORMULA_REGISTRY: tuple[OperatingTesFormulaDef, ...] = (
    _def(
        "to_natural",
        pages=EMISSION_PAGES,
        aggregation_level="Столбец",
        cell_name="Перевод в натур. (BH)",
        default_text="BH = В / (т у.т./тн)",
    ),
    _def(
        "ash_to_natural",
        pages=frozenset({PAGE_ZOLA, PAGE_SERA, PAGE_CO}),
        aggregation_level="Столбец",
        cell_name="Перевод в натур. (BH, зола, сера и CO)",
        default_text=(
            "BH = Топливо · 7000 / Qн. "
            "Топливо – акцептованное значение для данного вида/типа топлива "
            "со вкладки «Данные по модулю Топливо» за выбранный год и территорию; "
            "Qн – низшая теплота сгорания в ккал/кг со вкладки «Характеристики»."
        ),
    ),
    _def(
        "capture",
        pages=VOLUME_PAGES,
        aggregation_level="Лист",
        cell_name="Улавливание (Мвыб)",
        default_text="Мвыб = Мотх · (1 − η)",
    ),
    _def(
        "sheet_zola",
        pages=frozenset({PAGE_ZOLA}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text="Расчетная формула: Мотх = 0,01 · BH · (аун · Aр + qч · Qн / 32680)",
    ),
    _def(
        "ash_motkh",
        pages=frozenset({PAGE_ZOLA, PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="Мотх золы, тыс. т",
        default_text="Мотх = 0,01 · BH · (аун · Aр + qч · Qн / 32680)",
    ),
    _def(
        "ash_motkh_total",
        pages=frozenset({PAGE_ZOLA}),
        aggregation_level="Итог",
        cell_name="ΣМотх золы",
        default_text=_SUM_MOTKH_TEXT,
    ),
    _def(
        "ash_eta",
        pages=frozenset({PAGE_ZOLA}),
        aggregation_level="Итог",
        cell_name="КПД золоулавливания",
        default_text="КПД золоулавливания" + _CAPTURE_SCOPE_TEXT,
    ),
    _def(
        "ash_emitted",
        pages=frozenset({PAGE_ZOLA}),
        aggregation_level="Итог",
        cell_name="Мвыб золы",
        default_text="Мвыб = ΣМотх · (1 − КПД золоулавливания). Расчет отдельно для каждого столбца.",
    ),
    _def(
        "sheet_sera",
        pages=frozenset({PAGE_SERA}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text="Расчетная формула: Мотх = 0,02 · BH · Sp · (1 − x)",
    ),
    _def(
        "so2_motkh",
        pages=frozenset({PAGE_SERA, PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="Мотх SO2, тыс. т",
        default_text=(
            "Мотх = 0,02 · BH · Sp · (1 − x). "
            "Sp – сернистость топлива, %; x – доля окислов серы, связываемых золой топлива. "
            "Оба значения берутся со вкладки «Характеристики» за выбранный год."
        ),
    ),
    _def(
        "so2_motkh_total",
        pages=frozenset({PAGE_SERA}),
        aggregation_level="Итог",
        cell_name="ΣМотх серы",
        default_text=_SUM_MOTKH_TEXT,
    ),
    _def(
        "sulfur_eta",
        pages=frozenset({PAGE_SERA}),
        aggregation_level="Итог",
        cell_name="КПД сероочистки",
        default_text="КПД сероочистки" + _CAPTURE_SCOPE_TEXT,
    ),
    _def(
        "so2_emitted",
        pages=frozenset({PAGE_SERA}),
        aggregation_level="Итог",
        cell_name="Мвыб серы",
        default_text="Мвыб = ΣМотх · (1 − КПД сероочистки). Расчет отдельно для каждого столбца.",
    ),
    _def(
        "sheet_azot",
        pages=frozenset({PAGE_AZOT}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text="Расчетная формула: МотхNOx = 0,001 · B · (1 − qч / 100) · bj",
    ),
    _def(
        "nox_motkh",
        pages=frozenset({PAGE_AZOT}),
        aggregation_level="Показатель",
        cell_name="Мотх NOx без n, тыс. т",
        default_text=(
            "МотхNOx = 0,001 · B · (1 − qч / 100) · bj. "
            "B – акцептованный расход условного топлива со вкладки «Данные по модулю Топливо» "
            "за выбранный год и территорию, без перевода в натур. "
            "qч – потери теплоты от механической неполноты сгорания, %; "
            "bj – коэффициент для данного топлива со вкладки «Характеристики». "
            "Коэффициент n применяется один раз к сумме Мотх при расчете Мвыб."
        ),
    ),
    _def(
        "nox_motkh_total",
        pages=frozenset({PAGE_AZOT}),
        aggregation_level="Итог",
        cell_name="ΣМотх NOx",
        default_text=_SUM_MOTKH_TEXT,
    ),
    _def(
        "nox_n",
        pages=frozenset({PAGE_AZOT}),
        aggregation_level="Итог",
        cell_name="Коэффициент подавления оксидов азота в топке n",
        default_text="Коэффициент подавления оксидов азота в топке n" + _CAPTURE_SCOPE_TEXT,
    ),
    _def(
        "nox_emitted",
        pages=frozenset({PAGE_AZOT}),
        aggregation_level="Итог",
        cell_name="Мвыб NOx",
        default_text=(
            "Мвыб = ΣМотх · (1 − n). Коэффициент n применяется один раз после суммирования "
            "Мотх всех групп топлива, отдельно для каждого столбца."
        ),
    ),
    _def(
        "nox_capture",
        pages=frozenset({PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="Мвыб NOx, тыс. т",
        default_text="Мвыб = ΣМотх · (1 − n)",
    ),
    _def(
        "sheet_co",
        pages=frozenset({PAGE_CO}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text="Расчетная формула: МотхCO = 0,001 · BH · (q3 · R · Qн / 1013) · (1 − q4 / 100)",
    ),
    _def(
        "co_motkh",
        pages=frozenset({PAGE_CO, PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="Мотх CO, т",
        default_text=(
            "МотхCO = 0,001 · BH · (q3 · R · Qн / 1013) · (1 − q4 / 100). "
            "q3 – потери теплоты от химической неполноты сгорания, %; "
            "q4 – потери теплоты от механической неполноты сгорания, %; "
            "R – коэффициент химической неполноты сгорания; Qн – низшая теплота сгорания в кДж/кг. "
            "Характеристики топлива берутся со вкладки «Характеристики» за выбранный год."
        ),
    ),
    _def(
        "co_motkh_total",
        pages=frozenset({PAGE_CO}),
        aggregation_level="Итог",
        cell_name="ΣМотх CO",
        default_text=_SUM_MOTKH_TEXT,
    ),
    _def(
        "co_k",
        pages=frozenset({PAGE_CO}),
        aggregation_level="Итог",
        cell_name="Коэф. подавления CO",
        default_text="Коэф. подавления CO" + _CAPTURE_SCOPE_TEXT,
    ),
    _def(
        "co_emitted",
        pages=frozenset({PAGE_CO}),
        aggregation_level="Итог",
        cell_name="Мвыб CO",
        default_text="Мвыб = ΣМотх · (1 − Коэф. подавления CO). Расчет отдельно для каждого столбца.",
    ),
    _def(
        "sheet_pg",
        pages=frozenset({PAGE_PG}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text="Расчетная формула: МотхCO2 = B · KCO2",
    ),
    _def(
        "pg_motkh",
        pages=frozenset({PAGE_PG, PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="Мотх CO2, тыс. т",
        default_text=(
            "МотхCO2 = B · KCO2. B – акцептованный расход условного топлива со вкладки "
            "«Данные по модулю Топливо» за выбранный год и территорию, без перевода в натур. "
            "KCO2 – коэффициент выбросов CO2 для данного вида/типа топлива со вкладки "
            "«Характеристики» за выбранный год."
        ),
    ),
    _def(
        "pg_motkh_total",
        pages=frozenset({PAGE_PG}),
        aggregation_level="Итог",
        cell_name="ΣМотх ПГ",
        default_text=_SUM_MOTKH_TEXT,
    ),
    _def(
        "pg_k",
        pages=frozenset({PAGE_PG, PAGE_PG_TJ}),
        aggregation_level="Итог",
        cell_name="Коэффициент подавления ПГ (оксидов углерода)",
        default_text="Коэффициент подавления ПГ (оксидов углерода)" + _CAPTURE_SCOPE_TEXT,
    ),
    _def(
        "pg_emitted",
        pages=frozenset({PAGE_PG}),
        aggregation_level="Итог",
        cell_name="Мвыб ПГ",
        default_text=(
            "Мвыб = ΣМотх · (1 − Коэффициент подавления ПГ). "
            "Коэффициент применяется один раз после суммирования Мотх всех групп топлива, "
            "отдельно для каждого столбца."
        ),
    ),
    _def(
        "sheet_pg_tj",
        pages=frozenset({PAGE_PG_TJ}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text="Расчетная формула: МотхCO2 = МДж · KCO2 / 1000",
    ),
    _def(
        "pg_tj_energy",
        pages=frozenset({PAGE_PG_TJ}),
        aggregation_level="Столбец",
        cell_name="МДж (энергия, ТДж)",
        default_text=(
            "МДж = B / (тут/тн) · (ТДж/тыс. т натур.). "
            "B – акцептованный расход условного топлива со вкладки «Данные по модулю Топливо» "
            "за выбранный год и территорию. Оба коэффициента берутся из группы "
            "«Коэффициенты для расчета как в НД о Кадастре ПГ» во вкладке «Характеристики» "
            "для данного топлива и года. Энергия выражена в ТДж; «МДж» – название столбца."
        ),
    ),
    _def(
        "pg_tj_mass",
        pages=frozenset({PAGE_PG_TJ}),
        aggregation_level="Столбец",
        cell_name="Мотх CO2",
        default_text=(
            "МотхCO2 = МДж · KCO2 / 1000. МДж – энергия из соседнего столбца. "
            "KCO2 – коэффициент «т CO2/ТДж» из группы «Коэффициенты для расчета как в НД "
            "о Кадастре ПГ» во вкладке «Характеристики» для данного топлива и года, "
            "а не национальный коэффициент эмиссии. Деление на 1000 выполняется один раз; "
            "результат выражен в тыс. т."
        ),
    ),
    _def(
        "pg_tj_motkh_total",
        pages=frozenset({PAGE_PG_TJ}),
        aggregation_level="Итог",
        cell_name="ΣМотх ПГ через ТДж",
        default_text=_SUM_MOTKH_TEXT,
    ),
    _def(
        "pg_tj_emitted",
        pages=frozenset({PAGE_PG_TJ}),
        aggregation_level="Итог",
        cell_name="Мвыб ПГ через ТДж",
        default_text=(
            "Мвыб = ΣМотх · (1 − Коэффициент подавления ПГ). "
            "Коэффициент применяется один раз после суммирования Мотх всех групп топлива, "
            "отдельно для каждого столбца."
        ),
    ),
    _def(
        "sheet_obemy",
        pages=frozenset({PAGE_OBEMY}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text="Мвыб = Мотх · (1 − КПД); для NOx: ΣМотх · (1 − n)",
    ),
    _def(
        "d_mazut",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Разность по израсходованному мазуту, т у.т.",
        default_text="d_mazut = MAZUT_6tp − MAZUT_ek",
    ),
    _def(
        "d_gaz",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Разность по израсходованному газу, т у.т.",
        default_text="d_gaz = GAZ_ESTEST − GAZ_ek",
    ),
    _def(
        "d_tv",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Разность по израсходованному твердому топливу, т у.т.",
        default_text="d_tv = TvTopl_6tp − TvTopl_ek",
    ),
    _def(
        "K_gaz_ek",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Коэффициент эмиссии (газ)",
        default_text=(
            "K_gaz_ek = Выбросы СО2 от сжигания газа, т / Расход газа, т у.т. "
            "(CO2_gaz / GAZ_ek)"
        ),
    ),
    _def(
        "K_mazut_ek",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Коэффициент эмиссии (мазут)",
        default_text=(
            "K_mazut_ek = Выбросы СО2 от сжигания мазута, т / Расход мазута, т у.т. "
            "(CO2_mazut / MAZUT_ek)"
        ),
    ),
    _def(
        "K_ugol_ek",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Коэффициент эмиссии (твердое)",
        default_text=(
            "K_ugol_ek = Выбросы СО2 от сжигания твердого топлива, т / Расход твердого топлива, т у.т. "
            "(CO2_ugol / TvTopl_ek)"
        ),
    ),
    _def(
        "CO2",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Выброшено ПГ всего, т",
        default_text=(
            "Выброшено ПГ всего, т = Выбросы СО2 от сжигания газа, т "
            "+ Выбросы СО2 от сжигания мазута, т "
            "+ Выбросы СО2 от сжигания твердого топлива, т "
            "(CO2 = CO2_gaz + CO2_mazut + CO2_ugol)"
        ),
    ),
    _def(
        "UD_CO2_ek",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Удельные выбросы ПГ на единицу топлива, кг/т у.т.",
        default_text=(
            "UD_CO2_ek = Выброшено ПГ всего, т · 1000 "
            "/ (Расход газа + мазута + твердого топлива, т у.т.) "
            "(CO2 · 1000 / (GAZ_ek + MAZUT_ek + TvTopl_ek))"
        ),
    ),
    _def(
        "UD_CO2_ener",
        pages=frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE}),
        aggregation_level="Столбец",
        cell_name="Удельные выбросы ПГ на единицу энергии, г/кВт.ч",
        default_text=(
            "UD_CO2_ener = Выброшено ПГ всего, т "
            "/ (выработка электроэнергии, млн кВт·ч + отпуск тепла, тыс. Гкал / 859,8 · 1000) "
            "(CO2 / (W_en + Teplo / 859,8 · 1000)); "
            "859,8 ккал/кВт·ч – перевод тепла в электроэнергию"
        ),
    ),
    _def(
        "gaseous_and_liquid",
        pages=frozenset(
            {PAGE_GIS_TEK_ZV, PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}
        ),
        aggregation_level="Столбец",
        cell_name="Газообразные и жидкие вещества, всего",
        default_text=(
            "всего = диоксид серы "
            "+ оксид углерода [CO] "
            "+ оксиды азота [в пересчете на NO2] "
            "+ углеводороды [без летучих органических соединений] "
            "+ летучие органические соединения [ЛОС] "
            "+ прочие газообразные и жидкие"
        ),
    ),
    _def(
        "zv_total",
        pages=frozenset(
            {PAGE_GIS_TEK_ZV, PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}
        ),
        aggregation_level="Столбец",
        cell_name="всего",
        default_text=(
            "всего = Твердые вещества + Газообразные и жидкие вещества (всего)"
        ),
    ),
    _def(
        "zv_brought_energy",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="Приведенная энергия, млн. кВт.ч",
        default_text=(
            "Приведенная энергия = выработка электроэнергии, млн кВт·ч "
            "+ отпуск тепла, тыс. Гкал / 859,8 · 1000 "
            "(W_en + Teplo / 859,8 · 1000); "
            "859,8 ккал/кВт·ч – перевод тепла в электроэнергию"
        ),
    ),
    _def(
        "zv_normir",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="Итого ЗВ по нормируемым ингредиентам",
        default_text=(
            "Итого нормируемых ЗВ, т = твердые вещества + диоксид серы "
            "+ оксиды азота (TVERD_V + SO2_gaz + NOx_gaz)"
        ),
    ),
    _def(
        "zv_udel_na_energ",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="на приведенную (с учетом перевода отпуска тепла)",
        default_text=(
            "г/кВт·ч = всего выброшено ЗВ за год, т / приведенная энергия, млн кВт·ч "
            "(VIBROS_ekol / (W_en + Teplo / 859,8 · 1000))"
        ),
    ),
    _def(
        "zv_normir_na_ee",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="на выработку электроэнергии",
        default_text=(
            "г/кВт·ч = нормируемых ЗВ за год, т / выработка электроэнергии, млн кВт·ч "
            "((TVERD_V + SO2_gaz + NOx_gaz) / W_en)"
        ),
    ),
    _def(
        "zv_normir_na_energ",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="нормируемые ЗВ на приведенную (с учетом перевода отпуска тепла)",
        default_text=(
            "г/кВт·ч = нормируемых ЗВ за год, т / приведенная энергия, млн кВт·ч "
            "((TVERD_V + SO2_gaz + NOx_gaz) / (W_en + Teplo / 859,8 · 1000))"
        ),
    ),
    _def(
        "zv_normir_tverd_na_energ",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="твердое топливо",
        default_text=(
            "г/кВт·ч = твердые вещества, т / приведенная энергия, млн кВт·ч "
            "(TVERD_V / (W_en + Teplo / 859,8 · 1000))"
        ),
    ),
    _def(
        "zv_normir_so2_na_energ",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="сера",
        default_text=(
            "г/кВт·ч = диоксид серы, т / приведенная энергия, млн кВт·ч "
            "(SO2_gaz / (W_en + Teplo / 859,8 · 1000))"
        ),
    ),
    _def(
        "zv_normir_nox_na_energ",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="азот",
        default_text=(
            "г/кВт·ч = оксиды азота, т / приведенная энергия, млн кВт·ч "
            "(NOx_gaz / (W_en + Teplo / 859,8 · 1000))"
        ),
    ),
    _def(
        "zv_udel_tv",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="твердое топливо",
        default_text=(
            "кг/т у.т. = твердые вещества, т · 1000 / (мазут + уголь, т у.т.) "
            "(TVERD_V · 1000 / (MAZUT_6tp + TVERD_TOPL_6tp))"
        ),
    ),
    _def(
        "zv_udel_so2",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="сера",
        default_text=(
            "кг/т у.т. = диоксид серы, т · 1000 / (мазут + уголь, т у.т.) "
            "(SO2_gaz · 1000 / (MAZUT_6tp + TVERD_TOPL_6tp))"
        ),
    ),
    _def(
        "zv_udel_nox",
        pages=frozenset({PAGE_ANALYSIS_ZV_VSE, PAGE_ANALYSIS_ZV_BEZ_KOT}),
        aggregation_level="Столбец",
        cell_name="азот",
        default_text=(
            "кг/т у.т. = оксиды азота, т · 1000 / (газ + мазут + уголь, т у.т.) "
            "(NOx_gaz · 1000 / (GAZ_6tp + MAZUT_6tp + TVERD_TOPL_6tp))"
        ),
    ),
    _def(
        "nt_fuel_b",
        pages=frozenset({PAGE_ZOLA, PAGE_SERA, PAGE_AZOT, PAGE_CO, PAGE_PG}),
        aggregation_level="Столбец",
        cell_name="В, тыс. т у.т.",
        default_text="В – расход топлива новых ТЭС (d ≠ 1), тыс. т у.т.",
    ),
    _def(
        "nt_zv_tonnes",
        pages=frozenset({PAGE_ZOLA, PAGE_SERA, PAGE_AZOT, PAGE_CO, PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="М ЗВ, т",
        default_text="М, т = В, тыс. т у.т. × У, кг/т у.т.; У – норматив листа «Нормативы» (до 100 МВт / более 100 МВт по Nуст)",
    ),
    _def(
        "nt_zv_thous",
        pages=frozenset({PAGE_ZOLA, PAGE_SERA, PAGE_AZOT, PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="М ЗВ, тыс. т",
        default_text="М, тыс. т = (В, тыс. т у.т. × У, кг/т у.т.) / 1000",
    ),
    _def(
        "nt_pg_mass",
        pages=frozenset({PAGE_PG, PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="М CO2, тыс. т",
        default_text="М CO2, тыс. т = В, тыс. т у.т. × У, т/т у.т.",
    ),
    _def(
        "nt_zv_sum",
        pages=frozenset({PAGE_OBEMY}),
        aggregation_level="Показатель",
        cell_name="ВСЕГО ЗВ",
        default_text="ВСЕГО ЗВ = зола + SO2 + NOx + CO (CO в т, остальные в тыс. т на листе «Объемы»)",
    ),
    _def(
        "nt_volume",
        pages=frozenset({PAGE_OBEMY}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text=(
            "Новые ТЭС: сумма классов до 100 МВт и более 100 МВт. "
            "М ЗВ, т = В × У (кг/т у.т.); на «Объемах» тыс. т = М / 1000 (кроме CO, т). "
            "М CO2, тыс. т = В × У (т/т у.т.)"
        ),
    ),
    _def(
        "nt_ash_range",
        pages=frozenset({PAGE_SPR}),
        aggregation_level="Лист",
        cell_name="Заголовок страницы",
        default_text=(
            "Массовый выброс золы для агрегатов до 100 МВт – в диапазоне 1,76–2,93, "
            "более 100 МВт – 0,59–1,76 в зависимости от приведенного содержания золы. "
            "Для каменных углей массовый выброс оксидов азота выше, чем у бурых; "
            "для 2020 года сера не более 5 кг/т у.т. – не учитывали"
        ),
    ),
)

_BY_KEY = {item.key: item for item in OPERATING_TES_FORMULA_REGISTRY}


def get_formula_def(key: str) -> OperatingTesFormulaDef | None:
    return _BY_KEY.get(str(key or "").strip())


def iter_formula_defs(*, page: str | None = None) -> Iterable[OperatingTesFormulaDef]:
    wanted = str(page or "").strip()
    for item in OPERATING_TES_FORMULA_REGISTRY:
        if wanted and wanted not in item.pages:
            continue
        yield item
