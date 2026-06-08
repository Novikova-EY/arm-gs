# -*- coding: utf-8 -*-
"""Константы страницы электроёмкости."""

from decimal import Decimal

ROW_KIND_INTENSITY = "intensity"
ROW_KIND_GRAPH_POINT = "graph_point"
ROW_KIND_CALCULATED = "calculated"
ROW_KIND_DELTA = "delta"

ROW_KINDS: tuple[str, ...] = (
    ROW_KIND_INTENSITY,
    ROW_KIND_GRAPH_POINT,
    ROW_KIND_CALCULATED,
    ROW_KIND_DELTA,
)

# Строки и коэффициенты A/X — только для ВЭД из справочника /refdata/ved.
EI_MODEL_ROW_KINDS: frozenset[str] = frozenset(
    {ROW_KIND_GRAPH_POINT, ROW_KIND_CALCULATED, ROW_KIND_DELTA}
)

# Точность вывода «Характерные точки графика» (не зависит от округления UI).
EI_GRAPH_POINT_ROUNDING_DIGITS = 9

# Коэффициент X — среднее по строке «Характерные точки графика» с этого года по текущий включительно.
EI_COEFFICIENT_X_AVG_START_YEAR = 2010

# Точность вывода коэффициента X на странице (не зависит от округления UI).
EI_COEFFICIENT_X_DISPLAY_ROUNDING_DIGITS = 4

# Точность вывода коэффициента Арасч. на странице (не зависит от округления UI).
EI_COEFFICIENT_A_COMPUTED_DISPLAY_ROUNDING_DIGITS = 4

# Строки «Электроёмкость», «Электроёмкость (расчётная)», «Δ для электроёмкости».
EI_INTENSITY_VALUE_ROW_KINDS: frozenset[str] = frozenset(
    {ROW_KIND_INTENSITY, ROW_KIND_CALCULATED, ROW_KIND_DELTA}
)

# Режим «Не округлять» на странице: макс. знаков после запятой (хранение и отображение).
EI_INTENSITY_MAX_FRACTION_DIGITS = 10

# Точность всплывающей подсказки (title) для строки «Электроёмкость».
EI_INTENSITY_TOOLTIP_ROUNDING_DIGITS = EI_INTENSITY_MAX_FRACTION_DIGITS

# Расчёт по формуле при отсутствии значения в БД, ячейки остаются редактируемыми.
EI_FORMULA_EDITABLE_ROW_KINDS: frozenset[str] = frozenset({ROW_KIND_GRAPH_POINT})

# Не показывать на странице (как в потреблении по ВЭД).
EI_FD_EXCLUDED_NAME_KEYS = frozenset({"новые территории"})
EI_FD_PLACEHOLDER_NAME_KEYS = frozenset({"не указано", "не указано2"})

RUSSIA_TERRITORY_LABELS = frozenset(
    {
        "рф",
        "россия",
        "российская федерация",
        "российская федерация (всего)",
        "россия (всего)",
    }
)

EI_INTENSITY_FORMULA_LABEL = "Электроемкость"

# млн кВт·ч / млн руб. → кВт·ч/тыс. руб.
EI_INTENSITY_UNIT_FACTOR = Decimal("1000")

EI_INTENSITY_FORMULA_TOOLTIP = (
    "Электроёмкость, кВт·ч/тыс. руб., по каждому году (не позже года "
    "с признаком «текущий» включительно) = Потребление ээ / Выпуск продукции × 1000 "
    "(потребление — млн кВт·ч, выпуск — млн руб.)."
)

EI_CALCULATED_FORMULA_TOOLTIP = (
    "Электроёмкость (расчётная), кВт·ч/тыс. руб., по каждому году (не позже года "
    "с признаком «текущий» включительно) = введённый вручную коэффициент A × "
    "(Инвестиции в основной капитал)^коэффициент X "
    "(инвестиции — млн руб.). Значение «Арасч.» — подсказка, в расчёт строки не входит."
)

EI_COEFFICIENT_X_FORMULA_TOOLTIP = (
    "Коэффициент X = среднее арифметическое значений строки «Характерные точки графика» "
    f"по годам {EI_COEFFICIENT_X_AVG_START_YEAR}…N включительно (N — год с признаком «текущий»; "
    "пустые ячейки в среднее не входят)."
)

EI_COEFFICIENT_A_FORMULA_TOOLTIP = (
    "Коэффициент A вводится вручную; используется для строки «Электроёмкость (расчётная)» "
    "и линии «Расчётная» на графике."
)

