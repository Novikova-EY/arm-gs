# -*- coding: utf-8 -*-
"""Признаки типа электростанции для карточки station_details."""


def station_type_name_norm(station) -> str:
    try:
        st = getattr(station, "station_type", None)
        name = getattr(st, "name", None) if st is not None else None
        if not name:
            return ""
        return str(name).strip().lower()
    except Exception:
        return ""


def is_gaes_station(station) -> bool:
    return station_type_name_norm(station) == "гаэс"


def is_ges_station(station) -> bool:
    return station_type_name_norm(station) == "гэс"


def is_ves_or_ses_station(station) -> bool:
    name = station_type_name_norm(station)
    if not name:
        return False
    return name in {"вэс", "сэс"} or name.startswith(("вэс ", "сэс ", "вэс(", "сэс("))
