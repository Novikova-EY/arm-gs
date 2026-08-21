# -*- coding: utf-8 -*-
"""Pure helpers for SIPR Appendix A (Приложение А) Excel export."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable, Optional


DASH = "–"

_PLACEHOLDER_NAMES = {
    "не указано",
    "не указана",
    "не указан",
    "не указано.",
    "не указана.",
    "не указан.",
}

_DATE_FMTS = ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d")

_QUEUE_ORDER = (
    ("перв", 0),
    ("1 очер", 0),
    ("1-я", 0),
    ("1я", 0),
    ("втор", 1),
    ("2 очер", 1),
    ("2-я", 1),
    ("2я", 1),
    ("треть", 2),
    ("3 очер", 2),
    ("четверт", 3),
    ("4 очер", 3),
)

_HIDE_ENERGY_UNIT_SUBJECT_MARKERS = (
    "камчат",
    "сахалин",
    "магадан",
)

_NORILSK_TAIMYR_MARKERS = (
    "норильск",
    "таймыр",
    "турухан",
)

_DPM_PLACEHOLDER_STATION_RE = re.compile(r"^\s*новые\s+сэс\b", re.IGNORECASE)

_STATION_NUMBER_IN_NAME_RE = re.compile(
    r"(?:^|[\s\-–—])(?:ТЭЦ|ГРЭС|ТЭС|ГЭС|АЭС|СЭС|ВЭС)?[\s\-–—]*(\d+)\s*$",
    re.IGNORECASE,
)


def display_appendix_a_machine_number(machine_number: Any) -> str:
    """Пустой станционный номер в Приложении А → «–»."""
    if machine_number is None:
        return DASH
    text = str(machine_number).strip()
    return text if text else DASH


def parse_date_value(value: Any) -> Optional[date]:
    """Парсит дату из ISO / DD.MM.YYYY / YYYY."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    s = str(value).strip()
    if not s:
        return None

    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue

    if s.isdigit() and len(s) == 4:
        try:
            return date(int(s), 1, 1)
        except Exception:
            return None
    return None


def format_date_dd_mm_yyyy(value: Any) -> Optional[str]:
    dt = parse_date_value(value)
    if dt is None:
        return None
    return dt.strftime("%d.%m.%Y")


def extract_year(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.year
    if isinstance(value, datetime):
        return value.year
    dt = parse_date_value(value)
    if dt is not None:
        return dt.year
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s[:4])
    except Exception:
        return None


def iter_fact_dates(raw: Any) -> list[date]:
    """Разбирает одно или несколько значений дат (через ; , | пробел)."""
    if not raw:
        return []
    if isinstance(raw, (date, datetime)):
        dt = parse_date_value(raw)
        return [dt] if dt else []

    s = str(raw).strip()
    if not s:
        return []

    parts = re.split(r"[;|,]\s*|\s{2,}|\n+", s)
    if len(parts) == 1:
        # Иногда даты идут через один пробел: «01.02.2025 15.03.2025»
        maybe = re.findall(r"\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}", s)
        if len(maybe) > 1:
            parts = maybe

    out: list[date] = []
    seen = set()
    for part in parts:
        dt = parse_date_value(part)
        if dt is None or dt in seen:
            continue
        seen.add(dt)
        out.append(dt)
    return out


def _is_vie_station_type(station_type_name: Optional[str]) -> bool:
    name = (station_type_name or "").strip().lower()
    if not name:
        return False
    return any(token in name for token in ("вэс", "сэс", "виэ", "солнеч", "ветр"))


def _machine_planned_commission_year(machine: Any) -> Optional[int]:
    for attr in (
        "date_exploitation_expected",
        "date_exploitation",
        "date_commission_year",
    ):
        year = extract_year(getattr(machine, attr, None))
        if year is not None:
            return year
    return None


