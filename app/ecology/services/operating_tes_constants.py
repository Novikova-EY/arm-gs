# -*- coding: utf-8 -*-
"""Константы расчёта по действующим ТЭС (макет «перевод в натур через К»)."""
from __future__ import annotations
from decimal import Decimal
from typing import Any

KIND_VALUE = "value"
KIND_TOTAL = "total"

DEFAULT_TERRITORY_SLUG = "vsego"
DEFAULT_SHEET_SLUG = "obemy"

ROUNDING_DIGITS = 1
ROUNDING_CHOICES = (-1, 0, 1, 2, 3)
GCAL_TO_MWH = Decimal("1.163")

GROUP_TERRITORY = "territory"
GROUP_SPECIAL = "special"

TERRITORIES: tuple[dict[str, Any], ...] = (
    {'slug': 'vsego', 'sheet_name': 'Всего', 'group': 'territory'},
    {'slug': 'minen', 'sheet_name': 'МинЭн', 'group': 'special'},
    {'slug': 'prompred', 'sheet_name': 'ПромПред', 'group': 'special'},
    {'slug': 'severo-zapad', 'sheet_name': 'ОЭС Северо-Запада', 'group': 'territory'},
    {'slug': 'centr', 'sheet_name': 'ОЭС Центра', 'group': 'territory'},
    {'slug': 'srednyaya-volga', 'sheet_name': 'ОЭС Средней Волги', 'group': 'territory'},
    {'slug': 'yug', 'sheet_name': 'ОЭС Юга', 'group': 'territory'},
    {'slug': 'ural', 'sheet_name': 'ОЭС Урала', 'group': 'territory'},
    {'slug': 'sibir', 'sheet_name': 'ОЭС Сибири', 'group': 'territory'},
    {'slug': 'vostok', 'sheet_name': 'ОЭС Востока', 'group': 'territory'},
    {'slug': 'isolated-dv', 'sheet_name': 'Из.узлы Дальнего Востока', 'group': 'special'},
    {'slug': 'nikolaevsky', 'sheet_name': 'Николаевский э.р.', 'group': 'special'},
    {'slug': 'norilsk', 'sheet_name': 'Норильск.эн.р-н', 'group': 'special'},
)

CALC_SHEETS: tuple[dict[str, Any], ...] = (
    {'slug': 'toplivo', 'sheet_name': 'Данные по модулю Топливо', 'page_title': 'Топливные показатели (модуль Топливо)', 'unit': 'тыс.тут', 'layout': 'fuel'},
    {'slug': 'spravochnik', 'sheet_name': 'Справочник', 'page_title': 'Справочник характеристик топлива', 'unit': '', 'layout': 'spravochnik'},
    {'slug': 'khar-topl', 'sheet_name': 'Характеристики', 'page_title': 'Характеристика топлив, продуктов сгорания, удельных выбросов', 'unit': '', 'layout': 'chars'},
    {'slug': 'koeff', 'sheet_name': 'Коэффициенты', 'unit': '', 'layout': 'coeff'},
    {'slug': 'zola', 'sheet_name': 'Зола', 'page_title': 'Выбросы твердых веществ в атмосферу', 'unit': 'тыс. т', 'layout': 'emission'},
    {'slug': 'sera', 'sheet_name': 'Сера', 'page_title': 'Выбросы диоксидов серы МвыбSO2, тыс.т/год', 'unit': 'тыс. т', 'layout': 'emission'},
    {'slug': 'azot', 'sheet_name': 'Азот', 'page_title': 'Выбросы оксидов азота в атмосферу МвыбNOx, тыс.т/год', 'unit': 'тыс. т', 'layout': 'emission'},
    {'slug': 'co', 'sheet_name': 'CO', 'page_title': 'Выбросы монооксидов углерода в атмосферу МвыбCO, т/год', 'unit': 'т', 'layout': 'emission'},
    {'slug': 'pg', 'sheet_name': 'ПГ', 'page_title': 'Выбросы ПАРНИКОВЫХ ГАЗОВ (оксидов углерода) в атмосферу МвыбCO2, тыс.т/год', 'unit': 'тыс. т', 'layout': 'emission'},
    {'slug': 'pg-tj', 'sheet_name': 'ПГ через ТДж', 'page_title': 'Выбросы ПАРНИКОВЫХ ГАЗОВ (оксидов углерода) в атмосферу МвыбCO2, млн т/год', 'unit': 'млн т', 'layout': 'emission_tj'},
    {'slug': 'obemy', 'sheet_name': 'Объемы', 'unit': 'тыс. т', 'layout': 'volumes'},
    {'slug': 'udel-e', 'sheet_name': 'Удельные по привед Э', 'unit': 'г/кВт·ч', 'layout': 'specific_e'},
    {'slug': 'udel-fuel', 'sheet_name': 'Удельные по топл', 'unit': 'кг/тут', 'layout': 'specific_fuel'},
    {'slug': 'udel-ee', 'sheet_name': 'Удельные только по ЭЭ', 'unit': 'г/кВт·ч', 'layout': 'specific_ee'},
)

# Отображение листов выбросов как в xls: два столбца на территорию (Зола/Сера/CO/ПГ через ТДж)
# или один (Азот без n, ПГ = В*Kco2). Мотх. — до улавливания; КПД применяется на «Объемах».
EMISSION_SHEET_VIEW: dict[str, dict[str, Any]] = {
    'zola': {
        'kind': 'pair',
        'left_metric': 'bn',
        'right_metric': 'ash_motkh',
        'left_title': 'Перевод в натур.',
        'right_title': 'Мотх.',
        'formula': 'Мотх=0,01*ВН(аун Ар +qч*Qн/32680)',
        'show_unit_column': False,
    },
    'sera': {
        'kind': 'pair',
        'left_metric': 'bn',
        'right_metric': 'so2_motkh',
        'left_title': 'Перевод в натур.',
        'right_title': 'Мотх.',
        'formula': 'Мотх=0,02*ВН*Sp(1-x)',
        'show_unit_column': False,
    },
    'azot': {
        'kind': 'single',
        'metric': 'nox_raw',
        'col_title': '0,001*В*(1-qч /100)*b',
        'formula': 'МотхNOx=0,001*В*(1-qч/100)*(1-n)*b',
        'show_unit_column': False,
    },
    'co': {
        'kind': 'pair',
        'left_metric': 'bn',
        'right_metric': 'co_motkh',
        'left_title': 'Перевод в натур.',
        'right_title': 'Мотх.',
        'formula': 'Мотхco=0,001*Вн*(q3*R*Qн/1013)*(1-q4/100)',
        'show_unit_column': False,
    },
    'pg': {
        'kind': 'single',
        'metric': 'pg_motkh',
        'col_title': 'В*Kco2',
        'formula': 'Мотхco2=В*Kco2',
        'show_unit_column': False,
    },
    'pg-tj': {
        'kind': 'pair',
        'left_metric': 'energy_tj',
        'right_metric': 'pg_tj_motkh',
        'left_title': 'МДж',
        'right_title': 'В*Kco2',
        'formula': 'Qн*Вн/10^6',
        'show_unit_column': False,
    },
}