EI_COEFFICIENT_A_COMPUTED_FORMULA_TOOLTIP = (
    "«Арасч.» = EXP(СРЗНАЧ( LN(Yi) − X × LN(Ii) ) ), "
    f"где Yi — фактическая электроёмкость, Ii — накопленные инвестиции по годам "
    f"{EI_COEFFICIENT_X_AVG_START_YEAR}…N (N — год с признаком «текущий»), "
    "X — коэффициент X; LN и EXP — натуральный логарифм и экспонента (как в Excel); "
    "годы с неполными или неположительными Yi, Ii в среднее не входят — только подсказка, "
    "в расчёт строки не входит."
)

EI_DELTA_FORMULA_TOOLTIP = (
    "Δ для электроёмкости по каждому году (не позже года с признаком «текущий» "
    "включительно) = Электроёмкость − Электроёмкость (расчётная), "
    "кВт·ч/тыс. руб."
)

EI_GRAPH_POINT_FORMULA_TOOLTIP = (
    "Характерные точки графика по каждому году (не позже года с признаком «текущий» "
    "включительно) = LOG(Электроёмкость_Y / Электроёмкость_{Y−1}; "
    "Накопленные инвестиции_Y / Накопленные инвестиции_{Y−1}) "
    "(как в Excel: LOG; первый аргумент — отношение электроёмкости за год и предыдущий год, "
    "второй — основание логарифма из отношения накопленных инвестиций; "
    "электроёмкость считается по строке «Электроёмкость» из потребления и выпуска "
    "без округления отображения). "
    "При пустой ячейке значение подставляется по формуле; вручную введённое сохраняется "
    "(9 знаков после запятой)."
)

ROW_LABEL_BY_KIND: dict[str, str] = {
    ROW_KIND_INTENSITY: EI_INTENSITY_FORMULA_LABEL,
    ROW_KIND_GRAPH_POINT: "Характерные точки графика",
    ROW_KIND_CALCULATED: "Электроемкость (расчетная)",
    ROW_KIND_DELTA: "Δ для электроемкости",
}

ROW_FORMULA_KEY_BY_KIND: dict[str, str] = {
    ROW_KIND_INTENSITY: "ei_intensity",
    ROW_KIND_GRAPH_POINT: "ei_graph_point",
    ROW_KIND_CALCULATED: "ei_calculated",
    ROW_KIND_DELTA: "ei_delta",
}

# Справочные строки по ВЭД — только чтение, данные с отдельных страниц долгосрочного прогноза.
REF_ROW_PRODUCT_OUTPUT = "product_output"
REF_ROW_CONSUMPTION = "consumption"
REF_ROW_ACCUM_FIXED_CAPITAL = "accum_fixed_capital"

REF_ROW_KINDS: tuple[str, ...] = (
    REF_ROW_PRODUCT_OUTPUT,
    REF_ROW_CONSUMPTION,
    REF_ROW_ACCUM_FIXED_CAPITAL,
)

# Эндпоинты Flask для ссылок в шаблоне (url_for).
REF_ROW_SOURCE_ENDPOINT: dict[str, str] = {
    REF_ROW_PRODUCT_OUTPUT: "economics_bp.product_output",
    REF_ROW_CONSUMPTION: "economics_bp.ved_consumption",
    REF_ROW_ACCUM_FIXED_CAPITAL: "economics_bp.accum_fixed_capital",
}

REF_ROW_SOURCE_PAGE_TITLE: dict[str, str] = {
    REF_ROW_PRODUCT_OUTPUT: "Выпуск продукции",
    REF_ROW_CONSUMPTION: "Потребление ЭЭ по ВЭД",
    REF_ROW_ACCUM_FIXED_CAPITAL: "Накопленные инвестиции в основной капитал",
}

REF_ROW_LABEL_BY_KIND: dict[str, str] = {
    REF_ROW_PRODUCT_OUTPUT: "Выпуск продукции",
    REF_ROW_CONSUMPTION: "Потребление ээ",
    REF_ROW_ACCUM_FIXED_CAPITAL: "Накопленные инвестиции в основной капитал",
}


def ref_row_label(ref_kind: str, *, price_year: int | None = None) -> str:
    """Подпись справочной строки на странице электроёмкости."""
    _ = price_year
    return REF_ROW_LABEL_BY_KIND.get(ref_kind, ref_kind)