def subject_has_dpm_vie_commissions(
    stations: Iterable[Any],
    *,
    fact_year: int,
    sipr_end: int,
) -> bool:
    """
    Примечание ДПМ ВИЭ и «1)» в шапке — только если в субъекте есть вводы ВИЭ
    (ВЭС/СЭС) в окне [fact_year, sipr_end]. Плейсхолдеры «Новые СЭС» не считаем.
    """
    for station in stations or []:
        st_name = (getattr(station, "name", None) or "").strip()
        if _DPM_PLACEHOLDER_STATION_RE.match(st_name):
            continue
        st_type = getattr(getattr(station, "station_type", None), "name", None)
        if not _is_vie_station_type(st_type):
            continue
        for machine in getattr(station, "machines", None) or []:
            if bool(getattr(machine, "is_archived", False)):
                continue
            year = _machine_planned_commission_year(machine)
            if year is not None and fact_year <= year <= int(sipr_end):
                return True
            # фактический ввод в окне тоже считается
            for dt in iter_fact_dates(getattr(machine, "date_commission_fact", None)):
                if fact_year <= dt.year <= int(sipr_end):
                    return True
    return False


def territory_name_genitive(rd: Any) -> str:
    """Родительный падеж субъекта для фразы «территория …»."""
    if not rd:
        return "Не указано"
    raw_rp = (getattr(rd, "name_rp", None) or "").strip()
    if raw_rp and raw_rp.lower() not in _PLACEHOLDER_NAMES:
        return raw_rp
    for attr in ("name_full", "name"):
        raw = (getattr(rd, attr, None) or "").strip()
        if raw and raw.lower() not in _PLACEHOLDER_NAMES:
            return raw
    return "Не указано"


def is_norilsk_taimyr_energy_unit(energy_unit_name: Optional[str]) -> bool:
    name = (energy_unit_name or "").strip().lower()
    return bool(name) and any(m in name for m in _NORILSK_TAIMYR_MARKERS)


def is_norilsk_taimyr_station(station: Any) -> bool:
    eu = getattr(station, "energy_unit", None)
    eu_name = None
    if eu is not None:
        eu_name = getattr(eu, "name_full", None) or getattr(eu, "name", None)
    return is_norilsk_taimyr_energy_unit(eu_name)


def norilsk_taimyr_ees_label(energy_unit_name: Optional[str] = None) -> str:
    """
    Полное наименование ЭЭС для Норильска/Таймыра (ТИТЭС).
    """
    eu = (energy_unit_name or "").strip()
    if eu:
        # Убираем хвост «Красноярского края», если он уже есть в имени энергоузла —
        # оставляем формулировку энергоузла как территориальную часть.
        base = eu
        if not base.lower().startswith("электроэнергетическая система"):
            return f"Электроэнергетическая система {base}"
        return base
    return (
        "Электроэнергетическая система Таймырского Долгано-Ненецкого "
        "муниципального района, Туруханского района и городского округа "
        "г. Норильск Красноярского края"
    )


def norilsk_taimyr_file_label() -> str:
    return "Норильск_Таймыр"


def should_show_energy_unit_header(
    *,
    district_name: Optional[str],
    energy_unit_name: Optional[str],
    is_norilsk_taimyr: bool = False,
) -> bool:
    """
    Энергорайоны/энергоузлы: скрываем для Норильска/Таймыра, Камчатки, Сахалина,
    Магадана; для Чукотки оставляем.
    """
    eu = (energy_unit_name or "").strip()
    if not eu:
        return False
    eu_l = eu.lower()
    if "не указано" in eu_l or "не указан" in eu_l or eu.startswith("id="):
        return False
    if is_norilsk_taimyr or is_norilsk_taimyr_energy_unit(eu):
        return False
    district_l = (district_name or "").strip().lower()
    if any(m in district_l for m in _HIDE_ENERGY_UNIT_SUBJECT_MARKERS):
        return False
    return True


def fuel_display_value(fuel_so: Any) -> str:
    raw = (str(fuel_so).strip() if fuel_so is not None else "")
    if not raw or raw.lower() == "не указано":
        return DASH
    return raw