# Ключи строк макета → Fuel.nazvl / колонки gs_fue (справочник /refdata/fuel).
# Агрегаты (gaz, isk_gaz, mazut, бассейны) — EquipmentGroupFuelParam;
# листья (gaz_prir, domen_g, kuzngd, …) — EquipmentGroupExtraFuelParam.
FUEL_PARAM_FIELDS: dict[str, str] = {
    "gas": "gaz",
    "gas_natural": "gaz_prir",
    "gas_associated": "gazpp",
    "gas_artificial": "isk_gaz",
    "blast_furnace_gas": "domen_g",
    "coke_oven_gas": "koks_g",
    "npz_gas": "prochgaz",
    "oil_fuel": "mazut",
    "mazut": "maztop",
    "diesel": "disel",
    "other_oil": "nft_proch",
    "peat": "torf",
    "other_fuel": "proch",
    "other_solid": "tvproch",
    "lpg": "szh_gaz",
    "other_misc": "inoe",
    "coal": "ugol",
    "donetsk": "don",
    "moscow": "podm",
    "pechora": "pech",
    "inta": "intin",
    "vorkuta": "vork",
    "kuznetsk": "kuzn",
    "kuzn_gd": "kuzngd",
    "kuzn_t": "kuznt",
    "kuzn_ss": "kuznss",
    "kuzn_other": "kuznun",
    "ural": "ural",
    "sverdlovsk": "sver",
    "chelyabinsk": "chel",
    "kizel": "kizel",
    "bashkir": "bashk",
    "kansk_achinsk": "kan",
    "nazarov": "nazar",
    "borodino": "ibor",
    "berezovsky": "berez",
    "pereyaslav": "per",
    "irbey": "irbei",
    "kansk": "kansk",
    "tungus": "tung",
    "zheron": "jer",
    "karabul": "karab",
    "irkutsk": "irkut",
    "azey": "azey",
    "mugun": "mug",
    "cheremkhovo": "cher",
    "khakass": "hak",
    "tuva": "tuv",
    "buryat": "bur",
    "gusinoozersk": "gusin",
    "tugnuy": "tugn",
    "okino": "okino",
    "zabaykal": "chit",
    "kharanor": "har",
    "urtuy": "urt",
    "tataurovo": "tataur",
    "tarbagatai": "tarbag",
    "zab_hard": "zab_kam",
    "yakut": "yakut",
    "nerungri": "neru",
    "zyryan": "zyryan",
    "yakut_other": "pyak",
    "amur": "amur",
    "raychikhinsk": "rai",
    "erkovets": "erk",
    "ogodzha": "ogodj",
    "urgal": "urg",
    "ushumun": "ushum",
    "primorye": "prim",
    "bikin": "bikin",
    "razdolnensky": "razdol",
    "khanka": "hankai",
    "magadan": "mag",
    "sakhalin": "sah",
    "kamchatka": "kamch",
    "chukotka": "chukot",
    "anadyr": "anad",
    "beringovsky": "bering",
    "kazakhstan": "kazah",
    "ekibastuz": "ekib",
    "maikuben": "maikub",
    "karaganda": "karag",
    "karazhyra": "karajyra",
    "teniz": "teniz",
}

FUEL_MAIN_SUM_FIELDS: tuple[str, ...] = (
    "e",
    "q",
    "b",
    "gaz",
    "isk_gaz",
    "mazut",
    "torf",
    "proch",
    "slan",
    "ugol",
    "arkt",
    "don",
    "podm",
    "pech",
    "kuzn",
    "ural",
    "bashk",
    "kan",
    "tung",
    "irkut",
    "hak",
    "tuv",
    "bur",
    "chit",
    "yakut",
    "amur",
    "urg",
    "ushum",
    "prim",
    "mag",
    "sah",
    "kamch",
    "chukot",
    "kazah",
)

FUEL_EXTRA_SUM_FIELDS: tuple[str, ...] = (
    "gaz_prir",
    "gazpp",
    "disel",
    "maztop",
    "nft_proch",
    "domen_g",
    "koks_g",
    "prochgaz",
    "tvproch",
    "szh_gaz",
    "inoe",
    "nazar",
    "ibor",
    "berez",
    "per",
    "irbei",
    "kansk",
    "gusin",
    "tugn",
    "okino",
    "azey",
    "mug",
    "cher",
    "jer",
    "karab",
    "vork",
    "intin",
    "sver",
    "chel",
    "kizel",
    "har",
    "urt",
    "tataur",
    "tarbag",
    "zab_kam",
    "rai",
    "erk",
    "ogodj",
    "bikin",
    "razdol",
    "hankai",
    "neru",
    "zyryan",
    "pyak",
    "kuzngd",
    "kuznt",
    "kuznss",
    "kuznun",
    "bering",
    "anad",
    "ekib",
    "maikub",
    "karag",
    "karajyra",
    "teniz",
)

VED_INDUSTRY = frozenset({1, 2})  # КЭС/ТЭЦ отрасль → МинЭн
VED_INDUSTRIAL = frozenset({3, 4})  # ТЭЦ/КЭС промпредприятия
VED_PARENT_SHELL = 0

TOP_INPUT_FIELD = {
    "ee_generation": "e",
    "heat_output": "q",
    "fuel_total": "b",
}