REF_ROW_UNIT_BY_KIND: dict[str, str] = {
    REF_ROW_PRODUCT_OUTPUT: "млн руб.",
    REF_ROW_CONSUMPTION: "млн кВт.ч",
    REF_ROW_ACCUM_FIXED_CAPITAL: "млн руб.",
}

REF_ROW_CSS_BY_KIND: dict[str, str] = {
    REF_ROW_PRODUCT_OUTPUT: "lt-ei-ref-product-output",
    REF_ROW_CONSUMPTION: "lt-ei-ref-consumption",
    REF_ROW_ACCUM_FIXED_CAPITAL: "lt-ei-ref-accum-capital",
}

# Блок «Промышленное производство» на странице электроёмкости (уровень ФО).
INDUSTRIAL_GROUP_SECTION_LABEL = "Промышленное производство"

INDUSTRIAL_GROUP_COMPONENT_DISPLAY_NAMES: tuple[str, ...] = (
    "Обрабатывающие производства",
    "Добывающие производства",
    "Производство и распределение электроэнергии, газа и воды",
)

INDUSTRIAL_GROUP_COMPONENTS_JOINED = " + ".join(INDUSTRIAL_GROUP_COMPONENT_DISPLAY_NAMES)

REF_ROW_INDUSTRIAL_FORMULA_KEY_BY_KIND: dict[str, str] = {
    REF_ROW_PRODUCT_OUTPUT: "ei_industrial_product_output",
    REF_ROW_CONSUMPTION: "ei_industrial_consumption",
    REF_ROW_ACCUM_FIXED_CAPITAL: "ei_industrial_accum_fixed_capital",
}

EI_INDUSTRIAL_PRODUCT_OUTPUT_FORMULA_TOOLTIP = (
    f"Выпуск продукции = {INDUSTRIAL_GROUP_COMPONENTS_JOINED} "
    "(сумма строк «Выпуск продукции» по указанным ВЭД), млн руб."
)

EI_INDUSTRIAL_CONSUMPTION_FORMULA_TOOLTIP = (
    f"Потребление ээ = {INDUSTRIAL_GROUP_COMPONENTS_JOINED} "
    "(сумма строк «Потребление ээ» по указанным ВЭД), млн кВт·ч."
)

EI_INDUSTRIAL_ACCUM_FIXED_CAPITAL_FORMULA_TOOLTIP = (
    f"Накопленные инвестиции в основной капитал = {INDUSTRIAL_GROUP_COMPONENTS_JOINED} "
    "(сумма строк «Накопленные инвестиции в основной капитал» по указанным ВЭД), млн руб."
)

# Блок «Всего» на странице электроёмкости (уровень ФО, перед «Промышленное производство»).
FD_TOTAL_SECTION_LABEL = "Всего"

NETWORK_LOSSES_VED_TARGET = "Потери в сетях"
POWER_STATION_OWN_NEEDS_VED_TARGET = "С.н. электростанций"

# млн кВт·ч → млрд кВт·ч.
EI_BILLION_KWH_FACTOR = Decimal("1000")

REF_ROW_FD_VRP = "fd_vrp"
REF_ROW_FD_TOTAL_CONSUMPTION = "fd_total_consumption"
REF_ROW_FD_VED_CONSUMPTION = "fd_ved_consumption"
REF_ROW_FD_NETWORK_LOSSES = "fd_network_losses"
REF_ROW_FD_POWER_STATION = "fd_power_station"
REF_ROW_FD_ACCUM_FIXED_CAPITAL = "fd_accum_fixed_capital"

FD_TOTAL_REF_ROW_KINDS: tuple[str, ...] = (
    REF_ROW_FD_VRP,
    REF_ROW_FD_TOTAL_CONSUMPTION,
    REF_ROW_FD_VED_CONSUMPTION,
    REF_ROW_FD_NETWORK_LOSSES,
    REF_ROW_FD_POWER_STATION,
    REF_ROW_FD_ACCUM_FIXED_CAPITAL,
)

REF_ROW_FD_LABEL_BY_KIND: dict[str, str] = {
    REF_ROW_FD_VRP: "ВРП",
    REF_ROW_FD_TOTAL_CONSUMPTION: "Потребление ээ",
    REF_ROW_FD_VED_CONSUMPTION: "Потребление ээ ВЭД",
    REF_ROW_FD_NETWORK_LOSSES: NETWORK_LOSSES_VED_TARGET,
    REF_ROW_FD_POWER_STATION: POWER_STATION_OWN_NEEDS_VED_TARGET,
    REF_ROW_FD_ACCUM_FIXED_CAPITAL: "Накопленные инвестиции в основной капитал",
}