def fuel_rowspan_key(machine: Any) -> str:
    """Ключ объединения «Вид топлива»; пустое топливо → «–» (ВЭС/СЭС/ГЭС)."""
    return fuel_display_value(getattr(machine, "fuel_so", None))


def machine_queue_sort_key(machine: Any) -> tuple:
    group = (getattr(machine, "machine_group", None) or "").strip().lower()
    queue_rank = 50
    for marker, rank in _QUEUE_ORDER:
        if marker in group:
            queue_rank = rank
            break
    return (
        queue_rank,
        group,
        _machine_number_sort_key(getattr(machine, "machine_number", None)),
        (getattr(machine, "machine_name", None) or "").strip().lower(),
        getattr(machine, "id", 0) or 0,
    )


_DASH_RE = re.compile(r"[\s\-–—_]+", re.UNICODE)


def _machine_number_sort_key(value: Any) -> tuple:
    if value is None:
        return (2, "", 10**9, "")
    s = str(value).strip()
    if not s:
        return (2, "", 10**9, "")
    if s.isdigit():
        return (0, "", int(s), "")
    m = re.search(r"\d+", s)
    if m:
        prefix_raw = s[: m.start()]
        prefix_norm = _DASH_RE.sub("", prefix_raw).strip().upper()
        n = int(m.group(0))
        suffix = _DASH_RE.sub("", s[m.end() :]).strip().upper()
        return (1, prefix_norm, n, suffix)
    return (2, _DASH_RE.sub("", s).strip().upper(), 10**9, "")


def station_name_number_sort_key(name: Optional[str]) -> tuple:
    """Для ТЭЦ-21 / ТЭЦ-22 — натуральный номер из названия."""
    text = (name or "").strip()
    if not text:
        return (1, 10**9, "")
    m = _STATION_NUMBER_IN_NAME_RE.search(text)
    if m:
        return (0, int(m.group(1)), text.lower())
    m2 = re.search(r"(\d+)", text)
    if m2:
        return (0, int(m2.group(1)), text.lower())
    return (1, 10**9, text.lower())


def primary_gen_company_name(station: Any) -> str:
    names = []
    for m in getattr(station, "machines", None) or []:
        if bool(getattr(m, "is_archived", False)):
            continue
        gc = getattr(m, "gen_company", None)
        if gc and getattr(gc, "name", None):
            names.append(gc.name.strip())
    if not names:
        return ""
    return sorted(names, key=lambda x: x.lower())[0]


def distinct_gen_company_names(station: Any) -> list[str]:
    seen = []
    seen_l = set()
    for m in getattr(station, "machines", None) or []:
        if bool(getattr(m, "is_archived", False)):
            continue
        gc = getattr(m, "gen_company", None)
        name = (getattr(gc, "name", None) or "").strip() if gc else ""
        if not name:
            continue
        key = name.lower()
        if key in seen_l:
            continue
        seen_l.add(key)
        seen.append(name)
    return seen


