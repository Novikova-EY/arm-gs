# -*- coding: utf-8 -*-
"""Расчёт плановой выработки ВЭС/СЭС (минимум за 7 лет и сравнение с собственником).

План-годы таблицы «Выработка электроэнергии электростанцией»:
- расчётное значение, ячейка остаётся редактируемой;
- для каждого плана: min(выработка от собственника, если > 0;
  минимум положительных значений за последние 7 лет факта, без текущего года);
- если станция введена в этом 7-летнем окне, первое ненулевое значение
  в выборке не участвует; если выработка второго года < 50% третьего —
  второй год тоже исключается;
- если год ввода попадает в плановый период, берём выработку от собственника;
- если собственника нет, план = установленная мощность (МВт) × 1,5 для СЭС и × 2,5 для ВЭС,
  умноженная на долю года работы по «Ожидаемой дате ввода в эксплуатацию»
  (дней работы в году / 365 или 366 для високосного);
- то же Руст × коэффициент, если после отсечения лет разгона 7-летняя выборка
  пуста, а год ввода или первое Руст лежит в окне 7 лет факта.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

from sqlalchemy import func, or_

from app.common.services.database_version_filter import (
    filter_by_explicit_db_version,
    get_current_db_version_id,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.services.station_services.groupped_services import (
    parse_machine_commission_year,
)
from app.generation.services.station_services.station_type_flags import (
    is_ves_or_ses_station,
    station_type_name_norm,
)

VES_SES_SAMPLE_YEARS = 7
RAMP_SECOND_YEAR_SHARE = Decimal("0.5")
SES_PLAN_CAPACITY_FACTOR = Decimal("1.5")
VES_PLAN_CAPACITY_FACTOR = Decimal("2.5")
PLAN_CAPACITY_FACTOR = {
    "ses": SES_PLAN_CAPACITY_FACTOR,
    "ves": VES_PLAN_CAPACITY_FACTOR,
}

PLAN_RULE_OWNER_IN_PLAN = (
    "Расчёт: выработка от собственника (ввод мощности в плановом периоде)"
)
PLAN_RULE_CAPACITY_SES = (
    "Расчёт: установленная мощность × 1,5 (СЭС, нет данных от собственника)"
)
PLAN_RULE_CAPACITY_VES = (
    "Расчёт: установленная мощность × 2,5 (ВЭС, нет данных от собственника)"
)
PLAN_RULE_CAPACITY_SES_PARTIAL = (
    "Расчёт: установленная мощность × 1,5 × доля года работы по ожидаемой дате ввода "
    "(СЭС, нет данных от собственника)"
)
PLAN_RULE_CAPACITY_VES_PARTIAL = (
    "Расчёт: установленная мощность × 2,5 × доля года работы по ожидаемой дате ввода "
    "(ВЭС, нет данных от собственника)"
)
PLAN_RULE_OWNER_POSITIVE = "Расчёт: выработка от собственника (> 0)"
PLAN_RULE_SEVEN_YEAR_MIN = (
    "Расчёт: минимум положительной выработки за последние 7 лет факта"
)
PLAN_RULE_SEVEN_YEAR_MIN_RAMP = (
    "Расчёт: минимум положительной выработки за последние 7 лет факта "
    "(без учёта лет разгона после ввода)"
)
PLAN_RULE_MIN_OWNER_SAMPLE_OWNER = (
    "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта "
    "(взята выработка от собственника)"
)
PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE = (
    "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта "
    "(взято значение за 7 лет факта)"
)
PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE_RAMP = (
    "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта "
    "(взято значение за 7 лет факта, без учёта лет разгона после ввода)"
)
PLAN_RULE_MIN_OWNER_SAMPLE_EQUAL = (
    "Расчёт: минимум из выработки от собственника и минимума за 7 лет факта "
    "(значения совпадают)"
)


def _norm_year_feature(name: Any) -> str:
    return " ".join(str(name or "").split()).casefold().replace("ё", "е")


def _positive_decimal(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        value = raw if isinstance(raw, Decimal) else Decimal(str(raw).replace(",", "."))
    except Exception:
        return None
    if value > 0:
        return value
    return None


def ves_ses_type_key(station_or_name: Any) -> str:
    if isinstance(station_or_name, str):
        name = " ".join(station_or_name.split()).casefold().replace("ё", "е")
    else:
        name = station_type_name_norm(station_or_name)
    compact = name.replace(" ", "").replace("(", "").replace(")", "")
    if compact.startswith("сэс") or compact.startswith("ses") or "сэс" in name:
        return "ses"
    if compact.startswith("вэс") or compact.startswith("ves") or "вэс" in name:
        return "ves"
    return "other"


def parse_exploitation_date(value: Any) -> date | None:
    """Разбор ожидаемой даты ввода (ДД.ММ.ГГГГ / ISO / date)."""
    from app.common.services.help_services import convert_to_date

    if value in (None, "", "—", "-", "–"):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return convert_to_date(str(value).strip())


def year_operation_days(start_date: date | None, year: int) -> tuple[int, int]:
    """
    (дней работы в году, дней в году).

    День ввода включается. Без даты — полный год. До года ввода — (0, days_in_year).
    """
    y = int(year)
    days_in_year = 366 if calendar.isleap(y) else 365
    if start_date is None:
        return days_in_year, days_in_year
    year_start = date(y, 1, 1)
    year_end = date(y, 12, 31)
    if start_date > year_end:
        return 0, days_in_year
    if start_date <= year_start:
        return days_in_year, days_in_year
    return (year_end - start_date).days + 1, days_in_year


def year_operation_fraction(start_date: date | None, year: int) -> Decimal:
    """Доля года работы начиная с start_date (день ввода включается)."""
    days_in_operation, days_in_year = year_operation_days(start_date, year)
    if days_in_operation <= 0:
        return Decimal(0)
    if days_in_operation == days_in_year:
        return Decimal(1)
    return Decimal(days_in_operation) / Decimal(days_in_year)


def _plan_from_capacity(
    capacity: Any,
    type_key: str | None,
    *,
    year: int | None = None,
    exploitation_date: date | None = None,
) -> Decimal | None:
    factor = PLAN_CAPACITY_FACTOR.get(str(type_key or ""))
    capacity_value = _positive_decimal(capacity)
    if factor is None or capacity_value is None:
        return None
    value = capacity_value * factor
    if year is None:
        return value
    days_in_operation, days_in_year = year_operation_days(exploitation_date, int(year))
    if days_in_operation <= 0:
        return None
    if days_in_operation == days_in_year:
        return value
    # 1,5×Руст×(дни/365) как (1,5×Руст×дни)/365
    return (value * Decimal(days_in_operation)) / Decimal(days_in_year)


def _first_positive_capacity_year(capacity_by_year: Mapping[int, Any] | None) -> int | None:
    years: list[int] = []
    for year, capacity in (capacity_by_year or {}).items():
        if _positive_decimal(capacity) is None:
            continue
        try:
            years.append(int(year))
        except (TypeError, ValueError):
            continue
    return min(years) if years else None


def _uses_plan_capacity_fallback(
    *,
    commission_year: int | None,
    plan_set: set[int],
    capacity_by_year: Mapping[int, Any] | None,
    current_year: int | None = None,
    empty_sample: bool = False,
) -> bool:
    """
    Режим Руст×коэффициент:
    - год ввода или первое появление Руст попадает в план;
    - либо ввод/первое Руст в текущем году или позже;
    - либо после разгона 7-летняя выборка пуста, а ввод/первое Руст
      лежит в окне 7 лет факта.
    """
    if commission_year is not None and int(commission_year) in plan_set:
        return True
    first_capacity_year = _first_positive_capacity_year(capacity_by_year)
    if first_capacity_year is not None and first_capacity_year in plan_set:
        return True
    if current_year is not None:
        cy = int(current_year)
        if commission_year is not None and int(commission_year) >= cy:
            return True
        if first_capacity_year is not None and first_capacity_year >= cy:
            return True
        if empty_sample:
            window_start, window_end = seven_year_sample_window(cy)
            if commission_year is not None and window_start <= int(commission_year) <= window_end:
                return True
            if first_capacity_year is not None and window_start <= first_capacity_year <= window_end:
                return True
    return False


def classify_ves_ses_generation_years(
    year_features: Mapping[Any, Any] | None,
) -> tuple[int | None, list[int]]:
    """Возвращает (текущий год, список плановых лет) по YearFeature."""
    current_year: int | None = None
    plan_years: list[int] = []
    for raw_year, raw_name in (year_features or {}).items():
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue
        feature = _norm_year_feature(raw_name)
        if feature.startswith("текущий"):
            current_year = year
        elif feature == "план" or feature.startswith("план"):
            plan_years.append(year)
    plan_years.sort()
    return current_year, plan_years


def seven_year_sample_window(current_year: int) -> tuple[int, int]:
    """Последние 7 лет факта, без текущего года."""
    last_fact = int(current_year) - 1
    return last_fact - (VES_SES_SAMPLE_YEARS - 1), last_fact


def sample_generation_pairs(
    energy_by_year: Mapping[int, Any],
    window_start: int,
    window_end: int,
) -> list[tuple[int, Decimal]]:
    pairs: list[tuple[int, Decimal]] = []
    for year in range(int(window_start), int(window_end) + 1):
        value = _positive_decimal(energy_by_year.get(year))
        if value is not None:
            pairs.append((year, value))
    return pairs


def filter_commission_ramp_sample(
    pairs: list[tuple[int, Decimal]],
    *,
    commission_year: int | None,
    window_start: int,
    window_end: int,
) -> list[tuple[int, Decimal]]:
    """Исключает первый (и при разгоне второй) год для станций, введённых в окне."""
    if not pairs:
        return []
    if commission_year is None:
        return list(pairs)
    if not (int(window_start) <= int(commission_year) <= int(window_end)):
        return list(pairs)

    excluded = {pairs[0][0]}
    if len(pairs) >= 3:
        second_year, second_value = pairs[1]
        _third_year, third_value = pairs[2]
        if third_value > 0 and second_value < third_value * RAMP_SECOND_YEAR_SHARE:
            excluded.add(second_year)
    return [(year, value) for year, value in pairs if year not in excluded]


def min_generation_over_sample(
    energy_by_year: Mapping[int, Any],
    *,
    current_year: int | None,
    commission_year: int | None,
) -> Decimal | None:
    if current_year is None:
        return None
    window_start, window_end = seven_year_sample_window(current_year)
    pairs = filter_commission_ramp_sample(
        sample_generation_pairs(energy_by_year, window_start, window_end),
        commission_year=commission_year,
        window_start=window_start,
        window_end=window_end,
    )
    if not pairs:
        return None
    return min(value for _year, value in pairs)


def _capacity_fallback_rule(
    type_key: str | None,
    *,
    partial_year: bool = False,
) -> str | None:
    key = str(type_key or "")
    if key == "ses":
        return PLAN_RULE_CAPACITY_SES_PARTIAL if partial_year else PLAN_RULE_CAPACITY_SES
    if key == "ves":
        return PLAN_RULE_CAPACITY_VES_PARTIAL if partial_year else PLAN_RULE_CAPACITY_VES
    return None


def _seven_year_min_rule(*, ramp_excluded: bool) -> str:
    if ramp_excluded:
        return PLAN_RULE_SEVEN_YEAR_MIN_RAMP
    return PLAN_RULE_SEVEN_YEAR_MIN


def plan_generation_explained(
    year: int,
    *,
    owner_by_year: Mapping[int, Any],
    min_sample: Decimal | None,
    commission_year: int | None,
    plan_years: Iterable[int],
    capacity_by_year: Mapping[int, Any] | None = None,
    type_key: str | None = None,
    ramp_excluded: bool = False,
    exploitation_date_expected: Any = None,
    current_year: int | None = None,
) -> tuple[Decimal | None, str | None]:
    """Возвращает (значение плана, текст правила для подсказки)."""
    plan_set = {int(item) for item in plan_years}
    owner_positive = _positive_decimal(owner_by_year.get(int(year)))
    start_date = parse_exploitation_date(exploitation_date_expected)
    if _uses_plan_capacity_fallback(
        commission_year=commission_year,
        plan_set=plan_set,
        capacity_by_year=capacity_by_year,
        current_year=current_year,
        empty_sample=min_sample is None,
    ):
        if owner_positive is not None:
            return owner_positive, PLAN_RULE_OWNER_IN_PLAN
        value = _plan_from_capacity(
            (capacity_by_year or {}).get(int(year)),
            type_key,
            year=int(year),
            exploitation_date=start_date,
        )
        if value is None:
            return None, None
        fraction = year_operation_fraction(start_date, int(year))
        return value, _capacity_fallback_rule(type_key, partial_year=(fraction != 1))
    # Нет положительного Руст в году — станция не работает (выведена / ещё не введена)
    if capacity_by_year is not None and _positive_decimal(
        (capacity_by_year or {}).get(int(year))
    ) is None:
        return None, None
    if owner_positive is not None and min_sample is not None:
        value = min(owner_positive, min_sample)
        if owner_positive == min_sample:
            return value, PLAN_RULE_MIN_OWNER_SAMPLE_EQUAL
        if value == min_sample:
            if ramp_excluded:
                return value, PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE_RAMP
            return value, PLAN_RULE_MIN_OWNER_SAMPLE_SAMPLE
        return value, PLAN_RULE_MIN_OWNER_SAMPLE_OWNER
    if min_sample is not None:
        return min_sample, _seven_year_min_rule(ramp_excluded=ramp_excluded)
    if owner_positive is not None:
        return owner_positive, PLAN_RULE_OWNER_POSITIVE
    return None, None


def plan_generation_for_year(
    year: int,
    *,
    owner_by_year: Mapping[int, Any],
    min_sample: Decimal | None,
    commission_year: int | None,
    plan_years: Iterable[int],
    capacity_by_year: Mapping[int, Any] | None = None,
    type_key: str | None = None,
    ramp_excluded: bool = False,
    exploitation_date_expected: Any = None,
    current_year: int | None = None,
) -> Decimal | None:
    value, _rule = plan_generation_explained(
        year,
        owner_by_year=owner_by_year,
        min_sample=min_sample,
        commission_year=commission_year,
        plan_years=plan_years,
        capacity_by_year=capacity_by_year,
        type_key=type_key,
        ramp_excluded=ramp_excluded,
        exploitation_date_expected=exploitation_date_expected,
        current_year=current_year,
    )
    return value


def _sample_ramp_excluded(
    energy_by_year: Mapping[int, Any],
    *,
    current_year: int | None,
    commission_year: int | None,
) -> bool:
    if current_year is None:
        return False
    window_start, window_end = seven_year_sample_window(current_year)
    pairs = sample_generation_pairs(energy_by_year, window_start, window_end)
    filtered = filter_commission_ramp_sample(
        pairs,
        commission_year=commission_year,
        window_start=window_start,
        window_end=window_end,
    )
    return len(filtered) < len(pairs)


def compute_ves_ses_plan_generation(
    energy_by_year: Mapping[int, Any],
    owner_by_year: Mapping[int, Any],
    *,
    current_year: int | None,
    plan_years: Iterable[int],
    commission_year: int | None,
    capacity_by_year: Mapping[int, Any] | None = None,
    type_key: str | None = None,
    exploitation_date_expected: Any = None,
) -> tuple[Decimal | None, dict[int, Decimal], dict[int, str]]:
    """Возвращает (минимум выборки, {план-год: значение}, {план-год: правило})."""
    min_sample = min_generation_over_sample(
        energy_by_year,
        current_year=current_year,
        commission_year=commission_year,
    )
    ramp_excluded = _sample_ramp_excluded(
        energy_by_year,
        current_year=current_year,
        commission_year=commission_year,
    )
    calculated: dict[int, Decimal] = {}
    rules: dict[int, str] = {}
    plan_list = [int(year) for year in plan_years]
    years_to_fill = list(plan_list)
    if current_year is not None and _uses_plan_capacity_fallback(
        commission_year=commission_year,
        plan_set=set(plan_list),
        capacity_by_year=capacity_by_year,
        current_year=current_year,
    ):
        cy = int(current_year)
        if cy not in years_to_fill:
            years_to_fill = [cy] + years_to_fill
    for year in years_to_fill:
        value, rule = plan_generation_explained(
            year,
            owner_by_year=owner_by_year,
            min_sample=min_sample,
            commission_year=commission_year,
            plan_years=plan_list,
            capacity_by_year=capacity_by_year,
            type_key=type_key,
            ramp_excluded=ramp_excluded,
            exploitation_date_expected=exploitation_date_expected,
            current_year=current_year,
        )
        if value is not None:
            calculated[year] = value
            if rule:
                rules[year] = rule
    return min_sample, calculated, rules


def station_commission_year_from_machines(station) -> int | None:
    years: list[int] = []
    for machine in getattr(station, "machines", None) or []:
        if getattr(machine, "is_archived", False):
            continue
        year = parse_machine_commission_year(getattr(machine, "commission_display", None))
        if year is None:
            year = parse_machine_commission_year(getattr(machine, "date_commission_year", None))
        if year is None:
            year = parse_machine_commission_year(
                getattr(machine, "date_exploitation_expected", None)
            )
        if year is not None:
            years.append(year)
    if years:
        return min(years)
    return None


def load_station_commission_years(
    station_ids: Iterable[int],
    version_id: int | None = None,
) -> dict[int, int]:
    ids = [int(item) for item in station_ids if item is not None]
    if not ids:
        return {}
    if version_id is None:
        version_id = get_current_db_version_id()
    commission_year = func.coalesce(Machine.date_commission_year, Machine.date_exploitation_expected)
    query = (
        Machine.query.with_entities(Machine.id_station, func.min(commission_year))
        .filter(
            Machine.id_station.in_(ids),
            or_(Machine.is_archived.is_(False), Machine.is_archived.is_(None)),
            commission_year.isnot(None),
        )
        .group_by(Machine.id_station)
    )
    query = filter_by_explicit_db_version(query, Machine, version_id)
    result: dict[int, int] = {}
    for station_id, year in query.all():
        parsed = parse_machine_commission_year(year)
        if station_id is not None and parsed is not None:
            result[int(station_id)] = parsed
    return result


def expected_year_from_exploitation_date(value) -> int | None:
    """Год из ожидаемой даты ввода: 01.01.ГГГГ → ГГГГ-1, иначе календарный год."""
    from datetime import date, datetime

    from app.common.services.help_services import convert_to_date

    if value in (None, "", "—", "-"):
        return None
    if isinstance(value, datetime):
        dt = value.date()
    elif isinstance(value, date):
        dt = value
    else:
        dt = convert_to_date(value)
    if dt is None:
        return None
    if dt.month == 1 and dt.day == 1:
        return int(dt.year) - 1
    return int(dt.year)


def format_exploitation_date_display(value) -> str:
    """Отображение даты как ДД.ММ.ГГГГ (пусто → '')."""
    import re
    from datetime import date, datetime

    from app.common.services.help_services import convert_to_date

    if value in (None, "", "—", "-"):
        return ""
    if isinstance(value, datetime):
        dt = value.date()
    elif isinstance(value, date):
        dt = value
    else:
        text = str(value).strip()
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", text):
            return text
        dt = convert_to_date(text)
    if dt is None:
        return str(value).strip()
    return dt.strftime("%d.%m.%Y")


def load_station_exploitation_dates(
    station_ids: Iterable[int],
    version_id: int | None = None,
) -> dict[int, str]:
    """
    Ожидаемая дата ввода в эксплуатацию по станции (с агрегатов).

    Берём дату с агрегата с минимальным годом ввода
    (date_commission_year / date_exploitation_expected), иначе любую непустую.
    """
    ids = [int(item) for item in station_ids if item is not None]
    if not ids:
        return {}
    if version_id is None:
        version_id = get_current_db_version_id()
    commission_year = func.coalesce(Machine.date_commission_year, Machine.date_exploitation_expected)
    query = Machine.query.with_entities(
        Machine.id,
        Machine.id_station,
        Machine.date_exploitation_date_expected,
        commission_year.label("commission_year"),
    ).filter(
        Machine.id_station.in_(ids),
        or_(Machine.is_archived.is_(False), Machine.is_archived.is_(None)),
    )
    query = filter_by_explicit_db_version(query, Machine, version_id)
    by_station: dict[int, list[tuple]] = {}
    for machine_id, station_id, date_val, year_val in query.all():
        if station_id is None:
            continue
        by_station.setdefault(int(station_id), []).append(
            (machine_id, date_val, parse_machine_commission_year(year_val))
        )

    result: dict[int, str] = {}
    for station_id, rows in by_station.items():
        rows_sorted = sorted(
            rows,
            key=lambda item: (
                item[2] is None,
                item[2] if item[2] is not None else 10**9,
                item[0] or 0,
            ),
        )
        chosen = ""
        for _mid, date_val, _year in rows_sorted:
            display = format_exploitation_date_display(date_val)
            if display:
                chosen = display
                break
        result[station_id] = chosen
    return result


def save_station_exploitation_date_expected(
    user,
    station,
    raw_value,
    *,
    orig_value: str | None = None,
    version_id: int | None = None,
) -> tuple[list[str], str]:
    """
    Сохраняет Ожидаемую дату ввода в эксплуатацию во все неархивные агрегаты станции.

    Также синхронизирует date_exploitation_expected (правило 01.01.ГГГГ → год-1).
    Возвращает (changes, display_value).
    """
    import re

    from app.common.services.help_services import convert_to_date
    from app.extensions import db
    from app.logs.services.logging_service import log_to_db

    if version_id is None:
        version_id = get_current_db_version_id()

    raw = "" if raw_value is None else str(raw_value).strip()
    orig = "" if orig_value is None else str(orig_value).strip()
    if raw in {"—", "-", "–"}:
        raw = ""
    if orig in {"—", "-", "–"}:
        orig = ""

    display_new = format_exploitation_date_display(raw) if raw else ""
    display_orig = format_exploitation_date_display(orig) if orig else ""
    if display_new == display_orig:
        return [], display_new or display_orig

    stored_iso = None
    derived_year = None
    if raw:
        # Валидация как на карточке агрегата (YYYY / DD.MM.YYYY / YYYY-MM-DD)
        if not (
            re.fullmatch(r"\d{4}", raw)
            or re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", raw)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw)
            or re.fullmatch(r"\d{2}-\d{2}-\d{4}", raw)
        ):
            raise ValueError(
                "Некорректный формат. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD."
            )
        parsed = convert_to_date(raw)
        if parsed is None:
            raise ValueError(
                f"Некорректная дата: {raw}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD."
            )
        if parsed.year > 2050:
            raise ValueError("Год в дате не может быть больше 2050.")
        stored_iso = parsed.strftime("%Y-%m-%d")
        derived_year = expected_year_from_exploitation_date(parsed)
        display_new = format_exploitation_date_display(parsed)

    query = Machine.query.filter(
        Machine.id_station == int(station.id),
        or_(Machine.is_archived.is_(False), Machine.is_archived.is_(None)),
    )
    query = filter_by_explicit_db_version(query, Machine, version_id)
    machines = query.order_by(Machine.id.asc()).all()
    if not machines:
        raise ValueError("У станции нет агрегатов для сохранения даты")

    changes: list[str] = []
    for machine in machines:
        old_date = getattr(machine, "date_exploitation_date_expected", None)
        old_display = format_exploitation_date_display(old_date) or "—"
        new_display = display_new or "—"
        if (old_date or None) != (stored_iso or None):
            machine.date_exploitation_date_expected = stored_iso
            changes.append(
                f"агрегат №{machine.machine_number or machine.id}: "
                f"Ожидаемая дата ввода в эксплуатацию: {old_display} → {new_display}"
            )

        if derived_year is not None:
            old_year = getattr(machine, "date_exploitation_expected", None)
            if old_year != derived_year:
                machine.date_exploitation_expected = derived_year
                changes.append(
                    f"агрегат №{machine.machine_number or machine.id}: "
                    f"Ожидаемый год ввода в эксплуатацию: {old_year or '—'} → {derived_year}"
                )

    if changes:
        db.session.commit()
        rd_name = ""
        try:
            rd_name = station.regional_district.name if station.regional_district else ""
        except Exception:
            rd_name = ""
        station_details = "; ".join(changes)
        log_to_db(
            user,
            f"Изменения в электростанции {station.name}"
            + (f" ({rd_name})" if rd_name else "")
            + " (страница СЭС/ВЭС)",
            details=station_details,
            entity_type="station",
            entity_id=station.id,
        )
        for machine in machines:
            machine_prefix = f"агрегат №{machine.machine_number or machine.id}:"
            machine_details = "; ".join(c for c in changes if c.startswith(machine_prefix))
            if not machine_details:
                continue
            log_to_db(
                user,
                f"Изменения в электростанции {station.name}"
                + (f" ({rd_name})" if rd_name else "")
                + f", агрегат №{machine.machine_number}",
                details=machine_details,
                entity_type="machine",
                entity_id=machine.id,
            )
    return changes, display_new


def _station_plan_capacity_map(
    station_id: int,
    years: Iterable[int],
    version_id: int | None,
) -> dict[int, Decimal]:
    year_list = [int(year) for year in years]
    if not year_list:
        return {}
    from app.energy_balance.services.ee_balance_ves_ses_page_services import _load_stations_p_ust

    loaded = _load_stations_p_ust([int(station_id)], year_list, version_id)
    return loaded.get(int(station_id)) or {}


def attach_ves_ses_plan_generation(
    station,
    *,
    start_year: int,
    end_year: int,
    station_version_id: int | None,
    year_features: Mapping[Any, Any] | None = None,
) -> None:
    """Дополняет карточку станции расчётом план-ячеек (без записи в БД)."""
    station.station_energy_plan_calc_by_year = {}
    station.station_energy_plan_rule_by_year = {}
    station.station_energy_min_sample_value = None
    station.ves_ses_plan_years = []
    station.ves_ses_current_year = None
    if not is_ves_or_ses_station(station):
        return

    if year_features is None:
        from app.common.services.get_services.years.year_feature_services import (
            get_year_feature_dict,
        )

        year_features = get_year_feature_dict() or {}

    current_year, plan_years = classify_ves_ses_generation_years(year_features)
    station.ves_ses_current_year = current_year
    station.ves_ses_plan_years = plan_years
    if current_year is None and not plan_years:
        return

    from app.generation.services.station_services.station_services import (
        station_annual_energy_by_year,
        station_owner_energy_by_year,
    )

    window_start = int(start_year)
    if current_year is not None:
        window_start = min(window_start, seven_year_sample_window(current_year)[0])
    load_end = max(int(end_year), int(current_year or end_year))
    energy_full = station_annual_energy_by_year(
        station.id, window_start, load_end, station_version_id
    )
    owner_full = station_owner_energy_by_year(
        station.id, window_start, load_end, station_version_id
    )
    station.station_energy_by_year = {
        year: energy_full.get(year)
        for year in range(int(start_year), int(end_year) + 1)
        if energy_full.get(year) is not None
    }
    station.station_owner_energy_by_year = {
        year: owner_full.get(year)
        for year in range(int(start_year), int(end_year) + 1)
        if owner_full.get(year) is not None
    }

    commission_year = station_commission_year_from_machines(station)
    if commission_year is None:
        loaded = load_station_commission_years([station.id], station_version_id)
        commission_year = loaded.get(station.id)

    exploitation_dates = load_station_exploitation_dates([station.id], station_version_id)
    exploitation_date_expected = exploitation_dates.get(station.id) or ""

    min_sample, calculated, rules = compute_ves_ses_plan_generation(
        energy_full,
        owner_full,
        current_year=current_year,
        plan_years=plan_years,
        commission_year=commission_year,
        capacity_by_year=_station_plan_capacity_map(
            station.id,
            list(range(int(start_year), int(end_year) + 1)) or plan_years,
            station_version_id,
        ),
        type_key=ves_ses_type_key(station),
        exploitation_date_expected=exploitation_date_expected,
    )
    station.station_energy_min_sample_value = min_sample
    station.station_energy_plan_calc_by_year = calculated
    station.station_energy_plan_rule_by_year = rules
    station.ves_ses_commission_year = commission_year
    station.ves_ses_exploitation_date_expected = exploitation_date_expected