REF_ROW_FD_UNIT_BY_KIND: dict[str, str] = {
    REF_ROW_FD_VRP: "млн руб.",
    REF_ROW_FD_TOTAL_CONSUMPTION: "млрд кВт.ч.",
    REF_ROW_FD_VED_CONSUMPTION: "млрд кВт.ч.",
    REF_ROW_FD_NETWORK_LOSSES: "млрд кВт.ч.",
    REF_ROW_FD_POWER_STATION: "млрд кВт.ч.",
    REF_ROW_FD_ACCUM_FIXED_CAPITAL: "млн руб.",
}

REF_ROW_FD_CSS_BY_KIND: dict[str, str] = {
    REF_ROW_FD_VRP: "lt-ei-ref-product-output",
    REF_ROW_FD_TOTAL_CONSUMPTION: "lt-ei-ref-consumption",
    REF_ROW_FD_VED_CONSUMPTION: "lt-ei-ref-consumption",
    REF_ROW_FD_NETWORK_LOSSES: "lt-ei-ref-consumption",
    REF_ROW_FD_POWER_STATION: "lt-ei-ref-consumption",
    REF_ROW_FD_ACCUM_FIXED_CAPITAL: "lt-ei-ref-accum-capital",
}

REF_ROW_FD_FORMULA_KEY_BY_KIND: dict[str, str] = {
    REF_ROW_FD_VRP: "ei_fd_total_vrp",
    REF_ROW_FD_TOTAL_CONSUMPTION: "ei_fd_total_consumption",
    REF_ROW_FD_VED_CONSUMPTION: "ei_fd_total_ved_consumption",
    REF_ROW_FD_NETWORK_LOSSES: "ei_fd_total_network_losses",
    REF_ROW_FD_POWER_STATION: "ei_fd_total_power_station",
    REF_ROW_FD_ACCUM_FIXED_CAPITAL: "ei_fd_total_accum_fixed_capital",
}

EI_FD_TOTAL_VRP_FORMULA_TOOLTIP = (
    "ВРП = сумма строк «Выпуск продукции» по всем ВЭД федерального округа, млн руб."
)

EI_FD_TOTAL_VED_CONSUMPTION_FORMULA_TOOLTIP = (
    "Потребление ээ ВЭД = сумма строк «Потребление ээ» по всем ВЭД федерального округа / 1000, "
    "млрд кВт·ч."
)

EI_FD_TOTAL_NETWORK_LOSSES_FORMULA_TOOLTIP = (
    "Потери в сетях = значение строки «Потери в сетях» со страницы «Потребление ЭЭ по ВЭД» "
    "для соответствующего федерального округа / 1000, млрд кВт·ч."
)

EI_FD_TOTAL_POWER_STATION_FORMULA_TOOLTIP = (
    "С.н. электростанций = значение строки «С.н. электростанций» со страницы «Потребление ЭЭ по ВЭД» "
    "для соответствующего федерального округа / 1000, млрд кВт·ч."
)

EI_FD_TOTAL_CONSUMPTION_FORMULA_TOOLTIP = (
    "Потребление ээ = Потребление ээ ВЭД + Потери в сетях + С.н. электростанций "
    "(сумма соответствующих строк блока «Всего»), млрд кВт·ч."
)

EI_FD_TOTAL_ACCUM_FIXED_CAPITAL_FORMULA_TOOLTIP = (
    "Накопленные инвестиции в основной капитал = сумма строк "
    "«Накопленные инвестиции в основной капитал» по всем ВЭД федерального округа, млн руб."
)

# Блок «Население» на странице электроёмкости (уровень ФО, после всех ВЭД).
HOUSEHOLD_VED_TARGET = "Домашние хозяйства"
POPULATION_SECTION_LABEL = "Население"
POPULATION_SECTION_MARKER = "population"

REF_ROW_POPULATION = "population"
REF_ROW_HOUSEHOLD_CONSUMPTION = "household_consumption"
REF_ROW_ACCUM_MONETARY_INCOME = "accum_monetary_income"

POP_REF_ROW_KINDS: tuple[str, ...] = (
    REF_ROW_POPULATION,
    REF_ROW_HOUSEHOLD_CONSUMPTION,
    REF_ROW_ACCUM_MONETARY_INCOME,
)

POP_REF_ROW_LABEL_BY_KIND: dict[str, str] = {
    REF_ROW_POPULATION: "Численность населения (на начало года)",
    REF_ROW_HOUSEHOLD_CONSUMPTION: "Потребление ээ в домашних хозяйствах",
    REF_ROW_ACCUM_MONETARY_INCOME: "Накопленные денежные доходы населения",
}

