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
    name = re.sub(r'^"', r'«', name)  # Первая кавычка не может быть закрывающей
    name = re.sub(r'([(\[{])"', r'\1«', name)  # Открывающая кавычка после скобки
    name = re.sub(r'(?<=\s)"(\S)', r' «\1', name)  # Открывающая кавычка перед словом
    name = re.sub(r'(?<=\w)"(?=\w)', r' «', name)  # Открывающая кавычка внутри слова с пробелом перед ней
    name = re.sub(r'"(?=\s|$)', r'»', name)  # Закрывающая кавычка в конце слова
    name = re.sub(r'(?<!«)([^\s\(\[\{])"', r'\1»', name)  # Закрывающая, если перед ней нет открывающей
    name = re.sub(r'\s+', ' ', name)  # Убираем лишние пробелы
    
    return name


def _clean_multiline_text(value: Any) -> Optional[str]:
    """Сохраняет переносы строк, чистит каждый ряд отдельно."""
    if not isinstance(value, str):
        return value

    if value.strip().lower() == "nan":
        return None

    text = value.replace('\xa0', ' ')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')

    cleaned_lines = []
    for line in lines:
        cleaned_line = _clean_name(line)
        cleaned_lines.append(cleaned_line or "")

    # Убираем пустые строки только по краям
    while cleaned_lines and cleaned_lines[0] == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    return "\n".join(cleaned_lines) if cleaned_lines else None


# Неразрывный пробел для экспорта в Excel (предотвращает перенос строки внутри ячейки)
NBSP = "\u00A0"


def to_excel_nbsp(value: Any) -> Any:
    """
    Преобразует значение для экспорта в Excel: в строках пробелы заменяются на неразрывные.
    None и числа возвращаются без изменений.
    """
    if value is None:
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    s = str(value)
    return s.replace(" ", NBSP) if s else value


def apply_nbsp_to_row(row) -> list:
    """Применяет неразрывные пробелы ко всем значениям строки для Excel."""
    return [to_excel_nbsp(v) for v in row]


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

    # digits == 0 → без округления, все знаки после запятой
    if digits == 0:
        s = format(value.normalize(), '.20f')
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s.replace('.', ',')

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


def values_equal_by_display_precision(old_val, new_val, display_digits=6):
    """
    Считает значения равными, если разница меньше половины последнего значащего
    разряда округления. Используется, чтобы не считать «изменением» ситуацию,
    когда пользователь сохранил форму без правок, а в форме пришло округлённое
    значение (было в БД 1683.738997, в форме 1683.7).
    display_digits: число знаков после запятой при отображении (1, 2, 3 и т.д.).
    Для -1 (целые) используем digits=0.
    Для 0 («Не округлять») значения сравниваются строго (без допуска по округлению),
    т.к. в интерфейсе отображаются все знаки после запятой.
    Нулевое значение и None считаются эквивалентными (0.000000 → — не логируем).
    """
    if old_val is None and new_val is None:
        return True
    if old_val is None or new_val is None:
        try:
            other = Decimal(str(old_val if new_val is None else new_val))
            if other == 0:
                return True
        except (InvalidOperation, ValueError, TypeError):
            pass
        return False
    try:
        o = Decimal(str(old_val))
        n = Decimal(str(new_val))
    except (InvalidOperation, ValueError, TypeError):
        return old_val == new_val

    # 0 в UI означает «Не округлять» (см. format_decimal_for_display), поэтому сравниваем строго.
    if display_digits == 0:
        return o == n

    d = max(0, min(10, int(display_digits))) if display_digits != -1 else 0
    tol = Decimal("0.5") * (Decimal(10) ** -d)
    return abs(o - n) < tol



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

        # dd-mm-yyyy
        try:
            return datetime.strptime(value, "%d-%m-%Y").date()
        except ValueError:
            pass

        # yyyy-mm-dd
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass

    return None


def normalize_date_list(value: str) -> Optional[str]:
    """
    Нормализует список дат в строке к единому формату 'YYYY-MM-DD',
    разделённому запятыми.

    Примеры:
    - "01-10-2002, 01.10.2025" -> "2002-10-01, 2025-10-01"
    - "2020; 2021-02-05"        -> "2020-01-01, 2021-02-05"
    """
    if not value:
        return None

    parts = re.split(r"[;,]", str(value))
    normalized = []

    for raw in parts:
        token = raw.strip()
        if not token:
            continue

        dt = convert_to_date(token)
        if dt is None:
            # Если не смогли распарсить — сохраняем как есть,
            # чтобы не потерять ввод пользователя
            normalized.append(token)
        else:
            normalized.append(dt.strftime("%Y-%m-%d"))

    if not normalized:
        return None

    return ", ".join(normalized)