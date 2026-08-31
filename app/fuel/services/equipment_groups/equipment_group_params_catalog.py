# -*- coding: utf-8 -*-
"""
Справочник параметров групп оборудования (модуль «Топливо»).

Содержимое перенесено из canvas fuel-equipment-group-params:
код поля, смысл, единицы, модель и формулы.
"""

from __future__ import annotations

from typing import Any

PARAM_GROUPS: tuple[str, ...] = (
    "Удельные показатели",
    "Мощность и часы",
    "Энергобаланс ЭЭ",
    "Тепло",
    "Топливо (сумма и виды)",
    "Идентификаторы",
    "Промежуточные (не в БД)",
)

KIND_LABELS: dict[str, str] = {
    "input": "вход",
    "calc": "расчёт",
    "both": "вход + *_calc",
    "id": "идентификатор",
    "intermediate": "промежуточный",
}

UNIT_CONF_LABELS: dict[str, str] = {
    "confirmed": "ед. из кода",
    "inferred": "ед. по формуле",
    "unknown": "ед. неясна",
}

# Цепочка энергоблока (напоминание) — как в canvas.
ENERGY_BLOCK_CHAIN: tuple[dict[str, str], ...] = (
    {"step": "1", "result": "ewtp", "formula": "qotr · y / 1000", "unit": "тыс. кВт·ч"},
    {"step": "2", "result": "snk", "formula": "sn_ee / e · 100", "unit": "%"},
    {"step": "3", "result": "ekotp", "formula": "(e − ewtp) · (1 − snk/100)", "unit": "тыс. кВт·ч"},
    {"step": "4", "result": "etpotp", "formula": "ewtp · sntp", "unit": "тыс. кВт·ч"},
    {"step": "5", "result": "eotp", "formula": "ekotp + etpotp", "unit": "тыс. кВт·ч"},
    {"step": "6", "result": "eust", "formula": "(ekotp · bk + etpotp · btp) / 1000", "unit": "т у.т."},
    {"step": "7", "result": "eurt", "formula": "eust / eotp · 1000", "unit": "г у.т./кВт·ч"},
    {"step": "8", "result": "sn_t", "formula": "sn_te / q · 1000", "unit": "кВт·ч/Гкал"},
    {"step": "9", "result": "tust", "formula": "q · turt / 1000", "unit": "т у.т."},
    {"step": "10", "result": "b", "formula": "eust + tust", "unit": "т у.т."},
)