POP_REF_ROW_UNIT_BY_KIND: dict[str, str] = {
    REF_ROW_POPULATION: "тыс. чел.",
    REF_ROW_HOUSEHOLD_CONSUMPTION: "млн кВт.ч.",
    REF_ROW_ACCUM_MONETARY_INCOME: "млн руб.",
}

POP_REF_ROW_CSS_BY_KIND: dict[str, str] = {
    REF_ROW_POPULATION: "lt-ei-ref-population",
    REF_ROW_HOUSEHOLD_CONSUMPTION: "lt-ei-ref-consumption",
    REF_ROW_ACCUM_MONETARY_INCOME: "lt-ei-ref-accum-capital",
}

POP_REF_ROW_SOURCE_ENDPOINT: dict[str, str] = {
    REF_ROW_POPULATION: "economics_bp.population",
    REF_ROW_HOUSEHOLD_CONSUMPTION: "economics_bp.ved_consumption",
    REF_ROW_ACCUM_MONETARY_INCOME: "economics_bp.accum_monetary_income",
}

POP_REF_ROW_SOURCE_PAGE_TITLE: dict[str, str] = {
    REF_ROW_POPULATION: "Численность населения",
    REF_ROW_HOUSEHOLD_CONSUMPTION: "Потребление ЭЭ по ВЭД",
    REF_ROW_ACCUM_MONETARY_INCOME: "Накопленные денежные доходы населения",
}

POP_REF_ROW_FORMULA_KEY_BY_KIND: dict[str, str] = {
    REF_ROW_POPULATION: "ei_pop_ref_population",
    REF_ROW_HOUSEHOLD_CONSUMPTION: "ei_pop_ref_household_consumption",
    REF_ROW_ACCUM_MONETARY_INCOME: "ei_pop_ref_accum_monetary_income",
}

EI_POP_REF_POPULATION_FORMULA_TOOLTIP = (
    "Численность населения (на начало года) — значение со страницы "
    "«Численность населения» для соответствующего федерального округа, тыс. чел."
)

EI_POP_REF_HOUSEHOLD_CONSUMPTION_FORMULA_TOOLTIP = (
    "Потребление ээ в домашних хозяйствах = значение строки «Домашние хозяйства» "
    "со страницы «Потребление ЭЭ по ВЭД» для соответствующего федерального округа, "
    "млн кВт·ч."
)

EI_POP_REF_ACCUM_MONETARY_INCOME_FORMULA_TOOLTIP = (
    "Накопленные денежные доходы населения — значение со страницы "
    "«Накопленные денежные доходы населения» для соответствующего федерального "
    "округа, млн руб."
)

POP_ROW_LABEL_BY_KIND: dict[str, str] = {
    ROW_KIND_INTENSITY: "Потребление ээ на душу населения",
    ROW_KIND_GRAPH_POINT: "Характерные точки графика",
    ROW_KIND_CALCULATED: "Потребление ээ на душу (расчетное)",
    ROW_KIND_DELTA: "Δ для потребления ээ на душу",
}

POP_ROW_FORMULA_KEY_BY_KIND: dict[str, str] = {
    ROW_KIND_INTENSITY: "ei_pop_per_capita",
    ROW_KIND_GRAPH_POINT: "ei_pop_graph_point",
    ROW_KIND_CALCULATED: "ei_pop_calculated",
    ROW_KIND_DELTA: "ei_pop_delta",
}

EI_POP_PER_CAPITA_FORMULA_TOOLTIP = (
    "Потребление ээ на душу населения, кВт·ч/тыс. руб., по каждому году "
    "(не позже года с признаком «текущий» включительно) = Потребление ээ в домашних "
    "хозяйствах / Численность населения (на начало года) "
    "(потребление — млн кВт·ч, численность — тыс. чел.)."
)

EI_POP_CALCULATED_FORMULA_TOOLTIP = (
    "Потребление ээ на душу (расчётное), кВт·ч/тыс. руб., по каждому году "
    "(не позже года с признаком «текущий» включительно) = введённый вручную "
    "коэффициент A × (Накопленные денежные доходы населения)^коэффициент X "
    "(доходы — млн руб.). Значение «Арасч.» — подсказка, в расчёт строки не входит."
)

