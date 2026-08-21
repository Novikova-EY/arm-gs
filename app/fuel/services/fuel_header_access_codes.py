# -*- coding: utf-8 -*-
"""
Коды полей Access для шапок таблиц (в скобках) — регистр как в схеме СиПР.

numb1120 / year / year_number не меняем (в Access разный регистр по таблицам).
"""

from __future__ import annotations

# ORM-атрибут (lower) → имя в Access «как есть»
FUEL_HEADER_ACCESS_CODES: dict[str, str] = {
    # Станции(Схема)
    "nust": "NUST",
    "nr": "NR",
    "e": "E",
    "eotp": "EOTP",
    "eurt": "EURT",
    "eust": "EUST",
    "q": "Q",
    "turt": "TURT",
    "tust": "TUST",
    "b": "B",
    "gaz": "GAZ",
    "isk_gaz": "ISK_GAZ",
    "mazut": "MAZUT",
    "torf": "TORF",
    "slan": "SLAN",
    "proch": "PROCH",
    "ugol": "UGOL",
    "don": "DON",
    "podm": "PODM",
    "pech": "PECH",
    "alt": "ALT",
    "arkt": "ARKT",
    "kuzn": "KUZN",
    "ural": "URAL",
    "bashk": "BASHK",
    "kazah": "KAZAH",
    "kan": "KAN",
    "tung": "TUNG",
    "irkut": "IRKUT",
    "hak": "HAK",
    "tuv": "TUV",
    "bur": "BUR",
    "chit": "CHIT",
    "tal": "TAL",
    "amur": "AMUR",
    "urg": "URG",
    "ushum": "USHUM",
    "prim": "PRIM",
    "yakut": "YAKUT",
    "mag": "MAG",
    "kamch": "KAMCH",
    "chukot": "CHUKOT",
    "sah": "SAH",
    "qotr": "QOTR",
    # snk: в Станциях SNK, в Удельных snk — оставляем ORM-имя
    "ewtp": "EWTP",
    "nt": "NT",
    "nt_sum": "NTsum",
    "obor": "OBOR",
    "h": "H",
    "hfix": "HFIX",
    "ved": "VED",
    "obl": "OBL",
    "dep": "DEP",
    "oes": "OES",
    "er": "ER",
    "be": "BE",
    "gk": "GK",
    "sn_ee": "SN_EE",
    "sn_te": "SN_TE",
    "sn_t": "SNT",
    # Удельные(Схема) — смешанный регистр
    "bk": "Bk",
    "ksn": "Ksn",
    "kh": "Kh",
    # уже совпадают с Access (для явности): y, btp, sntp, k, snbas, bbas
}


def fuel_header_code(attr) -> str:
    """Код поля для подписи в скобках шапки таблицы."""
    key = attr if isinstance(attr, str) else ("" if attr is None else str(attr))
    if key in {"numb1120", "year", "year_number"}:
        return key
    if key.endswith("_calc"):
        base = key[: -len("_calc")]
        if base in {"numb1120", "year", "year_number"}:
            return key
        return f"{FUEL_HEADER_ACCESS_CODES.get(base, base)}_calc"
    return FUEL_HEADER_ACCESS_CODES.get(key, key)