EQUIPMENT_GROUP_PARAMS: tuple[dict[str, Any], ...] = (
    # --- Удельные показатели ---
    {
        "code": "y",
        "access": "y",
        "label": "Удельная выработка эл.эн. на тепловом потреблении",
        "meaning": (
            "Сколько электроэнергии вырабатывается на единицу тепла отборов турбин "
            "(теплофикационная удельная выработка)."
        ),
        "unit": "кВт·ч/Гкал",
        "unit_conf": "confirmed",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "both",
        "formula": "y_calc = EWTP / QOTR · 1000",
        "notes": "Вход для ewtp = qotr · y / 1000",
    },
    {
        "code": "btp",
        "access": "btp",
        "label": "УРУТ на отпуск ЭЭ в теплофикационном режиме",
        "meaning": (
            "Удельный расход условного топлива на отпущенную электроэнергию, "
            "выработанную в теплофикационном режиме."
        ),
        "unit": "г у.т./кВтч",
        "unit_conf": "confirmed",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "both",
        "formula": "btp_calc = EURT − K · (1 − EWTP/E) · 100",
        "notes": (
            "Не путать с тут/кВтч (тонны). Вход EUST: … + etpotp · btp. "
            "Типичные значения ~180–400."
        ),
    },
    {
        "code": "bk",
        "access": "Bk",
        "label": "Удельный расход усл.топлива на отпуск эл.эн. в конд.режиме",
        "meaning": (
            "Удельный расход условного топлива на отпущенную электроэнергию "
            "в конденсационном режиме."
        ),
        "unit": "г у.т./кВт·ч",
        "unit_conf": "inferred",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "both",
        "formula": "bk_calc зависит от eust, ewtp, sntp_calc, btp_calc, snk",
        "notes": "Вход EUST: ekotp · bk + …",
    },
    {
        "code": "sntp",
        "access": "sntp",
        "label": "Эл.энергия на собственные нужды в теплофик.режиме",
        "meaning": (
            "Доля (коэффициент) отпуска ЭЭ от теплофикационной выработки "
            "после учёта СН в теплофикационном режиме."
        ),
        "unit": "доля (безразм.)",
        "unit_conf": "inferred",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "both",
        "formula": "etpotp = ewtp · sntp",
        "notes": "В данных обычно ~0,6–0,9. Не проценты.",
    },
    {
        "code": "snk",
        "access": "snk / SNK",
        "label": "СН на производство электроэнергии",
        "meaning": (
            "Собственные нужды на производство электроэнергии, % от выработки ЭЭ. "
            "Используется в энергобалансе: ekotp = (e − ewtp) · (1 − snk/100)."
        ),
        "unit": "%",
        "unit_conf": "confirmed",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption / FuelParam",
        "kind": "both",
        "formula": "snk = sn_ee / e · 100",
        "notes": (
            "Числитель — sn_ee (тыс. кВт·ч), знаменатель — выработка ЭЭ (e). "
            "Удельные: snk; Станции: SNK. snk_calc равен SNK топливных параметров "
            "(формула sn_ee / e · 100 или сохранённый FuelParam.snk). "
            "В энергоблоке: ekotp = (e − ewtp) · (1 − snk/100)."
        ),
    },
    {
        "code": "k",
        "access": "k",
        "label": "Коэффициент экономии от теплофикации",
        "meaning": (
            "Коэффициент, учитывающий экономию топлива за счёт комбинированной "
            "выработки (теплофикация)."
        ),
        "unit": "безразм.",
        "unit_conf": "confirmed",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "input",
        "formula": "используется только в btp_calc",
        "notes": "Привязан к году. На карточке группы — редактируемый вход.",
    },
    {
        "code": "snbas",
        "access": "snbas",
        "label": "Базовый СН (VED 1/4)",
        "meaning": "Базовый уровень собственных нужд для ветви расчёта VED ∈ {1, 4}.",
        "unit": "%",
        "unit_conf": "inferred",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "input",
        "formula": "sn_eff = snbas − hours_util · Ksn",
        "notes": "",
    },
    {
        "code": "ksn",
        "access": "Ksn",
        "label": "Наклон СН по часам (Ksn, VED 1/4)",
        "meaning": "Изменение СН в зависимости от часов использования установленной мощности.",
        "unit": "% / (отн. ч)",
        "unit_conf": "unknown",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "bbas",
        "access": "bbas",
        "label": "Базовый удельный расход (bbas, VED 1/4)",
        "meaning": "Базовый удельный расход топлива для ветви EUST при VED ∈ {1, 4}.",
        "unit": "г у.т./кВт·ч",
        "unit_conf": "inferred",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "kh",
        "access": "Kh",
        "label": "Наклон удельного расхода по часам (Kh, VED 1/4)",
        "meaning": "Изменение удельного расхода топлива в зависимости от часов использования.",
        "unit": "не уточнена",
        "unit_conf": "unknown",
        "group": "Удельные показатели",
        "model": "SpecificFuelConsumption",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    # --- Мощность и часы ---
    {
        "code": "nust",
        "access": "NUST",
        "label": "Руст — установленная мощность",
        "meaning": "Установленная электрическая мощность группы оборудования.",
        "unit": "МВт",
        "unit_conf": "inferred",
        "group": "Мощность и часы",
        "model": "FuelParam",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "nr",
        "access": "NR",
        "label": "Ррасп — располагаемая мощность",
        "meaning": "Располагаемая электрическая мощность.",
        "unit": "МВт",
        "unit_conf": "inferred",
        "group": "Мощность и часы",
        "model": "FuelParam",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "h",
        "access": "H",
        "label": "Часы использования установленной мощности (H)",
        "meaning": "Число часов использования установленной мощности за год (Access H).",
        "unit": "ч",
        "unit_conf": "inferred",
        "group": "Мощность и часы",
        "model": "FuelParam",
        "kind": "both",
        "formula": "h = e / nust · 1000  (если nust > 0; при hfix=1 — вручную)",
        "notes": "Access calce: согласование часов с выработкой. hfix=1 фиксирует значение.",
    },
    {
        "code": "hfix",
        "access": "HFIX",
        "label": "Фиксация часов (HFIX)",
        "meaning": "Флаг: не пересчитывать H формулой распределения.",
        "unit": "0/1",
        "unit_conf": "confirmed",
        "group": "Мощность и часы",
        "model": "FuelParam",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "nt",
        "access": "NT",
        "label": "Тепловая мощность отборов",
        "meaning": "Тепловая мощность отборов турбин.",
        "unit": "Гкал/ч",
        "unit_conf": "confirmed",
        "group": "Мощность и часы",
        "model": "FuelParam",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "nt_sum",
        "access": "NTsum",
        "label": "Сумма NT",
        "meaning": "Суммарная тепловая мощность отборов.",
        "unit": "Гкал/ч",
        "unit_conf": "confirmed",
        "group": "Мощность и часы",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "",
        "notes": "",
    },
    # --- Энергобаланс ЭЭ ---
    {
        "code": "e",
        "access": "E",
        "label": "Выработка ЭЭ",
        "meaning": "Выработка электроэнергии группой оборудования за год.",
        "unit": "млн кВтч",
        "unit_conf": "confirmed",
        "group": "Энергобаланс ЭЭ",
        "model": "FuelParam",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "ewtp",
        "access": "EWTP",
        "label": "Теплофикационная выработка ЭЭ (Этц)",
        "meaning": "Часть выработки ЭЭ, относящаяся к теплофикационному режиму (отборы).",
        "unit": "тыс. кВт·ч",
        "unit_conf": "confirmed",
        "group": "Энергобаланс ЭЭ",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "ewtp = qotr · y / 1000",
        "notes": "",
    },
    {
        "code": "eotp",
        "access": "EOTP",
        "label": "Отпуск электроэнергии",
        "meaning": "Отпуск ЭЭ с шин (после СН) — сумма конденсационного и теплофикационного отпуска.",
        "unit": "млн кВтч",
        "unit_conf": "inferred",
        "group": "Энергобаланс ЭЭ",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "eotp = ekotp + etpotp",
        "notes": "",
    },
    {
        "code": "eurt",
        "access": "EURT",
        "label": "Удельный расход топлива на отпуск ЭЭ",
        "meaning": "Средний удельный расход условного топлива на отпущенную электроэнергию.",
        "unit": "г у.т./кВт·ч",
        "unit_conf": "inferred",
        "group": "Энергобаланс ЭЭ",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "eurt = eust / eotp · 1000  (если eotp ≠ 0)",
        "notes": "",
    },
    {
        "code": "eust",
        "access": "EUST",
        "label": "Расход топлива на электроэнергию",
        "meaning": "Абсолютный расход условного топлива, относимый на выработку/отпуск ЭЭ.",
        "unit": "т у.т.",
        "unit_conf": "inferred",
        "group": "Энергобаланс ЭЭ",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "eust = (ekotp · bk + etpotp · btp) / 1000",
        "notes": "При VED∈{1,4} — ветвь bbas/Kh.",
    },
    {
        "code": "sn_ee",
        "access": "SN_EE",
        "label": "СН на производство электроэнергии",
        "meaning": (
            "Абсолютные собственные нужды на производство электроэнергии "
            "(С н.ээ). Числитель для расчёта snk."
        ),
        "unit": "тыс. кВт·ч",
        "unit_conf": "confirmed",
        "group": "Энергобаланс ЭЭ",
        "model": "FuelParam",
        "kind": "input",
        "formula": "snk = sn_ee / e · 100",
        "notes": "Вход для snk (%).",
    },
    # --- Тепло ---
    {
        "code": "q",
        "access": "Q",
        "label": "Отпуск тепловой энергии",
        "meaning": "Отпуск тепла потребителям.",
        "unit": "Гкал",
        "unit_conf": "confirmed",
        "group": "Тепло",
        "model": "FuelParam",
        "kind": "input",
        "formula": "",
        "notes": "",
    },
    {
        "code": "qotr",
        "access": "QOTR",
        "label": "Тепловое потребление (отборов турбин)",
        "meaning": "Тепло, отобранное из турбин (отработавшее тепло отборов).",
        "unit": "тыс. Гкал",
        "unit_conf": "confirmed",
        "group": "Тепло",
        "model": "FuelParam",
        "kind": "input",
        "formula": "",
        "notes": "Вход для расчёта ewtp.",
    },
    {
        "code": "turt",
        "access": "TURT",
        "label": "Удельный расход топлива на тепло",
        "meaning": "Удельный расход условного топлива на отпуск тепловой энергии.",
        "unit": "кг у.т./Гкал",
        "unit_conf": "inferred",
        "group": "Тепло",
        "model": "FuelParam",
        "kind": "both",
        "formula": "turt = tust / q · 1000  (если q ≠ 0); иначе ручной ввод. Связь: tust = q · turt / 1000",
        "notes": "На странице «Сведения о работе ТЭС» считается из tust и q при наличии данных.",
    },
    {
        "code": "tust",
        "access": "TUST",
        "label": "Расход топлива на тепло",
        "meaning": "Абсолютный расход условного топлива на отпуск тепла.",
        "unit": "т у.т.",
        "unit_conf": "inferred",
        "group": "Тепло",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "tust = q · turt / 1000",
        "notes": "",
    },
    {
        "code": "sn_te",
        "access": "SN_TE",
        "label": "СН на отпуск тепловой энергии",
        "meaning": (
            "Абсолютные собственные нужды на отпуск тепловой энергии. "
            "Числитель для расчёта sn_t (SNT)."
        ),
        "unit": "тыс. кВт·ч",
        "unit_conf": "confirmed",
        "group": "Тепло",
        "model": "FuelParam",
        "kind": "input",
        "formula": "sn_t = sn_te / q · 1000",
        "notes": "Вход для sn_t / SNT (кВт·ч/Гкал).",
    },
    {
        "code": "sn_t",
        "access": "SNT",
        "label": "СН на отпуск тепла",
        "meaning": "Удельные собственные нужды, относимые на отпуск тепла.",
        "unit": "кВт·ч/Гкал",
        "unit_conf": "confirmed",
        "group": "Тепло",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "sn_t = sn_te / q · 1000",
        "notes": (
            "Числитель — sn_te (тыс. кВт·ч), знаменатель — отпуск тепловой энергии (q). "
            "В формах Access — SNT."
        ),
    },
    # --- Топливо ---
    {
        "code": "b",
        "access": "B",
        "label": "Расход топлива, всего",
        "meaning": "Суммарный расход условного топлива (ЭЭ + тепло). База для разложения по formtxt.",
        "unit": "т у.т.",
        "unit_conf": "inferred",
        "group": "Топливо (сумма и виды)",
        "model": "FuelParam",
        "kind": "calc",
        "formula": "b = eust + tust",
        "notes": "",
    },
    {
        "code": "gaz / isk_gaz / mazut / torf / slan / proch / ugol",
        "access": "GAZ / ISK_GAZ / MAZUT / TORF / SLAN / PROCH / UGOL",
        "label": "Расход по видам топлива (агрегаты)",
        "meaning": (
            "Разложение b по видам: газ, искусственный газ, мазут, торф, сланцы, прочее, уголь (сумма)."
        ),
        "unit": "т у.т.",
        "unit_conf": "inferred",
        "group": "Топливо (сумма и виды)",
        "model": "FuelParam",
        "kind": "both",
        "formula": "",
        "notes": (
            "Дальнейшая детализация — ExtraFuelParam (gaz_prir, kuzngd, …) "
            "и региональные угли (don…sah)."
        ),
    },
    {
        "code": "don … sah",
        "access": "DON … SAH",
        "label": "Региональные угли (Дон, Подм, Кузбасс, … Сахалин)",
        "meaning": "Расход условного топлива по бассейнам/регионам угля.",
        "unit": "т у.т.",
        "unit_conf": "inferred",
        "group": "Топливо (сумма и виды)",
        "model": "FuelParam",
        "kind": "both",
        "formula": "",
        "notes": (
            "Access: DON, PODM, PECH, ALT, KUZN, URAL, BASHK, KAZAH, KAN, TUNG, IRKUT, "
            "HAK, TUV, BUR, CHIT, TAL, AMUR, URG, USHUM, PRIM, YAKUT, MAG, KAMCH, CHUKOT, SAH."
        ),
    },
    # --- Идентификаторы ---
    {
        "code": "numb1120",
        "access": "NUMB1120 / numb1120",
        "label": "Код электростанции / группы",
        "meaning": "Код группы оборудования (= EquipmentGroup.numb). Ключ связи удельных и параметров.",
        "unit": "—",
        "unit_conf": "confirmed",
        "group": "Идентификаторы",
        "model": "FuelParam / Specific / Group",
        "kind": "id",
        "formula": "",
        "notes": "Станции: NUMB1120; Удельные: numb1120.",
    },
    {
        "code": "year_number",
        "access": "YEAR / year",
        "label": "Год",
        "meaning": "Расчётный/отчётный год строки параметров.",
        "unit": "год",
        "unit_conf": "confirmed",
        "group": "Идентификаторы",
        "model": "FuelParam / Specific",
        "kind": "id",
        "formula": "",
        "notes": "Станции: YEAR; Удельные: year.",
    },
    {
        "code": "ved",
        "access": "VED",
        "label": "Тип ТЭС (VED)",
        "meaning": (
            "Рабочий код Access «Станции(Схема).VED» за год: "
            "0 — оболочка родителя составной станции (не входит в Σ при ved>0); "
            "1 — КЭС, отрасль; 2 — ТЭЦ, отрасль; "
            "3 — ТЭЦ, промпредприятия; 4 — КЭС, промпредприятия; "
            "99 — родитель помечен к разбиению, группы ещё не вставлены. "
            "Не путать с EquipmentGroup.vedomstvo (1 отрасль / 2 пром)."
        ),
        "unit": "код",
        "unit_conf": "confirmed",
        "group": "Идентификаторы",
        "model": "FuelParam",
        "kind": "id",
        "formula": "",
        "notes": "Ветвь удельных EUST при VED∈{1,4}; отбор расчёта — (ved>0).",
    },
    {
        "code": "obor / obl / dep / oes / er / gk / be",
        "access": "OBOR / OBL / DEP / OES / ER / GK / BE",
        "label": "Территория и оргструктура",
        "meaning": "Группа оборудования (obor), субъект РФ, департамент, ОЭС, экон. район, ГК, тип ГК.",
        "unit": "коды EM",
        "unit_conf": "confirmed",
        "group": "Идентификаторы",
        "model": "FuelParam / EquipmentGroup",
        "kind": "id",
        "formula": "",
        "notes": "",
    },
    # --- Промежуточные ---
    {
        "code": "ekotp",
        "access": "ekotp",
        "label": "Отпуск ЭЭ конденсационного режима",
        "meaning": "Отпуск электроэнергии после СН от конденсационной части выработки.",
        "unit": "тыс. кВт·ч",
        "unit_conf": "inferred",
        "group": "Промежуточные (не в БД)",
        "model": "расчёт (_calculate_energy_part)",
        "kind": "intermediate",
        "formula": "ekotp = (e − ewtp) · (1 − sn_eff/100)",
        "notes": "В Access — локальная переменная VBA, не колонка таблицы.",
    },
    {
        "code": "etpotp",
        "access": "etpotp",
        "label": "Отпуск ЭЭ теплофикационного режима",
        "meaning": "Отпуск электроэнергии от теплофикационной выработки.",
        "unit": "тыс. кВт·ч",
        "unit_conf": "inferred",
        "group": "Промежуточные (не в БД)",
        "model": "расчёт (_calculate_energy_part)",
        "kind": "intermediate",
        "formula": "etpotp = ewtp · sntp",
        "notes": "В Access — локальная переменная VBA, не колонка таблицы.",
    },
    {
        "code": "hours_util",
        "access": "(E/NUST)/8.76",
        "label": "Относительные часы использования",
        "meaning": "Вспомогательная величина для ветви VED 1/4 (СН и удельный расход).",
        "unit": "безразм.",
        "unit_conf": "inferred",
        "group": "Промежуточные (не в БД)",
        "model": "расчёт",
        "kind": "intermediate",
        "formula": "hours_util = (E / NUST) / 8.76",
        "notes": "В Access выражение inline в формуле, отдельного поля нет.",
    },
)


def list_equipment_group_params_for_page() -> list[dict[str, Any]]:
    """Строки каталога с подписями для шаблона."""
    rows: list[dict[str, Any]] = []
    for p in EQUIPMENT_GROUP_PARAMS:
        unit_conf = str(p.get("unit_conf") or "unknown")
        kind = str(p.get("kind") or "")
        formula = str(p.get("formula") or "").strip()
        notes = str(p.get("notes") or "").strip()
        formula_notes = " · ".join(x for x in (formula, notes) if x) or "—"
        rows.append(
            {
                **p,
                "kind_label": KIND_LABELS.get(kind, kind),
                "unit_conf_label": UNIT_CONF_LABELS.get(unit_conf, unit_conf),
                "formula_notes": formula_notes,
            }
        )
    return rows


def params_catalog_stats() -> dict[str, int]:
    confirmed = sum(1 for p in EQUIPMENT_GROUP_PARAMS if p.get("unit_conf") == "confirmed")
    inferred = sum(1 for p in EQUIPMENT_GROUP_PARAMS if p.get("unit_conf") == "inferred")
    unknown = sum(1 for p in EQUIPMENT_GROUP_PARAMS if p.get("unit_conf") == "unknown")
    return {
        "total": len(EQUIPMENT_GROUP_PARAMS),
        "confirmed": confirmed,
        "inferred": inferred,
        "unknown": unknown,
    }