EI_POP_DELTA_FORMULA_TOOLTIP = (
    "Δ для потребления ээ на душу по каждому году (не позже года с признаком "
    "«текущий» включительно) = Потребление ээ на душу (расчётное) − "
    "Потребление ээ на душу населения, кВт·ч/тыс. руб."
)

EI_POP_GRAPH_POINT_FORMULA_TOOLTIP = (
    "Характерные точки графика по каждому году (не позже года с признаком «текущий» "
    "включительно) = LOG(Потребление ээ на душу_Y / Потребление ээ на душу_{Y−1}; "
    "Накопленные денежные доходы_Y / Накопленные денежные доходы_{Y−1}) "
    "(как в Excel: LOG; первый аргумент — отношение потребления на душу за год "
    "и предыдущий год, второй — основание логарифма из отношения накопленных "
    "денежных доходов; потребление на душу считается по строке "
    "«Потребление ээ на душу населения» без округления отображения). "
    "При пустой ячейке значение подставляется по формуле; вручную введённое "
    "сохраняется (9 знаков после запятой)."
)

EI_POP_COEFFICIENT_A_FORMULA_TOOLTIP = (
    "Коэффициент A вводится вручную; используется для строки "
    "«Потребление ээ на душу (расчётное)» и линии «Расчётная» на графике."
)

EI_POP_COEFFICIENT_A_COMPUTED_FORMULA_TOOLTIP = (
    "«Арасч.» = EXP(СРЗНАЧ( LN(Yi) − X × LN(Ii) ) ), "
    f"где Yi — фактическое потребление ээ на душу населения, Ii — накопленные "
    f"денежные доходы населения по годам {EI_COEFFICIENT_X_AVG_START_YEAR}…N "
    "(N — год с признаком «текущий»), X — коэффициент X; LN и EXP — натуральный "
    "логарифм и экспонента (как в Excel); годы с неполными или неположительными "
    "Yi, Ii в среднее не входят — только подсказка, в расчёт строки не входит."
)

EI_POP_COEFFICIENT_X_FORMULA_TOOLTIP = (
    "Коэффициент X = среднее арифметическое значений строки «Характерные точки графика» "
    f"по годам {EI_COEFFICIENT_X_AVG_START_YEAR}…N включительно (N — год с признаком "
    "«текущий»; пустые ячейки в среднее не входят)."
)

# Сводные строки РФ на странице электроёмкости (уровень «Российская Федерация»).
REF_ROW_RF_TOTAL_CONSUMPTION = "rf_total_consumption"
REF_ROW_RF_GROWTH_RATE = "rf_growth_rate"
REF_ROW_RF_VED_CONSUMPTION = "rf_ved_consumption"
REF_ROW_RF_GAES = "rf_gaes"
REF_ROW_RF_CONSUMPTION_WITHOUT_GAES = "rf_consumption_without_gaes"
REF_ROW_RF_NETWORK_LOSSES = "rf_network_losses"
REF_ROW_RF_POWER_STATION = "rf_power_station"
REF_ROW_RF_GDP = "rf_gdp"
REF_ROW_RF_GDP_INTENSITY = "rf_gdp_intensity"

RF_TOTAL_REF_ROW_KINDS: tuple[str, ...] = (
    REF_ROW_RF_TOTAL_CONSUMPTION,
    REF_ROW_RF_GROWTH_RATE,
    REF_ROW_RF_VED_CONSUMPTION,
    REF_ROW_RF_GAES,
    REF_ROW_RF_CONSUMPTION_WITHOUT_GAES,
    REF_ROW_RF_NETWORK_LOSSES,
    REF_ROW_RF_POWER_STATION,
    REF_ROW_RF_GDP,
    REF_ROW_RF_GDP_INTENSITY,
)

REF_ROW_RF_LABEL_BY_KIND: dict[str, str] = {
    REF_ROW_RF_TOTAL_CONSUMPTION: "Потребление ЭЭ",
    REF_ROW_RF_GROWTH_RATE: "Темп прироста",
    REF_ROW_RF_VED_CONSUMPTION: "Потребление (полезное) суммарно по ВЭД",
    REF_ROW_RF_GAES: "ГАЭС",
    REF_ROW_RF_CONSUMPTION_WITHOUT_GAES: "Потребление без ГАЭС",
    REF_ROW_RF_NETWORK_LOSSES: "потери в сетях",
    REF_ROW_RF_POWER_STATION: "с.н. эл.станций",
    REF_ROW_RF_GDP: "ВВП",
    REF_ROW_RF_GDP_INTENSITY: "Электроемкость ВВП",
}


