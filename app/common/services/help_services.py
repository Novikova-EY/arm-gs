"""Сервисный модуль: Common help services."""

import json
import re
from typing import Optional, Any


def _dash(x):
    return x if x not in (None, "") else "—"


def _to_int_or_none(v, keep_zero=True):
    """
    Конвертирует значение в int или возвращает None.
    Безопасно обрабатывает: None, '', 'None', 'null', 'undefined',
    а также числа и числовые строки.
    Параметр keep_zero:
      - True  → 0 считается валидным значением и возвращается как 0
      - False → 0 конвертируется в None
    """
    if v is None:
        return None

    # Если передали список/кортеж (например, из request.values.getlist)
    if isinstance(v, (list, tuple)):
        if not v:
            return None
        v = v[0]

    s = str(v).strip()
    if s == "" or s.lower() in {"none", "null", "undefined"}:
        return None

    try:
        iv = int(s)
    except (TypeError, ValueError):
        return None

    if iv == 0 and not keep_zero:
        return None
    return iv


def _replace_quotes_sequentially(text: str) -> str:
    """
    Последовательно заменяет все виды кавычек на «»:
    - любые варианты кавычек (" « » „ “ ”) приводятся к прямым "
    - лишние кавычки подряд схлопываются
    - потом слева направо заменяются: первая «, вторая », третья « и т.д.
    - убираем лишние пробелы внутри кавычек
    """
    if not text:
        return text

    # 1. Все кавычки в обычные "
    text = re.sub(r'[«»„“”]', '"', text)

    # 2. Схлопываем дубликаты кавычек
    text = re.sub(r'"+', '"', text)

    # 3. Заменяем по порядку
    result = []
    open_flag = True
    for ch in text:
        if ch == '"':
            if open_flag:
                result.append("«")
            else:
                result.append("»")
            open_flag = not open_flag
        else:
            result.append(ch)
    text = "".join(result)

    # 4. Чистим пробелы внутри кавычек
    text = re.sub(r'«\s+', '«', text)   # убираем пробел после «
    text = re.sub(r'\s+»', '»', text)   # убираем пробел перед »

    return text


def _clean_name(value: Any) -> Optional[str]:
    """
    Нормализация входного текста без изменения кавычек:
    - None и строка 'nan' -> None
    - обрезаем края, заменяем неразрывные пробелы, схлопываем множественные пробелы
    - нормализуем пробелы вокруг тире/дефиса: ' - ' -> ' – ' (среднее тире с пробелами)
    - убираем лишние пробелы перед знаками препинания и ставим пробел после них при необходимости
    """
    if not isinstance(value, str):
        return value

    s = value.strip()
    if s.lower() == "nan" or s == "":
        return None

    # неразрывные пробелы -> обычные
    s = s.replace("\xa0", " ")

    # схлопываем пробелы
    s = re.sub(r"\s+", " ", s)

    # нормализация " - " и вариаций вокруг дефиса/тире -> « пробел-тире(–)-пробел »
    # сначала уберём пробелы вокруг одиночных дефисов/тире
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s*–\s*", " – ", s)
    # затем приведём « - » к « – »
    s = s.replace(" - ", " – ")

    # пробелы перед знаками препинания не нужны
    s = re.sub(r"\s+([,;:.!?…])", r"\1", s)
    # но пробел после некоторых знаков обычно нужен (кроме конца строки)
    s = re.sub(r"([,;:])(?=\S)", r"\1 ", s)

    # ещё раз схлопнем возможные двойные пробелы после правок
    s = re.sub(r"\s{2,}", " ", s)

    return s