def build_machine_appendix_a_note(
    machine: Any,
    *,
    fact_year: int,
    all_years: Iterable[int],
) -> str:
    """
    Примечания агрегата для Приложения А.

    Факт текущего года (fact_year) — с точной датой:
      «Ввод в эксплуатацию ДД.ММ.ГГГГ», «Вывод …», «Перемаркировка …», «Присоединение …».
    Прошлые факты — без примечания.
    План (ожидаемые годы в all_years) — «… в YYYY г.».
    Несколько факт-событий текущего года объединяются в одно примечание.
    """
    years = set(int(y) for y in all_years)
    note_parts: list[str] = []

    joining_dates = [
        dt for dt in iter_fact_dates(getattr(machine, "date_joining_fact", None))
        if dt.year == fact_year
    ]
    commission_dates = [
        dt for dt in iter_fact_dates(getattr(machine, "date_commission_fact", None))
        if dt.year == fact_year
    ]
    relabing_dates = [
        dt for dt in iter_fact_dates(getattr(machine, "date_relabing_fact", None))
        if dt.year == fact_year
    ]
    decommission_dates = [
        dt for dt in iter_fact_dates(getattr(machine, "date_decompressing_fact", None))
        if dt.year == fact_year
    ]

    for dt in joining_dates:
        note_parts.append(f"Присоединение {dt.strftime('%d.%m.%Y')}")
    for dt in commission_dates:
        # не дублируем ввод, если в тот же день уже есть присоединение
        if any(j == dt for j in joining_dates):
            continue
        note_parts.append(f"Ввод в эксплуатацию {dt.strftime('%d.%m.%Y')}")
    for dt in relabing_dates:
        note_parts.append(f"Перемаркировка {dt.strftime('%d.%m.%Y')}")
    for dt in decommission_dates:
        note_parts.append(f"Вывод из эксплуатации {dt.strftime('%d.%m.%Y')}")

    has_fact_commission_or_join = bool(joining_dates or commission_dates)

    # Плановый / карточный ввод (в т.ч. ручные ВЭС/СЭС и СНЭЭ), если нет факта текущего года
    if not has_fact_commission_or_join:
        planned_year = None
        for attr in (
            "date_exploitation_expected",
            "date_exploitation",
            "date_commission_year",
        ):
            y = extract_year(getattr(machine, attr, None))
            if y is not None and y in years and y >= fact_year:
                planned_year = y
                break
        if planned_year is not None:
            note_parts.append(f"Ввод в эксплуатацию в {planned_year} г.")

    # Плановый вывод — только если нет факта вывода в текущем году
    if not decommission_dates:
        y = extract_year(getattr(machine, "date_decompressing_expected", None))
        if y is not None and y in years and y >= fact_year:
            note_parts.append(f"Вывод из эксплуатации в {y} г.")

    # Плановая модернизация — не подменяем факт перемаркировки
    if not relabing_dates:
        y = extract_year(getattr(machine, "date_modernization_power_change_expected", None))
        if y is not None and y in years and y >= fact_year:
            note_parts.append(f"Модернизация (с изм. мощности) в {y} г.")
        y = extract_year(getattr(machine, "date_modernization_no_power_change_expected", None))
        if y is not None and y in years and y >= fact_year:
            note_parts.append(f"Модернизация (без изм. мощности) в {y} г.")

    return ". ".join(note_parts)


def keep_machine_for_appendix_a_as_of(
    machine: Any,
    *,
    as_of_date: date,
    sipr_start: int,
) -> bool:
    """
    Фильтр агрегатов на дату as_of (01.01.<sipr_start-1>):
    - факт вывода <= as_of → исключаем;
    - факт вывода > as_of → включаем;
    - плановый вывод: год >= as_of.year → включаем (в т.ч. вывод в течение as_of.year).
    """
    if bool(getattr(machine, "is_archived", False)):
        return False

    fact_dt = parse_date_value(getattr(machine, "date_decompressing_fact", None))
    if fact_dt is not None:
        return fact_dt > as_of_date

    expected_year = extract_year(getattr(machine, "date_decompressing_expected", None))
    if expected_year is None:
        return True
    return expected_year >= as_of_date.year


DPM_VIE_NOTE_TEXT = (
    "          Примечание – 1) В соответствии с Правилами оптового рынка электрической "
    "энергии и мощности, утвержденными постановлением Правительства Российской Федерации "
    "от 27.12.2010 № 1172, поставщики мощности по договорам о предоставлении мощности "
    "квалифицированных генерирующих объектов, функционирующих на основе использования "
    "возобновляемых источников энергии, заключенным по результатам отбора проектов, "
    "вправе изменить планируемое местонахождение генерирующего объекта. В соответствии "
    "с постановлением Правительства Российской Федерации от 20.05.2022 № 912 поставщик "
    "мощности по указанным договорам вправе до наступления даты начала поставки мощности "
    "осуществить отсрочку начала периода поставки мощности."
)