def rf_gdp_row_label(price_year: int | None) -> str:
    """Подпись строки ВВП."""
    return REF_ROW_RF_LABEL_BY_KIND[REF_ROW_RF_GDP]


REF_ROW_RF_UNIT_BY_KIND: dict[str, str] = {
    REF_ROW_RF_TOTAL_CONSUMPTION: "млрд кВт.ч.",
    REF_ROW_RF_GROWTH_RATE: "%",
    REF_ROW_RF_VED_CONSUMPTION: "млрд кВт.ч.",
    REF_ROW_RF_GAES: "млрд кВт.ч.",
    REF_ROW_RF_CONSUMPTION_WITHOUT_GAES: "млрд кВт.ч.",
    REF_ROW_RF_NETWORK_LOSSES: "млрд кВт.ч.",
    REF_ROW_RF_POWER_STATION: "млрд кВт.ч.",
    REF_ROW_RF_GDP: "млрд руб.",
    REF_ROW_RF_GDP_INTENSITY: "кВт.ч./тыс.руб.",
}

REF_ROW_RF_CSS_BY_KIND: dict[str, str] = {
    REF_ROW_RF_TOTAL_CONSUMPTION: "lt-ei-ref-consumption",
    REF_ROW_RF_GROWTH_RATE: "lt-ei-rf-growth-rate",
    REF_ROW_RF_VED_CONSUMPTION: "lt-ei-ref-consumption",
    REF_ROW_RF_GAES: "lt-ei-ref-consumption",
    REF_ROW_RF_CONSUMPTION_WITHOUT_GAES: "lt-ei-ref-consumption",
    REF_ROW_RF_NETWORK_LOSSES: "lt-ei-ref-consumption",
    REF_ROW_RF_POWER_STATION: "lt-ei-ref-consumption",
    REF_ROW_RF_GDP: "lt-ei-ref-product-output",
    REF_ROW_RF_GDP_INTENSITY: "lt-ei-row-intensity",
}

REF_ROW_RF_FORMULA_KEY_BY_KIND: dict[str, str] = {
    REF_ROW_RF_TOTAL_CONSUMPTION: "ei_rf_total_consumption",
    REF_ROW_RF_GROWTH_RATE: "ei_rf_growth_rate",
    REF_ROW_RF_VED_CONSUMPTION: "ei_rf_summary_ved_consumption",
    REF_ROW_RF_GAES: "ei_rf_gaes",
    REF_ROW_RF_CONSUMPTION_WITHOUT_GAES: "ei_rf_consumption_without_gaes",
    REF_ROW_RF_NETWORK_LOSSES: "ei_rf_network_losses",
    REF_ROW_RF_POWER_STATION: "ei_rf_power_station",
    REF_ROW_RF_GDP: "ei_rf_gdp",
    REF_ROW_RF_GDP_INTENSITY: "ei_rf_gdp_intensity",
}

REF_ROW_RF_SOURCE_ENDPOINT: dict[str, str] = {
    REF_ROW_RF_VED_CONSUMPTION: "economics_bp.ved_consumption",
    REF_ROW_RF_NETWORK_LOSSES: "economics_bp.ved_consumption",
    REF_ROW_RF_POWER_STATION: "economics_bp.ved_consumption",
    REF_ROW_RF_GDP: "economics_bp.product_output",
    REF_ROW_RF_GAES: "energy_consumption_bp.demand_summary_oes_gaes_charge",
}

REF_ROW_RF_SOURCE_PAGE_TITLE: dict[str, str] = {
    REF_ROW_RF_VED_CONSUMPTION: "Потребление ЭЭ по ВЭД",
    REF_ROW_RF_NETWORK_LOSSES: "Потребление ЭЭ по ВЭД",
    REF_ROW_RF_POWER_STATION: "Потребление ЭЭ по ВЭД",
    REF_ROW_RF_GDP: "Выпуск продукции",
    REF_ROW_RF_GAES: "ГАЭС на заряд",
}

EI_RF_TOTAL_CONSUMPTION_FORMULA_TOOLTIP = (
    "Потребление ЭЭ = Потребление (полезное) суммарно по ВЭД + потери в сетях + "
    "с.н. эл.станций (сумма соответствующих строк блока РФ), млрд кВт·ч."
)

EI_RF_GROWTH_RATE_FORMULA_TOOLTIP = (
    "Темп прироста, % = (Потребление ЭЭ за текущий год / Потребление ЭЭ за предыдущий год) "
    "× 100 − 100."
)

