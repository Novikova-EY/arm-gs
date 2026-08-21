# -*- coding: utf-8 -*-
"""
Защита импортов на странице «Словарь станций и групп оборудования».

Access-выгрузки «Станции*.xlsx» / «Доп_угли*.xlsx» относятся к параметрам работы
(страница «Сведения о работе ТЭС»), а не к связям групп/агрегатов и не к soft-флагам
COMP/MAIN/NIV («Имена_станций»). Их случайная загрузка сюда ломает группировку.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

_EXTRA_NAME_MARKERS = (
    ("доп", "угл"),
    ("dop", "ugl"),
)
_EXTRA_NAME_PREFIXES = ("доп_угл", "допугл", "dop_ugl", "dopugli")

# Маркеры листа Access «Станции» / «Доп_угли» (нормализованные заголовки).
_ACCESS_FUEL_TABLE_MARKER_COLS = frozenset(
    {
        "nust",
        "nr",
        "eotp",
        "nt",
        "ntsum",
        "nt_sum",
        "qotr",
        "gaz_prir",
        "nazar",
        "kuzngd",
        "maztop",
        "tvproch",
        "eurt",
        "eust",
        "turt",
        "tust",
        "isk_gaz",
        "mazut",
    }
)

_FUEL_PARAMS_PAGE_HINT = (
    "Этот файл — выгрузка Access «Станции» / «Доп_угли». "
    "Его нужно загружать на странице «Сведения о работе ТЭС» "
    "(/fuel/stations_equipment_group_fuel_params), а не в словаре групп оборудования."
)

_SOFT_IMPORT_HINT = (
    "Для мягкой дозагрузки COMP/MAIN/NIV нужна выгрузка Access «Имена_станций.xlsx» "
    "(поля NUMB, COMP, MAIN, NIV), а не «Станции» / «Доп_угли»."
)

_FUEL_DB_IMPORT_HINT = (
    "Для «Импорт из Excel» на словаре нужен шаблон со столбцами id_station и "
    "equipment_group (обычно экспорт с этой же страницы), а не Access «Станции»."
)

_IMENA_ON_FUEL_DB_HINT = (
    "Этот файл — выгрузка Access «Имена_станций». "
    "Его нужно загружать жёлтой кнопкой «Проверить / загрузить флаги» "
    "(при необходимости отметьте «Создать отсутствующие NUMB»), "
    "а не синей «Импорт из Excel». "
    "Синяя кнопка принимает только шаблон АРМ с колонками id_station и equipment_group "
    "(экспорт с этой же страницы)."
)

_IMENA_HEADER_FLAG_COLS = frozenset({"comp", "main", "niv"})
_FUEL_DB_TEMPLATE_COLS = frozenset({"equipment_group", "id_station"})


def excel_basename_lower(filename: str | None) -> str:
    name = (filename or "").strip().replace("\\", "/")
    name = name.rsplit("/", 1)[-1]
    return name.lower().replace("ё", "е")


def _normalize_header(col: Any) -> str:
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").replace("\u00a0", " ").strip().lower()
    s = s.replace("ё", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    return "_".join(filter(None, s.split("_")))


def filename_looks_like_access_stations_or_extra_fuel(filename: str | None) -> bool:
    """True, если имя файла похоже на Access «Станции*.xlsx» / «Доп_угли*.xlsx»."""
    base = excel_basename_lower(filename)
    if not base:
        return False
    # «Имена_станций» содержит «станци», но это разрешённый файл soft-import.
    if ("имен" in base and "станц" in base) or ("imena" in base and "stanci" in base):
        return False
    if any(base.startswith(p) for p in _EXTRA_NAME_PREFIXES):
        return True
    if any(a in base and b in base for a, b in _EXTRA_NAME_MARKERS):
        return True
    if base.startswith("станци") or base.startswith("stanci"):
        return True
    if "станци" in base or "stanci" in base:
        return True
    return False


def _peek_excel_header_norms(file) -> set[str] | None:
    if file is None:
        return None
    pos = None
    try:
        if hasattr(file, "tell"):
            try:
                pos = file.tell()
            except Exception:
                pos = None
        xls = pd.ExcelFile(file)
        df_head = xls.parse(xls.sheet_names[0], header=0, nrows=0)
        return {_normalize_header(c) for c in df_head.columns}
    except Exception:
        return None
    finally:
        if hasattr(file, "seek"):
            try:
                file.seek(0 if pos is None else pos)
            except Exception:
                try:
                    file.seek(0)
                except Exception:
                    pass


def headers_look_like_access_stations_or_extra_fuel(file=None) -> bool:
    """True, если заголовки листа похожи на Access «Станции» / «Доп_угли»."""
    norms = _peek_excel_header_norms(file)
    if not norms:
        return False
    return bool(norms & _ACCESS_FUEL_TABLE_MARKER_COLS)


def reject_access_stations_or_extra_fuel_excel(
    filename: str | None,
    file=None,
    *,
    context: str = "fuel_db",
) -> None:
    """
    Бросает ValueError, если файл — Access «Станции» / «Доп_угли».

    :param context: «fuel_db» | «soft_import» — уточняет текст подсказки.
    """
    by_name = filename_looks_like_access_stations_or_extra_fuel(filename)
    by_headers = headers_look_like_access_stations_or_extra_fuel(file)
    if not by_name and not by_headers:
        return

    extra = _SOFT_IMPORT_HINT if context == "soft_import" else _FUEL_DB_IMPORT_HINT
    raise ValueError(f"{_FUEL_PARAMS_PAGE_HINT} {extra}")


def filename_looks_like_imena_stanciy(filename: str | None) -> bool:
    """True, если имя файла похоже на Access «Имена_станций.xlsx»."""
    base = excel_basename_lower(filename)
    if not base:
        return False
    return ("имен" in base and "станц" in base) or ("imena" in base and "stanci" in base)


def headers_look_like_imena_stanciy(file=None) -> bool:
    """True, если заголовки похожи на Access «Имена_станций», а не на шаблон АРМ."""
    norms = _peek_excel_header_norms(file)
    if not norms:
        return False
    if norms & _FUEL_DB_TEMPLATE_COLS:
        return False
    has_numb = "numb" in norms or "numb1120" in norms
    has_flags = bool(norms & _IMENA_HEADER_FLAG_COLS)
    return has_numb and has_flags


def reject_imena_stanciy_on_fuel_db_import(filename: str | None, file=None) -> None:
    """Синий «Импорт из Excel» не принимает Access «Имена_станций»."""
    if filename_looks_like_imena_stanciy(filename) or headers_look_like_imena_stanciy(file):
        raise ValueError(_IMENA_ON_FUEL_DB_HINT)
