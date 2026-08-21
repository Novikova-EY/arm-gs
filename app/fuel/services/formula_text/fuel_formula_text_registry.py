# -*- coding: utf-8 -*-
"""Реестр текстов подсказок «i» для модуля «Топливо»."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


PAGE_SPECIFIC = "Удельные показатели / ТЭП"
PAGE_RESTRICTION = "Ограничения (этап «Распред»)"
PAGE_COEFF = "Расчёт: таблица «Коэфф»"


@dataclass(frozen=True)
class FuelFormulaDef:
    key: str
    page: str
    aggregation_level: str
    cell_name: str
    default_text: str
    # Ключ в словаре, который уходит в шаблон (consumption_formulas / tooltips).
    map_key: str
    map_name: str  # consumption | restriction | coeff


def _def(
    key: str,
    *,
    page: str,
    aggregation_level: str,
    cell_name: str,
    default_text: str,
    map_key: str | None = None,
    map_name: str,
) -> FuelFormulaDef:
    return FuelFormulaDef(
        key=key,
        page=page,
        aggregation_level=aggregation_level,
        cell_name=cell_name,
        default_text=default_text,
        map_key=map_key or key,
        map_name=map_name,
    )


FUEL_FORMULA_REGISTRY: tuple[FuelFormulaDef, ...] = (
    # --- Удельные показатели (*_calc) ---
    _def(
        "snk_calc",
        page=PAGE_SPECIFIC,
        aggregation_level="Колонка таблицы",
        cell_name="snk_calc — СН на выработку ЭЭ, %",
        default_text=(
            "snk_calc равен SNK на странице топливных параметров: "
            "sn_ee / e · 100, если есть входы; иначе сохранённый FuelParam.snk. "
            "Правило заполнения: если есть данные — то же значение, что в столбце SNK; если нет — «—»."
        ),
        map_name="consumption",
    ),
    _def(
        "y_calc",
        page=PAGE_SPECIFIC,
        aggregation_level="Колонка таблицы",
        cell_name="y_calc — Удельная выработка ЭЭ на тепловом потреблении",
        default_text=(
            "y_calc = EWTP / QOTR * 1000. "
            "Правило заполнения: если есть данные для расчёта (QOTR > 0) — значение по формуле; если нет — «—»/ручной ввод."
        ),
        map_name="consumption",
    ),
    _def(
        "btp_calc",
        page=PAGE_SPECIFIC,
        aggregation_level="Колонка таблицы",
        cell_name="btp_calc — УРУТ на отпуск ЭЭ в теплофикационном режиме",
        default_text=(
            "btp_calc = EURT - K * (1 - EWTP / E) * 100. "
            "Правило заполнения: если есть данные для расчёта (VED > 1 и EWTP > 0) — значение по формуле; если нет — «—»/ручной ввод."
        ),
        map_name="consumption",
    ),
    _def(
        "sntp_calc",
        page=PAGE_SPECIFIC,
        aggregation_level="Колонка таблицы",
        cell_name="sntp_calc — Коэффициент отпуска ЭЭ в теплофикационном режиме",
        default_text=(
            "sntp_calc = [EOTP - (E - EWTP) * (1 - SNK / 100)] / EWTP. "
            "Правило заполнения: если есть данные для расчёта (VED > 1 и EWTP > 0) — значение по формуле; если нет — «—»/ручной ввод."
        ),
        map_name="consumption",
    ),
    _def(
        "bk_calc",
        page=PAGE_SPECIFIC,
        aggregation_level="Колонка таблицы",
        cell_name="bk_calc — УРУТ на отпуск ЭЭ в конденсационном режиме",
        default_text=(
            "bk_calc = [EUST - EWTP * sntp_calc * btp_calc / 1000] / "
            "[(E - EWTP) * (1 - SNK / 100)] * 1000. "
            "Правило заполнения: если есть данные для расчёта — значение по формуле; если нет — «—»/ручной ввод."
        ),
        map_name="consumption",
    ),
    # --- Ограничения ---
    _def(
        "restriction_etp",
        page=PAGE_RESTRICTION,
        aggregation_level="Колонка шапки",
        cell_name="etp — Теплофикационная выработка ЭЭ",
        default_text=(
            "Расчётная величина на этапе «Распред» (Ограничения_Click): "
            "etp = Σ ewtp по станциям региона (obl) внутри фильтра параметра распределения "
            "за расчётный год. Берутся ewtp уже после пересчёта ewtp = qotr·y/1000 "
            "на этапах «Коэфф»/«Распред», а не «сырые» значения со страницы "
            "«Сведения о работе ТЭС» без этого пересчёта."
        ),
        map_key="etp",
        map_name="restriction",
    ),
    # --- Коэфф (ячейки сводки) ---
    _def(
        "coeff_b_nust",
        page=PAGE_COEFF,
        aggregation_level="Базовый год",
        cell_name="Nуст (b_nust)",
        default_text=(
            "Сумма установленной мощности N_уст (поле nust топливных параметров) по группам фильтра параметра "
            "распределения, для которых есть строка за базовый год."
        ),
        map_key="b_nust",
        map_name="coeff",
    ),
    _def(
        "coeff_c_nust",
        page=PAGE_COEFF,
        aggregation_level="Расчётный год",
        cell_name="Nуст (c_nust)",
        default_text=(
            "Сумма nust за расчётный год по группам фильтра, у которых есть строка топлива за расчётный год "
            "и найден удельник с year ≤ расчётного (последний такой год; если ни одного — Skip)."
        ),
        map_key="c_nust",
        map_name="coeff",
    ),
    _def(
        "coeff_b_e",
        page=PAGE_COEFF,
        aggregation_level="Базовый год",
        cell_name="E (b_e)",
        default_text=(
            "Сумма выработки ЭЭ, тыс.кВтч (поле e топливных параметров групп) за базовый год — столбец «E»."
        ),
        map_key="b_e",
        map_name="coeff",
    ),
    _def(
        "coeff_c_e",
        page=PAGE_COEFF,
        aggregation_level="Расчётный год",
        cell_name="E (c_e)",
        default_text=(
            "В строке расчётного года столбец «E» (e) не заполняется суммой по станциям; целевое Ераспред "
            "см. в колонке «Выработка ЭЭ, тыс.кВтч» (e) таблицы параметров распределения."
        ),
        map_key="c_e",
        map_name="coeff",
    ),
    _def(
        "coeff_b_etp",
        page=PAGE_COEFF,
        aggregation_level="Базовый год",
        cell_name="Eтп (b_etp)",
        default_text=(
            "Сумма теплофикационной выработки ЭЭ, тыс.кВтч (поле ewtp) за базовый год — столбец «Eтп»."
        ),
        map_key="b_etp",
        map_name="coeff",
    ),
    _def(
        "coeff_c_etp",
        page=PAGE_COEFF,
        aggregation_level="Расчётный год",
        cell_name="Eтп (c_etp)",
        default_text=(
            "Сумма теплофикационной выработки ЭЭ, тыс.кВтч за расчётный год (cetp): Σ ewtp после пересчёта "
            "ewtp = qotr·y/1000 только по станциям с удельником year ≤ расчётного (иначе Skip)."
        ),
        map_key="c_etp",
        map_name="coeff",
    ),
    _def(
        "coeff_b_q",
        page=PAGE_COEFF,
        aggregation_level="Базовый год",
        cell_name="Q (b_q)",
        default_text=(
            "Сумма отпуска ТЭ, тыс.Гкал (поле q топливных параметров) по группам фильтра за базовый год."
        ),
        map_key="b_q",
        map_name="coeff",
    ),
    _def(
        "coeff_c_q",
        page=PAGE_COEFF,
        aggregation_level="Расчётный год",
        cell_name="Q (c_q)",
        default_text=(
            "Сумма отпуска ТЭ, тыс.Гкал за расчётный год по группам со строкой топлива и удельником year ≤ расчётного "
            "(если ни одного удельника — Skip)."
        ),
        map_key="c_q",
        map_name="coeff",
    ),
    _def(
        "coeff_b_qotr",
        page=PAGE_COEFF,
        aggregation_level="Базовый год",
        cell_name="Qотр (b_qotr)",
        default_text=(
            "Сумма теплового потребления (отборов турбин), тыс.Гкал (поле qotr) "
            "по группам фильтра за базовый год."
        ),
        map_key="b_qotr",
        map_name="coeff",
    ),
    _def(
        "coeff_c_qotr",
        page=PAGE_COEFF,
        aggregation_level="Расчётный год",
        cell_name="Qотр (c_qotr)",
        default_text=(
            "Сумма теплового потребления (отборов турбин), тыс.Гкал за расчётный год "
            "по группам со строкой топлива и удельником year ≤ расчётного "
            "(если ни одного удельника — Skip)."
        ),
        map_key="c_qotr",
        map_name="coeff",
    ),
    _def(
        "coeff_b_ptp",
        page=PAGE_COEFF,
        aggregation_level="Базовый год",
        cell_name="%тп (b_ptp)",
        default_text=(
            "Доля тепла в электроэнергии, %: (сумма теплофикационной выработки ЭЭ)/(сумма E)·100 "
            "за базовый год (bptp = betp/be·100)."
        ),
        map_key="b_ptp",
        map_name="coeff",
    ),
    _def(
        "coeff_c_ptp",
        page=PAGE_COEFF,
        aggregation_level="Расчётный год",
        cell_name="%тп (c_ptp)",
        default_text=(
            "Как в Access (Кнопка5_Click): cptp = csumetp / E · 100, где E — Ераспред (поле e параметра), "
            "csumetp — сумма пересчитанной теплофикационной выработки ЭЭ, тыс.кВтч (ewtp) за расчётный год. "
            "Если E в параметре не задан, при расчёте "
            "в знаменателе используется ΣE по строкам топлива расчётного года."
        ),
        map_key="c_ptp",
        map_name="coeff",
    ),
    _def(
        "coeff_b_h",
        page=PAGE_COEFF,
        aggregation_level="Базовый год",
        cell_name="ЧЧИУМ (b_h)",
        default_text=(
            "ЧЧИУМ, ч за базовый год: ΣE / ΣN_уст·1000 (bh в расчёте «Коэфф»; не поле h станции)."
        ),
        map_key="b_h",
        map_name="coeff",
    ),
    _def(
        "coeff_c_h",
        page=PAGE_COEFF,
        aggregation_level="Расчётный год",
        cell_name="ЧЧИУМ (c_h)",
        default_text=(
            "ЧЧИУМ, ч за расчётный год: Ераспред / ΣN_уст·1000 (ch), где ΣN_уст — по станциям "
            "с топливом и удельником year ≤ расчётного (если ни одного — Skip)."
        ),
        map_key="c_h",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_n",
        page=PAGE_COEFF,
        aggregation_level="Новые (ПСУ/ГТУ/ПГУ)",
        cell_name="Nнов (tech_n)",
        default_text=(
            "Сумма N_уст расчётного года по «новым» группам данного типа: в базовом году N_уст было 0; "
            "станция учтена только если есть удельник year ≤ расчётного (иначе Skip). "
            "Отнесение к ПСУ/ГТУ/ПГУ — по коду obor: ГТУ 20|90, ПГУ 21|91, ПСУ = остальное новое."
        ),
        map_key="tech_n",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_h_col_empty",
        page=PAGE_COEFF,
        aggregation_level="Новые (ПСУ/ГТУ/ПГУ)",
        cell_name="Kнов / пустая ячейка ЧЧИУМ",
        default_text=(
            "В строках ПСУ/ГТУ/ПГУ коэффициенты hn (hnps, hngt, hnpg) вводятся в столбце «ЧЧИУМ»; "
            "столбец K_нов пересчитывается (kn = hn/ch) после сохранения."
        ),
        map_key="tech_h_col_empty",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_h_psu",
        page=PAGE_COEFF,
        aggregation_level="Новые ПСУ",
        cell_name="ЧЧИУМ hnps (tech_h_psu)",
        default_text="Коэффициент hnps вводится в столбце «ЧЧИУМ»; здесь значение не дублируется.",
        map_key="tech_h_psu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_h_gtu",
        page=PAGE_COEFF,
        aggregation_level="Новые ГТУ",
        cell_name="ЧЧИУМ hngt (tech_h_gtu)",
        default_text="Коэффициент hngt вводится в столбце «ЧЧИУМ»; здесь значение не дублируется.",
        map_key="tech_h_gtu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_h_pgu",
        page=PAGE_COEFF,
        aggregation_level="Новые ПГУ",
        cell_name="ЧЧИУМ hnpg (tech_h_pgu)",
        default_text="Коэффициент hnpg вводится в столбце «ЧЧИУМ»; здесь значение не дублируется.",
        map_key="tech_h_pgu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_k_psu",
        page=PAGE_COEFF,
        aggregation_level="Новые ПСУ",
        cell_name="Kнов ПСУ (tech_k_psu)",
        default_text="K_нов для ПСУ: knps = hnps / ch (этап «Коэфф»; значение в сводке коэффициентов).",
        map_key="tech_k_psu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_k_gtu",
        page=PAGE_COEFF,
        aggregation_level="Новые ГТУ",
        cell_name="Kнов ГТУ (tech_k_gtu)",
        default_text="K_нов для ГТУ: kngt = hngt / ch.",
        map_key="tech_k_gtu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_k_pgu",
        page=PAGE_COEFF,
        aggregation_level="Новые ПГУ",
        cell_name="Kнов ПГУ (tech_k_pgu)",
        default_text="K_нов для ПГУ: knpg = hnpg / ch.",
        map_key="tech_k_pgu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_agg_n",
        page=PAGE_COEFF,
        aggregation_level="Агрегат новых",
        cell_name="ΣNнов (tech_agg_n)",
        default_text=(
            "Сумма мощностей новых агрегатов (cnustn): Σ N_уст по группам, где в базовом году N_уст было 0 "
            "(и есть удельник year ≤ расчётного — иначе Skip)."
        ),
        map_key="tech_agg_n",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_agg_hd",
        page=PAGE_COEFF,
        aggregation_level="Агрегат новых",
        cell_name="Hдейств hd (tech_agg_hd)",
        default_text=(
            "Hдейств (hd), ч: "
            "hd = (Ераспред − (Nпс·knps + Nгт·kngt + Nпг·knpg)·ch/1000) / (Nуст − Nнов) · 1000 "
            "(как в Access Кнопка5; при Nуст=Nнов → 0)."
        ),
        map_key="tech_agg_hd",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_hd_col_ph",
        page=PAGE_COEFF,
        aggregation_level="Агрегат новых",
        cell_name="PH (tech_hd_col_ph)",
        default_text=(
            "PH = hd / bh: отношение ЧЧИУМ на действующую часть парка (hd в строке выше) к базовому ЧЧИУМ bh "
            "(как в сводке этапа «Коэфф»). Выводится в строке ПСУ под тем же столбцом, что и hd."
        ),
        map_key="tech_hd_col_ph",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_agg_kn",
        page=PAGE_COEFF,
        aggregation_level="Агрегат новых",
        cell_name="Kнов ср. (tech_agg_kn)",
        default_text=(
            "Средневзвешенный K_нов по новым мощностям (kn): (N_пс·knps + N_гт·kngt + N_пг·knpg) / cnustn."
        ),
        map_key="tech_agg_kn",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_ch_psu",
        page=PAGE_COEFF,
        aggregation_level="Ввод hn ПСУ",
        cell_name="Ввод hnps (tech_ch_psu)",
        default_text=(
            "Ввод ЧЧИУМ hnps для ПСУ (поле параметра распределения). После сохранения пересчитывается этап «Коэфф»: "
            "knps = hnps/ch и связанные поля сводки."
        ),
        map_key="tech_ch_psu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_ch_gtu",
        page=PAGE_COEFF,
        aggregation_level="Ввод hn ГТУ",
        cell_name="Ввод hngt (tech_ch_gtu)",
        default_text=(
            "Ввод ЧЧИУМ hngt для ГТУ. После сохранения: kngt = hngt/ch и пересчёт этапа «Коэфф»."
        ),
        map_key="tech_ch_gtu",
        map_name="coeff",
    ),
    _def(
        "coeff_tech_ch_pgu",
        page=PAGE_COEFF,
        aggregation_level="Ввод hn ПГУ",
        cell_name="Ввод hnpg (tech_ch_pgu)",
        default_text=(
            "Ввод ЧЧИУМ hnpg для ПГУ. После сохранения: knpg = hnpg/ch и пересчёт этапа «Коэфф»."
        ),
        map_key="tech_ch_pgu",
        map_name="coeff",
    ),
    _def(
        "coeff_r_nust",
        page=PAGE_COEFF,
        aggregation_level="Отношения к базе",
        cell_name="Nуст (r_nust)",
        default_text=(
            "Для отношения текущего года к базовому по N_уст отдельный коэффициент в этой строке не выводится."
        ),
        map_key="r_nust",
        map_name="coeff",
    ),
    _def(
        "coeff_r_pe",
        page=PAGE_COEFF,
        aggregation_level="Отношения к базе",
        cell_name="PE (r_pe)",
        default_text=(
            "PE = Ераспред / ΣE за базовый год (отношение целевой выработки к сумме E базы)."
        ),
        map_key="r_pe",
        map_name="coeff",
    ),
    _def(
        "coeff_r_etp",
        page=PAGE_COEFF,
        aggregation_level="Отношения к базе",
        cell_name="PETP (r_etp)",
        default_text=(
            "PETP = Σ теплофикационной выработки ЭЭ расчётного года / Σ базового года "
            "(суммы поля ewtp по фильтру). "
            "Не путать с PQ — это отношение по столбцу Q (см. следующий столбец)."
        ),
        map_key="r_etp",
        map_name="coeff",
    ),
    _def(
        "coeff_r_pq",
        page=PAGE_COEFF,
        aggregation_level="Отношения к базе",
        cell_name="PQ (r_pq)",
        default_text="PQ = ΣQ расчётного года / ΣQ базового года.",
        map_key="r_pq",
        map_name="coeff",
    ),
    _def(
        "coeff_r_potr",
        page=PAGE_COEFF,
        aggregation_level="Отношения к базе",
        cell_name="Pотр (r_potr)",
        default_text=(
            "Pотр = Σ теплового потребления (отборов турбин) расчётного года / Σ базового года "
            "(суммы поля qotr по фильтру)."
        ),
        map_key="r_potr",
        map_name="coeff",
    ),
    _def(
        "coeff_r_ptp",
        page=PAGE_COEFF,
        aggregation_level="Отношения к базе",
        cell_name="%тп (r_ptp)",
        default_text=(
            "Для доли %тп отдельное отношение к базе в этой строке не показывается "
            "(см. столбцы E, Q, тепловое потребление/qotr, Н)."
        ),
        map_key="r_ptp",
        map_name="coeff",
    ),
    _def(
        "coeff_r_ph1",
        page=PAGE_COEFF,
        aggregation_level="Отношения к базе",
        cell_name="PH1 (r_ph1)",
        default_text=(
            "PH1 = ch / bh: отношение ЧЧИУМ (Ераспред/ΣNуст·1000) расчётного года к базовому (ΣE/ΣNуст·1000)."
        ),
        map_key="r_ph1",
        map_name="coeff",
    ),
)

_BY_KEY: dict[str, FuelFormulaDef] = {item.key: item for item in FUEL_FORMULA_REGISTRY}


def get_formula_def(formula_key: str) -> FuelFormulaDef | None:
    return _BY_KEY.get(str(formula_key or "").strip())


def iter_formula_defs(*, map_name: str | None = None) -> Iterator[FuelFormulaDef]:
    for item in FUEL_FORMULA_REGISTRY:
        if map_name is None or item.map_name == map_name:
            yield item