EI_RF_SUMMARY_VED_CONSUMPTION_FORMULA_TOOLTIP = (
    "Потребление (полезное) суммарно по ВЭД = сумма строк «Потребление ээ» по ВЭД "
    "для РФ (включая потребление ээ в домашних хозяйствах) / 1000, млрд кВт·ч."
)

EI_RF_POP_HOUSEHOLD_CONSUMPTION_FORMULA_TOOLTIP = (
    "Потребление ээ в домашних хозяйствах = сумма строк «Домашние хозяйства» "
    "по всем федеральным округам, млн кВт·ч."
)

EI_RF_POP_POPULATION_FORMULA_TOOLTIP = (
    "Численность населения (на начало года) = сумма значений по всем "
    "федеральным округам, тыс. чел."
)

EI_RF_POP_PER_CAPITA_FORMULA_TOOLTIP = (
    "Потребление ээ на душу населения, тыс. кВт·ч/чел. = Потребление ээ в домашних "
    "хозяйствах / Численность населения (на начало года) "
    "(потребление — млн кВт·ч, численность — тыс. чел.)."
)

EI_RF_GAES_FORMULA_TOOLTIP = (
    "ГАЭС = значение строки «Потребление электрической энергии ГАЭС на заряд, млн кВт·ч "
    "(всего)» со страницы «ГАЭС на заряд» / 1000, млрд кВт·ч."
)

EI_RF_CONSUMPTION_WITHOUT_GAES_FORMULA_TOOLTIP = (
    "Потребление без ГАЭС = Потребление (полезное) суммарно по ВЭД − ГАЭС, млрд кВт·ч."
)

EI_RF_NETWORK_LOSSES_FORMULA_TOOLTIP = (
    "потери в сетях = значение строки «Потери в сетях» для РФ со страницы "
    "«Потребление ЭЭ по ВЭД» / 1000, млрд кВт·ч."
)

EI_RF_POWER_STATION_FORMULA_TOOLTIP = (
    "с.н. эл.станций = значение строки «С.н. электростанций» для РФ со страницы "
    "«Потребление ЭЭ по ВЭД» / 1000, млрд кВт·ч."
)

EI_RF_GDP_FORMULA_TOOLTIP = (
    "ВВП = сумма строк «Выпуск продукции» по всем ВЭД "
    "по всем федеральным округам / 1000, млрд руб."
)

EI_RF_GDP_INTENSITY_FORMULA_TOOLTIP = (
    "Электроемкость ВВП, кВт·ч/тыс. руб. = Потребление ЭЭ / ВВП "
    "(потребление — млрд кВт·ч, ВВП — млрд руб.; пересчёт в кВт·ч/тыс. руб. "
    "как для строки «Электроемкость»)."
)

# Строки секций ВЭД на уровне РФ (агрегат по ФО).
RF_VED_REF_ROW_KINDS: tuple[str, ...] = (
    REF_ROW_CONSUMPTION,
    REF_ROW_PRODUCT_OUTPUT,
)

RF_VED_INTENSITY_ROW_LABEL = "Электроемкость ВЭД"


def rf_ved_product_output_row_label(price_year: int | None) -> str:
    return REF_ROW_LABEL_BY_KIND[REF_ROW_PRODUCT_OUTPUT]


REF_ROW_RF_VED_UNIT_BY_KIND: dict[str, str] = {
    REF_ROW_CONSUMPTION: "млн кВт.ч.",
    REF_ROW_PRODUCT_OUTPUT: "млрд руб.",
}

REF_ROW_RF_VED_FORMULA_KEY_BY_KIND: dict[str, str] = {
    REF_ROW_CONSUMPTION: "ei_rf_ved_consumption",
    REF_ROW_PRODUCT_OUTPUT: "ei_rf_ved_product_output",
}

EI_RF_VED_CONSUMPTION_FORMULA_TOOLTIP = (
    "Потребление ээ = сумма строк «Потребление ээ» по данному ВЭД "
    "по всем федеральным округам, млн кВт·ч."
)

EI_RF_VED_PRODUCT_OUTPUT_FORMULA_TOOLTIP = (
    "Выпуск продукции = сумма строк «Выпуск продукции» по данному ВЭД "
    "по всем федеральным округам / 1000, млрд руб."
)

EI_RF_VED_INTENSITY_FORMULA_TOOLTIP = (
    "Электроемкость ВЭД, кВт·ч/тыс. руб. = сумма строк «Электроемкость» "
    "по данному ВЭД по всем федеральным округам."
)
