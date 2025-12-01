"""Сервисный модуль: Common help services."""

import re
import pandas as pd
from typing import Optional, Any
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from jinja2 import Undefined
from datetime import datetime, date


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
    result = list(text)
    quote_indices = []
    for i, ch in enumerate(text):
        if ch == '"':
            quote_indices.append(i)

    # Заменяем по очереди:
    for idx, pos in enumerate(quote_indices):
        if idx % 2 == 0:
            # нечетный индекс пары (с точки зрения человеческого счёта) – «
            result[pos] = '«'
        else:
            # чётный индекс пары – »
            result[pos] = '»'

    return ''.join(result)


def _clean_name(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return value
    
    # Проверка на строку 'nan', игнорируем её
    if value.strip().lower() == "nan":
        return None
    
    # Очищаем строку
    name = value.strip()
    name = name.replace('\xa0', ' ')  # Заменяем неразрывные пробелы на обычные
    name = re.sub(r'\s+', ' ', name)  # Убираем лишние пробелы

    # Заменяем пробел-тире-пробел на пробел-длинное тире-пробел
    name = re.sub(r'\s-\s', ' – ', name)
    
    # Расстановка кавычек в зависимости от их положения
    name = re.sub(r'(?<=\s)"(\S)', r' «\1', name)  # Открывающая кавычка перед словом
    name = re.sub(r'(?<=\w)"(?=\w)', r' «', name)  # Открывающая кавычка внутри слова с пробелом перед ней
    name = re.sub(r'"(?=\s|$)', r'»', name)  # Закрывающая кавычка в конце слова
    name = re.sub(r'(?<!«)(\S)"', r'\1»', name)  # Закрывающая кавычка, если перед ней нет открывающей
    name = re.sub(r'\s+', ' ', name)  # Убираем лишние пробелы
    
    return name


def format_decimal_for_display(value, digits=None):
    if value is None or isinstance(value, Undefined):
        return "—"

    # Приводим к Decimal
    try:
        if isinstance(value, str):
            value = Decimal(value.replace(",", "."))
        elif isinstance(value, float):
            value = Decimal(str(value))
        elif not isinstance(value, Decimal):
            value = Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return ""

    # digits == -1 → округление до целого
    if digits == -1:
        value = value.to_integral_value(rounding=ROUND_HALF_UP)
        return str(value).replace('.', ',')

    # digits is None → округляем до 1 знака по умолчанию
    if digits is None:
        digits = 1

    # digits == 0 → без округления, без экспоненты
    if digits == 0:
        return format(value.normalize(), 'f').replace('.', ',')

    # digits > 0 → округление с нужной точностью
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        quant = Decimal('1.' + '0' * digits)
        value = value.quantize(quant)
        return format(value, f'.{digits}f').replace('.', ',')


def rounded_decimal(value, digits=15):
    """
    Безопасное округление значения с сохранением точности. 
    Возвращает None, если value пустое или невалидное.
    """
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal(f"1.{'0'*digits}"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None



def convert_to_date(value):
    """
    Универсально конвертирует значение в datetime.date:
    - '2021' → date(2021, 1, 1)
    - '01.01.2021' → date(2021, 1, 1)
    - '2021-01-01' → date(2021, 1, 1)
    - datetime, pd.Timestamp → date
    - пусто или некорректно → None
    """
    if not value or pd.isna(value):
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().date()

    if isinstance(value, str):
        value = value.strip()

        # Только год
        if re.fullmatch(r"\d{4}", value):
            return date(int(value), 1, 1)

        # dd.mm.yyyy
        try:
            return datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            pass

        # yyyy-mm-dd
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass

    return None