FUEL_ROWS: tuple[dict[str, Any], ...] = (
    {'key': 'gas', 'label': 'Газ', 'indent': 0, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': None, 'children': ('gas_natural', 'gas_associated')},
    {'key': 'gas_natural', 'label': 'природный газ', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'gas', 'children': ()},
    {'key': 'gas_associated', 'label': 'попутный газ', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'gas', 'children': ()},
    {'key': 'gas_artificial', 'label': 'Газ искуственный', 'indent': 0, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': None, 'children': ('blast_furnace_gas', 'coke_oven_gas', 'npz_gas')},
    {'key': 'blast_furnace_gas', 'label': 'доменый газ', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'gas_artificial', 'children': ()},
    {'key': 'coke_oven_gas', 'label': 'коксовый газ', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'gas_artificial', 'children': ()},
    {'key': 'npz_gas', 'label': 'газ НПЗ (прочий газ)', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'gas_artificial', 'children': ()},
    {'key': 'oil_fuel', 'label': 'Нефтетопливо', 'indent': 0, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': None, 'children': ('mazut', 'diesel', 'other_oil')},
    {'key': 'mazut', 'label': 'мазут топочный', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'oil_fuel', 'children': ()},
    {'key': 'diesel', 'label': 'дизель', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'oil_fuel', 'children': ()},
    {'key': 'other_oil', 'label': 'прочее нефтетопливо', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'oil_fuel', 'children': ()},
    {'key': 'peat', 'label': 'Торф', 'indent': 0, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': None, 'children': ()},
    {'key': 'other_fuel', 'label': 'Прочее топливо', 'indent': 0, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': None, 'children': ('other_solid', 'lpg', 'other_misc')},
    {'key': 'other_solid', 'label': 'тв.топливо', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'other_fuel', 'children': ()},
    {'key': 'lpg', 'label': 'сжиженый газ', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'other_fuel', 'children': ()},
    {'key': 'other_misc', 'label': 'иное прочее топливо', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'other_fuel', 'children': ()},
    {'key': 'coal', 'label': 'Уголь', 'indent': 0, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': None, 'children': ('donetsk', 'moscow', 'pechora', 'kuznetsk', 'ural', 'bashkir', 'kansk_achinsk', 'tungus', 'irkutsk', 'khakass', 'tuva', 'buryat', 'zabaykal', 'yakut', 'amur', 'urgal', 'ushumun', 'primorye', 'magadan', 'sakhalin', 'kamchatka', 'chukotka', 'kazakhstan')},
    {'key': 'donetsk', 'label': 'Донецкий', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'moscow', 'label': 'Подмосковный', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'pechora', 'label': 'Печорский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('inta', 'vorkuta')},
    {'key': 'inta', 'label': 'интинский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'pechora', 'children': ()},
    {'key': 'vorkuta', 'label': 'воркутинский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'pechora', 'children': ()},
    {'key': 'kuznetsk', 'label': 'Кузнецкий', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('kuzn_gd', 'kuzn_t', 'kuzn_ss', 'kuzn_other')},
    {'key': 'kuzn_gd', 'label': 'кузнецкий Г,Д', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kuznetsk', 'children': ()},
    {'key': 'kuzn_t', 'label': 'кузнецкий Т', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kuznetsk', 'children': ()},
    {'key': 'kuzn_ss', 'label': 'кузнецкий СС', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kuznetsk', 'children': ()},
    {'key': 'kuzn_other', 'label': 'кузнецкий прочий', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kuznetsk', 'children': ()},
    {'key': 'ural', 'label': 'Уральский (буреинский)', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('sverdlovsk', 'chelyabinsk', 'kizel')},
    {'key': 'sverdlovsk', 'label': 'свердловский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'ural', 'children': ()},
    {'key': 'chelyabinsk', 'label': 'челябинский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'ural', 'children': ()},
    {'key': 'kizel', 'label': 'кизеловский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'ural', 'children': ()},
    {'key': 'bashkir', 'label': 'Башкирский (Южно-Уральский)', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'kansk_achinsk', 'label': 'Канско-ачинский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('nazarov', 'borodino', 'berezovsky', 'pereyaslav', 'irbey', 'kansk')},
    {'key': 'nazarov', 'label': 'назаровский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kansk_achinsk', 'children': ()},
    {'key': 'borodino', 'label': 'бородинский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kansk_achinsk', 'children': ()},
    {'key': 'berezovsky', 'label': 'березовский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kansk_achinsk', 'children': ()},
    {'key': 'pereyaslav', 'label': 'переяславский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kansk_achinsk', 'children': ()},
    {'key': 'irbey', 'label': 'ирбейский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kansk_achinsk', 'children': ()},
    {'key': 'kansk', 'label': 'канский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kansk_achinsk', 'children': ()},
    {'key': 'tungus', 'label': 'Тунгусский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('zheron', 'karabul')},
    {'key': 'zheron', 'label': 'жеронский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'tungus', 'children': ()},
    {'key': 'karabul', 'label': 'карабульский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'tungus', 'children': ()},
    {'key': 'irkutsk', 'label': 'Иркутский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('azey', 'mugun', 'cheremkhovo')},
    {'key': 'azey', 'label': 'азейский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'irkutsk', 'children': ()},
    {'key': 'mugun', 'label': 'мугунский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'irkutsk', 'children': ()},
    {'key': 'cheremkhovo', 'label': 'черемховский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'irkutsk', 'children': ()},
    {'key': 'khakass', 'label': 'Хакасский (минусинский)', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'tuva', 'label': 'Тувинский (Улуг-хемский)', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'buryat', 'label': 'Бурятский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('gusinoozersk', 'tugnuy', 'okino')},
    {'key': 'gusinoozersk', 'label': 'гусиноозерский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'buryat', 'children': ()},
    {'key': 'tugnuy', 'label': 'тугнуйский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'buryat', 'children': ()},
    {'key': 'okino', 'label': 'окино-ключевский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'buryat', 'children': ()},
    {'key': 'zabaykal', 'label': 'Забайкальский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('kharanor', 'urtuy', 'tataurovo', 'tarbagatai', 'zab_hard')},
    {'key': 'kharanor', 'label': 'харанорский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'zabaykal', 'children': ()},
    {'key': 'urtuy', 'label': 'уртуйский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'zabaykal', 'children': ()},
    {'key': 'tataurovo', 'label': 'татауровский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'zabaykal', 'children': ()},
    {'key': 'tarbagatai', 'label': 'тарабагатайский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'zabaykal', 'children': ()},
    {'key': 'zab_hard', 'label': 'забайкальский каменный', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'zabaykal', 'children': ()},
    {'key': 'yakut', 'label': 'Якутские', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('nerungri', 'zyryan', 'yakut_other')},
    {'key': 'nerungri', 'label': 'нерюнгринский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'yakut', 'children': ()},
    {'key': 'zyryan', 'label': 'зырянский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'yakut', 'children': ()},
    {'key': 'yakut_other', 'label': 'проч.якутские', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'yakut', 'children': ()},
    {'key': 'amur', 'label': 'Амурский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('raychikhinsk', 'erkovets', 'ogodzha')},
    {'key': 'raychikhinsk', 'label': 'райчихинский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'amur', 'children': ()},
    {'key': 'erkovets', 'label': 'ерковецкий', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'amur', 'children': ()},
    {'key': 'ogodzha', 'label': 'огоджинский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'amur', 'children': ()},
    {'key': 'urgal', 'label': 'Ургальский', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'ushumun', 'label': 'Ушумунский(средне-амурский)', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'primorye', 'label': 'Приморский', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('bikin', 'razdolnensky', 'khanka')},
    {'key': 'bikin', 'label': 'бикинский (лучегорский)', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'primorye', 'children': ()},
    {'key': 'razdolnensky', 'label': 'раздольненский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'primorye', 'children': ()},
    {'key': 'khanka', 'label': 'ханкайский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'primorye', 'children': ()},
    {'key': 'magadan', 'label': 'Магаданский', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'sakhalin', 'label': 'Сахалинский', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'kamchatka', 'label': 'Камчатский', 'indent': 1, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'coal', 'children': ()},
    {'key': 'chukotka', 'label': 'Чукотские', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('anadyr', 'beringovsky')},
    {'key': 'anadyr', 'label': 'анадырский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'chukotka', 'children': ()},
    {'key': 'beringovsky', 'label': 'беринговский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'chukotka', 'children': ()},
    {'key': 'kazakhstan', 'label': 'Угли казахстанские', 'indent': 1, 'kind': KIND_TOTAL, 'is_header': True, 'parent_key': 'coal', 'children': ('ekibastuz', 'maikuben', 'karaganda', 'karazhyra', 'teniz')},
    {'key': 'ekibastuz', 'label': 'экибастутский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kazakhstan', 'children': ()},
    {'key': 'maikuben', 'label': 'майкубенский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kazakhstan', 'children': ()},
    {'key': 'karaganda', 'label': 'карагандинский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kazakhstan', 'children': ()},
    {'key': 'karazhyra', 'label': 'каражирский(кам)', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kazakhstan', 'children': ()},
    {'key': 'teniz', 'label': 'тениз-коржункольский', 'indent': 2, 'kind': KIND_VALUE, 'is_header': False, 'parent_key': 'kazakhstan', 'children': ()},
)

PARENT_CHILDREN: dict[str, tuple[str, ...]] = {
    'gas': ('gas_natural', 'gas_associated'),
    'gas_artificial': ('blast_furnace_gas', 'coke_oven_gas', 'npz_gas'),
    'oil_fuel': ('mazut', 'diesel', 'other_oil'),
    'other_fuel': ('other_solid', 'lpg', 'other_misc'),
    'pechora': ('inta', 'vorkuta'),
    'kuznetsk': ('kuzn_gd', 'kuzn_t', 'kuzn_ss', 'kuzn_other'),
    'ural': ('sverdlovsk', 'chelyabinsk', 'kizel'),
    'kansk_achinsk': ('nazarov', 'borodino', 'berezovsky', 'pereyaslav', 'irbey', 'kansk'),
    'tungus': ('zheron', 'karabul'),
    'irkutsk': ('azey', 'mugun', 'cheremkhovo'),
    'buryat': ('gusinoozersk', 'tugnuy', 'okino'),
    'zabaykal': ('kharanor', 'urtuy', 'tataurovo', 'tarbagatai', 'zab_hard'),
    'yakut': ('nerungri', 'zyryan', 'yakut_other'),
    'amur': ('raychikhinsk', 'erkovets', 'ogodzha'),
    'primorye': ('bikin', 'razdolnensky', 'khanka'),
    'chukotka': ('anadyr', 'beringovsky'),
    'kazakhstan': ('ekibastuz', 'maikuben', 'karaganda', 'karazhyra', 'teniz'),
    'coal': ('donetsk', 'moscow', 'pechora', 'kuznetsk', 'ural', 'bashkir', 'kansk_achinsk', 'tungus', 'irkutsk', 'khakass', 'tuva', 'buryat', 'zabaykal', 'yakut', 'amur', 'urgal', 'ushumun', 'primorye', 'magadan', 'sakhalin', 'kamchatka', 'chukotka', 'kazakhstan'),
}

DEFAULT_CHARACTERISTICS: dict[str, dict[str, float | None]] = {
    'gas_natural': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.0, 'sulfur': 0.0, 'sulfur_share': 0.0, 'qh_kj': 33812.2, 'qh_kcal': 8077.999999999999, 'bj': 2.7, 'k_co2': 1.59, 'r_chem': 0.5, 'q_chem': 0.1, 'tut_per_t': 1.154, 'tj_per_kt': 33.82, 't_co2_per_tj': 54.4, 'k_natural': 1.1772392519737258},
    'gas_associated': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.0, 'sulfur': 0.0, 'sulfur_share': 0.0, 'qh_kj': 38099.88, 'qh_kcal': 8077.999999999999, 'bj': 2.7, 'k_co2': 1.695, 'r_chem': 0.5, 'q_chem': 0.1, 'tut_per_t': 1.154, 'tj_per_kt': 33.82, 't_co2_per_tj': 57.166666666666664, 'k_natural': 1.2689360498356468},
    'blast_furnace_gas': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.0, 'sulfur': 0.0, 'sulfur_share': 0.0, 'qh_kj': 4190.9868, 'qh_kcal': 1000.9999999999999, 'bj': 2.7, 'k_co2': 7.2, 'r_chem': 0.5, 'q_chem': 1.5, 'tut_per_t': 0.143, 'tj_per_kt': 4.2, 't_co2_per_tj': 260.0, 'k_natural': 0.13771812594618504},
    'coke_oven_gas': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.0, 'sulfur': 0.0, 'sulfur_share': 0.0, 'qh_kj': 16705.332, 'qh_kcal': 3989.9999999999995, 'bj': 2.7, 'k_co2': 1.3, 'r_chem': 0.5, 'q_chem': 0.1, 'tut_per_t': 0.57, 'tj_per_kt': 16.71, 't_co2_per_tj': 44.4, 'k_natural': 0.5644817679105085},
    'npz_gas': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.0, 'sulfur': 0.0, 'sulfur_share': 0.0, 'qh_kj': 43961.399999999994, 'qh_kcal': 10500.0, 'bj': 2.7, 'k_co2': 1.3, 'r_chem': 0.5, 'q_chem': 0.1, 'tut_per_t': 1.5, 'tj_per_kt': 43.96, 't_co2_per_tj': 57.6, 'k_natural': 1.1819554586973922},
    'mazut': {'ash': 0.05, 'ash_share': 0.9, 'q_mech': 0.02, 'sulfur': 0.2, 'sulfur_share': 0.02, 'qh_kj': 40141.0, 'qh_kcal': 9590.0, 'bj': 3.2, 'k_co2': 2.27, 'r_chem': 0.65, 'q_chem': 0.5, 'tut_per_t': 1.37, 'tj_per_kt': 40.15, 't_co2_per_tj': 77.64, 'k_natural': 1.366148321553468},
    'diesel': {'ash': 0.025, 'ash_share': 0.9, 'q_mech': 0.02, 'sulfur': 0.3, 'sulfur_share': 0.02, 'qh_kj': 42620.0, 'qh_kcal': 10180.0, 'bj': 3.2, 'k_co2': 2.17, 'r_chem': 0.65, 'q_chem': 0.5, 'tut_per_t': 1.45, 'tj_per_kt': 42.5, 't_co2_per_tj': 74.32, 'k_natural': 1.4538711956021007},
    'other_oil': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.02, 'sulfur': 0.3, 'sulfur_share': 0.02, 'qh_kj': 41899.0, 'qh_kcal': 10010.0, 'bj': 3.2, 'k_co2': 2.17, 'r_chem': 0.65, 'q_chem': 0.5, 'tut_per_t': 1.43, 'tj_per_kt': 41.91, 't_co2_per_tj': 77.4, 'k_natural': 1.5839237691352916},
    'peat': {'ash': 6.3, 'ash_share': 0.9, 'q_mech': 2.2, 'sulfur': 0.1, 'sulfur_share': 0.15, 'qh_kj': 8120.0, 'qh_kcal': 1940.0, 'bj': 8.2, 'k_co2': 3.11, 'r_chem': 1.0, 'q_chem': 0.75, 'tut_per_t': 0.34, 'tj_per_kt': 9.96, 't_co2_per_tj': 106.0, 'k_natural': 0.2990437690226185},
    'other_solid': {'ash': 0.6, 'ash_share': 0.9, 'q_mech': 1.8, 'sulfur': 0.1, 'sulfur_share': 0.1, 'qh_kj': 7793.8, 'qh_kcal': 1862.0, 'bj': 4.8, 'k_co2': 3.14, 'r_chem': 1.0, 'q_chem': 0.75, 'tut_per_t': 0.266, 'tj_per_kt': 7.8, 't_co2_per_tj': 112.0, 'k_natural': 0.2412486296645667},
    'lpg': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.0, 'sulfur': 0.0, 'sulfur_share': 0.0, 'qh_kj': 46012.932, 'qh_kcal': 10990.0, 'bj': 2.7, 'k_co2': 1.85, 'r_chem': 0.5, 'q_chem': 0.1, 'tut_per_t': 1.57, 'tj_per_kt': 46.01, 't_co2_per_tj': 63.2, 'k_natural': 1.8967826534913126},
    'other_misc': {'ash': 0.0, 'ash_share': 0.9, 'q_mech': 0.0, 'sulfur': 0.0, 'sulfur_share': 0.0, 'qh_kj': 11810.9628, 'qh_kcal': 2821.0, 'bj': 3.2, 'k_co2': 4.19, 'r_chem': 0.65, 'q_chem': 0.5, 'tut_per_t': 0.403, 'tj_per_kt': 29.31, 't_co2_per_tj': 143.0, 'k_natural': 0.4544929215233868},
    'donetsk': {'ash': 25.8, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 2.5, 'sulfur_share': 0.1, 'qh_kj': 18500.0, 'qh_kcal': 4420.0, 'bj': 5.6, 'k_co2': 2.65, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.876, 'tj_per_kt': 25.67, 't_co2_per_tj': 90.2, 'k_natural': 0.804},
    'moscow': {'ash': 30.6, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 1.6, 'sulfur_share': 0.1, 'qh_kj': 8670.0, 'qh_kcal': 2070.0, 'bj': 4.2, 'k_co2': 2.79, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.335, 'tj_per_kt': 9.82, 't_co2_per_tj': 95.0, 'k_natural': 0.24},
    'inta': {'ash': 25.4, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 2.0, 'sulfur_share': 0.1, 'qh_kj': 17540.0, 'qh_kcal': 4190.0, 'bj': 7.03, 'k_co2': 2.73, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.649, 'tj_per_kt': 19.02, 't_co2_per_tj': 93.1, 'k_natural': 0.343},
    'vorkuta': {'ash': 23.6, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.8, 'sulfur_share': 0.1, 'qh_kj': 20600.0, 'qh_kcal': 4920.0, 'bj': 7.03, 'k_co2': 2.71, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.822, 'tj_per_kt': 24.09, 't_co2_per_tj': 92.6, 'k_natural': 0.608},
    'kuzn_gd': {'ash': 16.9, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 21900.0, 'qh_kcal': 5230.0, 'bj': 7.3, 'k_co2': 2.69, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.867, 'tj_per_kt': 25.41, 't_co2_per_tj': 91.9, 'k_natural': 0.712},
    'kuzn_t': {'ash': 14.6, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.5, 'sulfur_share': 0.1, 'qh_kj': 25120.0, 'qh_kcal': 6000.0, 'bj': 7.3, 'k_co2': 2.69, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.75, 'tj_per_kt': 21.975, 't_co2_per_tj': 91.9, 'k_natural': 0.764},
    'kuzn_ss': {'ash': 16.5, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 25330.0, 'qh_kcal': 6050.0, 'bj': 7.3, 'k_co2': 2.69, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.8, 'tj_per_kt': 23.44, 't_co2_per_tj': 91.9, 'k_natural': 0.831},
    'kuzn_other': {'ash': 30.7, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.7, 'sulfur_share': 0.1, 'qh_kj': 20934.0, 'qh_kcal': 5000.0, 'bj': 7.3, 'k_co2': 2.69, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.867, 'tj_per_kt': 25.41, 't_co2_per_tj': 91.9, 'k_natural': 0.714},
    'sverdlovsk': {'ash': 30.4, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 11010.0, 'qh_kcal': 2630.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.33, 'tj_per_kt': 9.67, 't_co2_per_tj': 94.2, 'k_natural': None},
    'chelyabinsk': {'ash': 29.5, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 1.0, 'sulfur_share': 0.1, 'qh_kj': 12770.0, 'qh_kcal': 3050.0, 'bj': 4.2, 'k_co2': 2.78, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.552, 'tj_per_kt': 16.18, 't_co2_per_tj': 94.9, 'k_natural': 0.528},
    'kizel': {'ash': 31.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 6.1, 'sulfur_share': 0.1, 'qh_kj': 19590.0, 'qh_kcal': 4680.0, 'bj': 4.2, 'k_co2': 2.77, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.753, 'tj_per_kt': 22.07, 't_co2_per_tj': 94.3, 'k_natural': None},
    'bashkir': {'ash': 14.4, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 7450.0, 'qh_kcal': 1780.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.264, 'tj_per_kt': 7.737206400000001, 't_co2_per_tj': 94.2, 'k_natural': None},
    'nazarov': {'ash': 7.3, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 13812.857142857143, 'qh_kcal': 3300.0, 'bj': 4.8, 'k_co2': 2.87, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.47, 'tj_per_kt': 13.770999999999999, 't_co2_per_tj': 94.2, 'k_natural': 0.468},
    'borodino': {'ash': 6.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.2, 'sulfur_share': 0.1, 'qh_kj': 15659.0, 'qh_kcal': 3740.0, 'bj': 4.8, 'k_co2': 2.87, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.57, 'tj_per_kt': 16.701, 't_co2_per_tj': 94.2, 'k_natural': 0.573},
    'berezovsky': {'ash': 4.7, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.2, 'sulfur_share': 0.2, 'qh_kj': 15659.0, 'qh_kcal': 3740.0, 'bj': 4.8, 'k_co2': 2.87, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.53, 'tj_per_kt': 15.529000000000002, 't_co2_per_tj': 94.2, 'k_natural': 0.522},
    'pereyaslav': {'ash': 5.1, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.05, 'sulfur_share': 0.1, 'qh_kj': 18340.0, 'qh_kcal': 4400.0, 'bj': 4.8, 'k_co2': 2.87, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.58, 'tj_per_kt': 16.994, 't_co2_per_tj': 94.2, 'k_natural': 0.591},
    'irbey': {'ash': 10.4, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 16990.0, 'qh_kcal': 4055.0, 'bj': 4.8, 'k_co2': 2.87, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.56, 'tj_per_kt': 16.408, 't_co2_per_tj': 94.2, 'k_natural': 0.555},
    'kansk': {'ash': 5.8, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.48, 'sulfur_share': 0.1, 'qh_kj': 16931.214285714286, 'qh_kcal': 4045.0, 'bj': 4.8, 'k_co2': 2.87, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.516, 'tj_per_kt': 15.12, 't_co2_per_tj': 98.1, 'k_natural': None},
    'zheron': {'ash': 24.6, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 1.0, 'qh_kj': 19880.0, 'qh_kcal': 4770.0, 'bj': 5.0, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.65, 'tj_per_kt': 19.045, 't_co2_per_tj': 94.2, 'k_natural': 0.6},
    'karabul': {'ash': 15.2, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 1.0, 'sulfur_share': 1.0, 'qh_kj': 23615.8, 'qh_kcal': 5642.0, 'bj': 5.0, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.754, 'tj_per_kt': 22.1, 't_co2_per_tj': 94.2, 'k_natural': None},
    'azey': {'ash': 16.5, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.5, 'sulfur_share': 0.1, 'qh_kj': 15990.0, 'qh_kcal': 3820.0, 'bj': 4.6, 'k_co2': 2.75, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.483, 'tj_per_kt': 14.16, 't_co2_per_tj': 93.9, 'k_natural': 0.58},
    'mugun': {'ash': 15.6, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.9, 'sulfur_share': 0.1, 'qh_kj': 17290.0, 'qh_kcal': 4130.0, 'bj': 4.6, 'k_co2': 2.75, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.57, 'tj_per_kt': 16.701, 't_co2_per_tj': 94.2, 'k_natural': 0.571},
    'cheremkhovo': {'ash': 27.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 1.1, 'sulfur_share': 0.1, 'qh_kj': 17880.0, 'qh_kcal': 4270.0, 'bj': 4.6, 'k_co2': 2.75, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.752, 'tj_per_kt': 22.0, 't_co2_per_tj': 94.0, 'k_natural': 0.63},
    'khakass': {'ash': 15.5, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.5, 'sulfur_share': 0.1, 'qh_kj': 20560.0, 'qh_kcal': 4910.0, 'bj': 4.2, 'k_co2': 2.77, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.727, 'tj_per_kt': 21.3, 't_co2_per_tj': 94.4, 'k_natural': 0.757},
    'tuva': {'ash': 14.3, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 25410.0, 'qh_kcal': 6070.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.906, 'tj_per_kt': 26.55, 't_co2_per_tj': 94.2, 'k_natural': 0.9},
    'gusinoozersk': {'ash': 18.5, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 16408.0, 'qh_kcal': 3920.0, 'bj': 4.2, 'k_co2': 2.78, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.506, 'tj_per_kt': 14.8, 't_co2_per_tj': 94.9, 'k_natural': None},
    'tugnuy': {'ash': 18.5, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 24277.14285714286, 'qh_kcal': 5800.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.692, 'tj_per_kt': 20.3, 't_co2_per_tj': 94.2, 'k_natural': 0.749},
    'okino': {'ash': 21.5, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.86, 'sulfur_share': 0.1, 'qh_kj': 17496.285714285717, 'qh_kcal': 4180.0, 'bj': 4.2, 'k_co2': 2.78, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.64, 'tj_per_kt': 18.752000000000002, 't_co2_per_tj': 94.2, 'k_natural': 0.619},
    'kharanor': {'ash': 8.6, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.3, 'sulfur_share': 0.1, 'qh_kj': 12477.0, 'qh_kcal': 2980.0, 'bj': 4.2, 'k_co2': 2.9, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.506, 'tj_per_kt': 14.83, 't_co2_per_tj': 93.1, 'k_natural': 0.457},
    'urtuy': {'ash': 8.8, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.3, 'sulfur_share': 0.1, 'qh_kj': 15905.714285714284, 'qh_kcal': 3800.0, 'bj': 4.2, 'k_co2': 2.9, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.52, 'tj_per_kt': 15.236, 't_co2_per_tj': 94.4, 'k_natural': 0.542},
    'tataurovo': {'ash': 10.7, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.2, 'sulfur_share': 0.1, 'qh_kj': 14690.0, 'qh_kcal': 3510.0, 'bj': 4.2, 'k_co2': 2.9, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.51, 'tj_per_kt': 14.943000000000001, 't_co2_per_tj': 94.2, 'k_natural': 0.526},
    'tarbagatai': {'ash': 15.4, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 1.8, 'sulfur_share': 0.1, 'qh_kj': 15780.0, 'qh_kcal': 3770.0, 'bj': 4.2, 'k_co2': 2.9, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.526, 'tj_per_kt': 15.42, 't_co2_per_tj': 99.3, 'k_natural': None},
    'zab_hard': {'ash': 13.7, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.5, 'sulfur_share': 0.1, 'qh_kj': 24570.0, 'qh_kcal': 5870.0, 'bj': 4.2, 'k_co2': 2.9, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.768, 'tj_per_kt': 22.5, 't_co2_per_tj': 94.6, 'k_natural': None},
    'nerungri': {'ash': 12.7, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.2, 'sulfur_share': 0.1, 'qh_kj': 24530.0, 'qh_kcal': 5860.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.987, 'tj_per_kt': 28.93, 't_co2_per_tj': 94.2, 'k_natural': 0.806},
    'zyryan': {'ash': 10.8, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 23440.0, 'qh_kcal': 5600.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.82, 'tj_per_kt': 24.026, 't_co2_per_tj': 94.2, 'k_natural': 0.824},
    'yakut_other': {'ash': 16.9, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.3, 'sulfur_share': 0.1, 'qh_kj': 24430.0, 'qh_kcal': 5860.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.751, 'tj_per_kt': 22.01, 't_co2_per_tj': 94.2, 'k_natural': None},
    'raychikhinsk': {'ash': 7.9, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.3, 'sulfur_share': 0.1, 'qh_kj': 12557.142857142857, 'qh_kcal': 3000.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.43, 'tj_per_kt': 12.599, 't_co2_per_tj': 94.2, 'k_natural': 0.438},
    'erkovets': {'ash': 12.4, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.3, 'sulfur_share': 0.1, 'qh_kj': 12138.57142857143, 'qh_kcal': 2900.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.42, 'tj_per_kt': 12.306, 't_co2_per_tj': 94.2, 'k_natural': 0.415},
    'ogodzha': {'ash': 33.4, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.2, 'sulfur_share': 0.1, 'qh_kj': 23021.428571428572, 'qh_kcal': 5500.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.447, 'tj_per_kt': 13.1, 't_co2_per_tj': 94.2, 'k_natural': 0.723},
    'urgal': {'ash': 29.6, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 19970.0, 'qh_kcal': 4770.0, 'bj': 4.2, 'k_co2': 2.77, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.7, 'tj_per_kt': 20.509999999999998, 't_co2_per_tj': 94.2, 'k_natural': 0.644},
    'ushumun': {'ash': 22.3, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.2, 'sulfur_share': 0.1, 'qh_kj': 11210.0, 'qh_kcal': 2690.0, 'bj': 4.2, 'k_co2': 2.96, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.506, 'tj_per_kt': 14.83, 't_co2_per_tj': 93.1, 'k_natural': None},
    'bikin': {'ash': 22.1, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.3, 'sulfur_share': 0.1, 'qh_kj': 9043.0, 'qh_kcal': 2160.0, 'bj': 4.2, 'k_co2': 2.73, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.31, 'tj_per_kt': 9.083, 't_co2_per_tj': 94.2, 'k_natural': 0.294},
    'razdolnensky': {'ash': 36.8, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 16540.0, 'qh_kcal': 3950.0, 'bj': 4.2, 'k_co2': 2.73, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.506, 'tj_per_kt': 14.83, 't_co2_per_tj': 93.1, 'k_natural': None},
    'khanka': {'ash': 14.8, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.3, 'sulfur_share': 0.1, 'qh_kj': 9960.0, 'qh_kcal': 2380.0, 'bj': 4.2, 'k_co2': 2.96, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.506, 'tj_per_kt': 14.83, 't_co2_per_tj': 93.1, 'k_natural': None},
    'magadan': {'ash': 11.9, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 17920.0, 'qh_kcal': 4280.0, 'bj': 4.2, 'k_co2': 2.73, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.701, 'tj_per_kt': 20.54, 't_co2_per_tj': 93.1, 'k_natural': 0.643},
    'sakhalin': {'ash': 22.1, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 17580.0, 'qh_kcal': 4200.0, 'bj': 4.2, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.58, 'tj_per_kt': 16.994, 't_co2_per_tj': 94.2, 'k_natural': 0.534},
    'kamchatka': {'ash': 29.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.51, 'sulfur_share': 0.1, 'qh_kj': 19960.0, 'qh_kcal': 4770.0, 'bj': 4.2, 'k_co2': 2.73, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.323, 'tj_per_kt': 9.47, 't_co2_per_tj': 93.1, 'k_natural': 0.714},
    'anadyr': {'ash': 11.9, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.1, 'sulfur_share': 0.1, 'qh_kj': 17920.0, 'qh_kcal': 4280.0, 'bj': 4.2, 'k_co2': 2.96, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.768, 'tj_per_kt': 22.51, 't_co2_per_tj': 94.2, 'k_natural': 0.594},
    'beringovsky': {'ash': 16.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.9, 'sulfur_share': 0.1, 'qh_kj': 25114.285714285714, 'qh_kcal': 6000.0, 'bj': 4.2, 'k_co2': 2.77, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.768, 'tj_per_kt': 22.51, 't_co2_per_tj': 94.2, 'k_natural': None},
    'ekibastuz': {'ash': 38.1, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.02, 'qh_kj': 18880.0, 'qh_kcal': 4510.0, 'bj': 8.2, 'k_co2': 2.77, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.628, 'tj_per_kt': 18.41, 't_co2_per_tj': 94.6, 'k_natural': 0.57},
    'maikuben': {'ash': 23.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.5, 'sulfur_share': 0.1, 'qh_kj': 14530.0, 'qh_kcal': 3000.0, 'bj': 4.2, 'k_co2': 2.96, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.6, 'tj_per_kt': 17.58, 't_co2_per_tj': 94.6, 'k_natural': 0.624},
    'karaganda': {'ash': 40.7, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.6, 'sulfur_share': 0.1, 'qh_kj': 18835.714285714286, 'qh_kcal': 4500.0, 'bj': 7.1, 'k_co2': 2.76, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.726, 'tj_per_kt': 21.28, 't_co2_per_tj': 94.2, 'k_natural': None},
    'karazhyra': {'ash': 25.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.4, 'sulfur_share': 0.1, 'qh_kj': 20097.0, 'qh_kcal': 4800.0, 'bj': 8.2, 'k_co2': 2.77, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.75, 'tj_per_kt': 21.975, 't_co2_per_tj': 94.6, 'k_natural': 0.764},
    'teniz': {'ash': 32.0, 'ash_share': 0.9, 'q_mech': 2.0, 'sulfur': 0.775, 'sulfur_share': 0.1, 'qh_kj': 15068.571428571428, 'qh_kcal': 3600.0, 'bj': 4.2, 'k_co2': 2.77, 'r_chem': 1.0, 'q_chem': 0.5, 'tut_per_t': 0.768, 'tj_per_kt': 22.51, 't_co2_per_tj': 94.2, 'k_natural': None},
}

VOLUME_ROWS: tuple[dict[str, Any], ...] = (
    {'key': 'pollutants_total', 'label': 'ВСЕГО', 'indent': 0, 'kind': KIND_TOTAL, 'group': 'zv'},
    {'key': 'ash', 'label': 'в т.ч.: твердые частицы (зола)', 'indent': 1, 'kind': KIND_VALUE, 'group': 'zv'},
    {'key': 'so2', 'label': 'диоксид серы (SO2)', 'indent': 1, 'kind': KIND_VALUE, 'group': 'zv'},
    {'key': 'nox', 'label': 'оксиды азота (NOx)', 'indent': 1, 'kind': KIND_VALUE, 'group': 'zv'},
    {'key': 'co', 'label': 'монооксид углерода (CO)', 'indent': 1, 'kind': KIND_VALUE, 'group': 'zv'},
    {'key': 'co2', 'label': 'Диоксид углерода (CO2)', 'indent': 0, 'kind': KIND_TOTAL, 'group': 'pg'},
)

COEFF_KINDS: tuple[dict[str, Any], ...] = (
    {'key': 'ash_eta', 'label': 'КПД золоулавливания'},
    {'key': 'sulfur_eta', 'label': 'КПД сероочистки'},
    {'key': 'nox_n', 'label': 'Коэффициент подавления оксидов азота n'},
    {'key': 'co_k', 'label': 'Коэффициент подавления CO'},
    {'key': 'pg_k', 'label': 'Коэффициент подавления ПГ'},
)

CHAR_COLUMNS: tuple[tuple[str, str], ...] = (
    ('ash', 'Ap, %'),
    ('ash_share', 'аун'),
    ('q_mech', 'qч, %'),
    ('sulfur', 'Sp, %'),
    ('sulfur_share', 'x'),
    ('qh_kj', 'QH, кДж/кг'),
    ('qh_kcal', 'QH, ккал/кг'),
    ('bj', 'bj'),
    ('k_co2', 'КСО2'),
    ('r_chem', 'R, %'),
    ('q_chem', 'q3, %'),
    ('tut_per_t', 'тут/тн'),
    ('tj_per_kt', 'ТДж/тыс т натур'),
    ('t_co2_per_tj', 'т СО2/ТДж'),
    ('k_natural', 'K'),
)

CHAR_HEADER_GROUPS: tuple[dict[str, Any], ...] = (
    {"title": "Зольность", "keys": ("ash",)},
    {"title": "Доля золы", "keys": ("ash_share",)},
    {"title": "Потери тепла от мех. неполноты сгорания", "keys": ("q_mech",)},
    {"title": "Сернистость", "keys": ("sulfur",)},
    {"title": "Доля окислов серы", "keys": ("sulfur_share",)},
    {"title": "Низшая теплота сгорания", "keys": ("qh_kj", "qh_kcal")},
    {"title": "Уд.выброс окислов азота", "keys": ("bj",)},
    {"title": "Нац.коэфф.эмиссии", "keys": ("k_co2",)},
    {"title": "Коэф. доли потери тепла от хим. неполноты сгорания", "keys": ("r_chem",)},
    {"title": "Потери тепла от хим. неполноты сгорания", "keys": ("q_chem",)},
    {
        "title": "Коэффициенты для расчета как в НД о Кадастре ПГ",
        "keys": ("tut_per_t", "tj_per_kt", "t_co2_per_tj"),
    },
    {
        "title": "К перехода к натур топливу по данным формы ГИСТЭК 27-30",
        "keys": ("k_natural",),
        "rowspan": 2,
    },
)

# Лист «Справочник»: те же характеристики, без кадастровых К и Kнатур.
SPR_COLUMNS: tuple[tuple[str, str], ...] = CHAR_COLUMNS[:11]
SPR_HEADER_GROUPS: tuple[dict[str, Any], ...] = CHAR_HEADER_GROUPS[:-2]

# Источники значений листа «Справочник» (легенда C17–C18 макета Excel).
# Цвета — Interior.Color легенды, BGR → CSS; для «методических указаний»
# взят RGB-вид #d58d53, как на цветной подписи «кузнецкий прочий».
CHAR_SOURCE_OPTIONS: tuple[dict[str, str], ...] = (
    {
        "key": "thermal",
        "short": "Тепловой расчет котлов",
        "label": (
            "«Тепловой расчет котлов (нормативный метод)» ВТИ, СПб 1989 г."
        ),
        "color": "#b7e8e8",
    },
    {
        "key": "method",
        "short": "Методические указания",
        "label": (
            "«Методические указания по проектированию развития энергосистем», 2022 г."
        ),
        "color": "#d58d53",
    },
    {
        "key": "industry",
        "short": "Отраслевая методика",
        "label": (
            "Отраслевая методика расчета количества отходящих, улавливаемых "
            "и выбрасываемых вредных веществ предприятиями по добыче угля, г. Пермь 2003 г."
        ),
        "color": "#e6b8b7",
    },
    {
        "key": "table21",
        "short": "Таблица 2.1",
        "label": (
            "Таблица 2.1. «Справочник по котельным установкам малой производительности» "
            "под ред. К.Ф. Роддатиса. — М.: Энергоатомиздат, 1989."
        ),
        "color": "#a6a6a6",
    },
    {
        "key": "rosstat",
        "short": "Приказ Росстата",
        "label": (
            "Приказ Росстата от 22.11.2023 № 591 (коэффициент низшей теплоты сгорания; "
            "зольность и сернистость — среднее из справочника)"
        ),
        "color": "#44d89b",
    },
)

CHAR_SOURCE_KEYS = frozenset(item["key"] for item in CHAR_SOURCE_OPTIONS)
CHAR_SOURCE_COLORS: dict[str, str] = {
    item["key"]: item["color"] for item in CHAR_SOURCE_OPTIONS
}

# Заливка «Вид топлива» из макета, если источник не выбран (серый бассейнов без легенды).
FUEL_LABEL_COLORS: dict[str, str] = {
    "donetsk": "#bfbfbf",
    "inta": "#bfbfbf",
    "vorkuta": "#bfbfbf",
    "sverdlovsk": "#bfbfbf",
    "chelyabinsk": "#bfbfbf",
    "kizel": "#bfbfbf",
    "cheremkhovo": "#bfbfbf",
    "khakass": "#bfbfbf",
    "raychikhinsk": "#bfbfbf",
    "anadyr": "#bfbfbf",
    "ekibastuz": "#bfbfbf",
}

# Красный шрифт в макете: принятые значения при отсутствии справочных данных.
FUEL_ADOPTED_KEYS = frozenset({"irbey", "kansk"})

DEFAULT_CHAR_SOURCES: dict[str, str] = {
    "gas_natural": "rosstat",
    "gas_associated": "rosstat",
    "other_oil": "rosstat",
    "npz_gas": "rosstat",
    "other_solid": "rosstat",
    "mazut": "table21",
    "diesel": "table21",
    "peat": "table21",
    "urgal": "table21",
    "khanka": "table21",
    "sakhalin": "table21",
    "blast_furnace_gas": "thermal",
    "coke_oven_gas": "thermal",
    "moscow": "thermal",
    "kuzn_gd": "thermal",
    "kuzn_t": "thermal",
    "kuzn_ss": "thermal",
    "bashkir": "thermal",
    "azey": "thermal",
    "mugun": "thermal",
    "tuva": "thermal",
    "gusinoozersk": "thermal",
    "urtuy": "thermal",
    "tataurovo": "thermal",
    "tarbagatai": "thermal",
    "zab_hard": "thermal",
    "erkovets": "thermal",
    "razdolnensky": "thermal",
    "maikuben": "thermal",
    "karaganda": "thermal",
    "kuzn_other": "method",
    "nazarov": "method",
    "borodino": "method",
    "berezovsky": "method",
    "kharanor": "method",
    "bikin": "method",
    "pereyaslav": "industry",
    "zheron": "industry",
    "nerungri": "industry",
    "zyryan": "industry",
    "yakut_other": "industry",
    "ogodzha": "industry",
    "ushumun": "industry",
    "magadan": "industry",
}

DEFAULT_CHAR_NOTES: dict[str, str] = {
    "mazut": "Марка мазута М100, малосернистый",
    "diesel": "Среднее содержание топлива",
    "other_oil": "Среднее содержание топлива",
    "other_solid": "Щепа, опилки",
    "kuzn_t": "Стр. 129 из котельного справочника",
    "kuzn_other": "Взято из методики",
    "nazarov": "Взято из методики",
    "irbey": "Из статьи",
    "kansk": "Из сертификата угля",
    "karabul": "Каменный, из статьи",
    "bashkir": "Тульганский (бурый)",
    "tuva": "Уголь каахемского месторождения",
    "tugnuy": "Каменный",
    "okino": "Из статьи ВТИ-Урал (в пересчёте на рабочую)",
    "zab_hard": "Как багучанский",
    "yakut_other": "Взято как нерюнгринские промпродукты",
    "ushumun": "Бурый",
    "razdolnensky": "Каменный (липовецкий)",
    "khanka": "Бурый (раковский)",
    "magadan": "Каменный (аркагалинский)",
    "sakhalin": "Бывает каменный и бурый. Переводной коэффициент 0,6–0,7",
    "kamchatka": "Статья",
    "anadyr": "Бурый",
    "beringovsky": "Каменный",
    "karazhyra": "Каменный уголь марки Д месторождения Каражыра",
    "teniz": "Бурый. Уголь сарыадырский ГЖО",
}


def fuel_label_bg(fuel_key: str, source_key: str | None) -> str | None:
    """Цвет столбца «Вид топлива»: сначала источник, иначе заливка макета."""
    wanted = str(source_key or "").strip()
    if wanted:
        return CHAR_SOURCE_COLORS.get(wanted)
    return FUEL_LABEL_COLORS.get(fuel_key)


TOP_INPUT_ROWS: tuple[dict[str, Any], ...] = (
    {'key': 'ee_generation', 'label': 'Выработка электроэнергии', 'unit': 'млрд.кВтч', 'kind': KIND_VALUE},
    {'key': 'heat_output', 'label': 'Отпуск тепла', 'unit': 'тыс.Гкал', 'kind': KIND_VALUE},
)

EMISSION_FORMULAS = {
    "zola": "Мотх = 0,01·Вн·(аун·Ар + qч·QH/32680); Мвыб = Мотх·(1 − КПД золоулавливания)",
    "sera": "Мотх = 0,02·Вн·Sp·(1 − x); Мвыб = Мотх·(1 − КПД сероочистки)",
    "azot": "Мотх = 0,001·В·(1 − qч/100)·bj; Мвыб = ΣМотх·(1 − n)",
    "co": "Мотх = 0,001·Вн·(q3·R·QH/1013)·(1 − qч/100); Мвыб = Мотх·(1 − kCO)",
    "pg": "Мотх = В·KCO2; Мвыб = Мотх·(1 − kПГ)",
    "pg-tj": "TJ = Вн·(QH, кДж/кг)/1000; М = TJ·(т CO2/ТДж)/1000",
}

# Запасные КПД/коэффициенты подавления, если нет записи в БД.
# Год 2024 и далее — как в макете на 2024.
_COEFF_BY_YEAR: dict[int, dict[str, dict[str, float]]] = {
    2021: {
        "ash_eta": {"vsego": 0.975, "*": 0.975},
        "sulfur_eta": {"vsego": 0.139, "minen": 0.139, "*": 0.14665},
        "nox_n": {"vsego": 0.16172, "minen": 0.16172, "*": 0.17425},
        "co_k": {"vsego": 0.0, "*": 1.0},
        "pg_k": {"*": 0.0},
    },
    2022: {
        "ash_eta": {"*": 0.97765},
        "sulfur_eta": {"vsego": 0.139, "minen": 0.139, "*": 0.0084},
        "nox_n": {"vsego": 0.161, "minen": 0.162, "*": 0.0887},
        "co_k": {"*": 0.0},
        "pg_k": {"*": 0.0},
    },
    2023: {
        "ash_eta": {"vsego": 0.977192, "*": 0.97341},
        "sulfur_eta": {"vsego": 0.139, "minen": 0.139, "*": 0.0084},
        "nox_n": {"vsego": 0.161, "minen": 0.162, "*": 0.0887},
        "co_k": {"*": 0.0},
        "pg_k": {"*": 0.0},
    },
    2024: {
        "ash_eta": {"*": 0.97341},
        "sulfur_eta": {"vsego": 0.139, "minen": 0.14, "*": 0.0084},
        "nox_n": {"vsego": 0.162, "minen": 0.162, "*": 0.0887},
        "co_k": {"*": 0.0},
        "pg_k": {"*": 0.0},
    },
}


def get_territory(slug: str) -> dict[str, Any] | None:
    wanted = str(slug or "").strip()
    return next((item for item in TERRITORIES if item["slug"] == wanted), None)


def get_calc_sheet(slug: str) -> dict[str, Any] | None:
    wanted = str(slug or "").strip()
    return next((item for item in CALC_SHEETS if item["slug"] == wanted), None)


def default_coefficient(year: int, territory_slug: str, kind: str) -> float:
    table = _COEFF_BY_YEAR.get(int(year)) or _COEFF_BY_YEAR[2024]
    by_kind = table.get(kind) or {}
    if territory_slug in by_kind:
        return float(by_kind[territory_slug])
    return float(by_kind.get("*", 0.0))

