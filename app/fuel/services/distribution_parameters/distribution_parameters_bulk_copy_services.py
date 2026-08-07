# -*- coding: utf-8 -*-
"""Данные для массового добавления строк параметров распределения по всем ОЭС."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import joinedload

from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
)
from app.common.services.get_services.years.years_get_services import get_year_list_full
from app.common.services.help_services import format_decimal_trim_for_display
from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.refdata.models.years.year_model import Year

_NUMERIC_ATTRS = (
    "e",
    "kplus",
    "kmin",
    "k",
    "bkl",
    "kn",
    "knps",
    "kngt",
    "knpg",
    "hnps",
    "hngt",
    "hnpg",
    "numb",
    "doptim",
)


def _year_ids_with_same_number(year_id: int) -> list[int]:
    """
    Все id справочника Year с тем же календарным номером, что и у year_id
    (как в get_distribution_parameters_list: разные database_version_id — разные строки).
    """
    y = db.session.get(Year, year_id)
    if y is None or y.number is None:
        return []
    return [
        row[0]
        for row in db.session.query(Year.id).filter(Year.number == y.number).all()
    ]


def _row_has_filled_values(dp: DistributionParameter) -> bool:
    """Есть ли в строке введённые данные (числа, lim, текст фильтра)."""
    if dp.lim is not None:
        return True
    if (dp.filter_text or "").strip():
        return True
    for attr in _NUMERIC_ATTRS:
        if getattr(dp, attr, None) is not None:
            return True
    return False


def _pick_source_row_for_ues(
    rows: list[DistributionParameter],
    *,
    target_year_number: int,
) -> DistributionParameter | None:
    """
    Строка-источник: заполненные данные, расчитываемый год (календарь) строго меньше целевого;
    из подходящих — с максимальным таким годом (крайний заполненный до целевого).
    """
    eligible: list[DistributionParameter] = []
    for dp in rows:
        ynum = dp.year.number if dp.year and dp.year.number is not None else None
        if ynum is None:
            continue
        if ynum >= target_year_number:
            continue
        if _row_has_filled_values(dp):
            eligible.append(dp)
    if not eligible:
        return None
    return max(eligible, key=lambda d: (d.year.number if d.year and d.year.number is not None else -1, d.id))


def _target_year_id_for_calendar_number(year_number: int) -> int | None:
    """Первый id года из справочника текущей версии с номером year_number."""
    for y in get_year_list_full():
        if y.number is not None and int(y.number) == int(year_number):
            return int(y.id)
    return None


def _numb_for_target_from_source(
    src: DistributionParameter,
    *,
    target_year_number: int,
) -> str:
    """
    Порядковый номер нарастающий по календарю: numbцель = numb_источник + (Nрасчёта − N_года_источника).

    Источник — строка с расчётным годом строго меньше целевого; при пропуске лет в справочнике
    (например с 2031 сразу 2033) шаг по numb равен разнице номеров лет, а не +1 от копии.
    """
    raw = getattr(src, "numb", None)
    if raw is None:
        return ""
    src_yn = src.year.number if src.year and src.year.number is not None else None
    if src_yn is None:
        return format_decimal_trim_for_display(raw, 0)
    try:
        delta = int(target_year_number) - int(src_yn)
    except (TypeError, ValueError):
        return format_decimal_trim_for_display(raw, 0)
    value = Decimal(str(raw)) + Decimal(delta)
    return format_decimal_trim_for_display(value, 0)


def _doptim_from_base_and_calculated_year(
    *,
    base_year_number: int,
    calculated_year_number: int,
) -> str:
    """
    Как в Access: UPDATE … SET doptim = 0.05 + 0.03 * ([year] - [базовый_год]);
    здесь year — календарный номер расчётного года, базовый_год — календарный номер базового.

    Форматирование с digits=0 — полная точность, без округления под отображение страницы.
    """
    delta = int(calculated_year_number) - int(base_year_number)
    value = Decimal("0.05") + Decimal("0.03") * Decimal(delta)
    return format_decimal_trim_for_display(value, 0)


def build_distribution_parameters_bulk_copy_rows(
    *,
    id_base_year: int,
    id_year_target: int,
    rounding_digits: int = 0,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """
    В ответ попадают только ОЭС, у которых для выбранного базового года есть заполненная
    строка с расчитываемым годом меньше целевого; значения копируются из крайней такой
    строки (макс. год среди них). Цель: id_base_year + id_year_target.
    Строка с уже существующей парой «базовый + расчётный год» в БД не исключается: те же
    данные возвращаются для подстановки в таблицу (перезапись полей при сохранении).

    Исключение: поле doptim не копируется — выставляется как в Access:
    0.05 + 0.03 * (календарный расчётный год − календарный базовый год).

    Поле numb не копируется с источника: numbцель = numb_источник + (Nрасчёта − N_года_источника),
    где N — календарные номера расчётного года целевой строки и строки-источника.

    Поле e (выработка ТЭС) не копируется: в подстановку уходит пустое значение.

    Числа с источника сериализуются с полной точностью из БД (digits=0), а не с округлением
    из параметра rounding_digits страницы — чтобы в новые строки не попадали усечённые значения.

    Returns:
        (rows, errors, stats) — при непустых errors строки не использовать; stats для подсказок в UI.
    """
    errors: list[str] = []
    empty_stats: dict[str, Any] = {}

    base_year_ids = _year_ids_with_same_number(id_base_year)
    if not base_year_ids:
        errors.append("Базовый год не найден в справочнике.")
        return [], errors, empty_stats
    base_year_ent = db.session.get(Year, id_base_year)
    if base_year_ent is None or base_year_ent.number is None:
        errors.append("У базового года не задан номер в справочнике.")
        return [], errors, empty_stats
    base_year_number = int(base_year_ent.number)
    target_year = db.session.get(Year, id_year_target)
    if target_year is None:
        errors.append("Расчитываемый год не найден в справочнике.")
        return [], errors, empty_stats
    if target_year.number is None:
        errors.append("У целевого года не задан номер в справочнике.")
        return [], errors, empty_stats
    target_year_number = int(target_year.number)
    target_year_ids = _year_ids_with_same_number(id_year_target)
    if not target_year_ids:
        errors.append("Расчитываемый год не найден в справочнике.")
        return [], errors, empty_stats

    all_for_base = (
        DistributionParameter.query.filter(
            DistributionParameter.id_base_year.in_(base_year_ids),
        )
        .options(joinedload(DistributionParameter.year))
        .all()
    )
    by_ues_lists: dict[int | None, list[DistributionParameter]] = defaultdict(list)
    for dp in all_for_base:
        by_ues_lists[dp.id_union_energy_system].append(dp)

    existing_target = (
        DistributionParameter.query.filter(
            DistributionParameter.id_base_year.in_(base_year_ids),
            DistributionParameter.id_year.in_(target_year_ids),
        )
        .all()
    )
    target_ues_ids = {dp.id_union_energy_system for dp in existing_target}

    out: list[dict[str, Any]] = []
    n_skip_no_source = 0
    for ues in get_union_energy_system_list_full():
        uid = ues.id
        src = _pick_source_row_for_ues(
            by_ues_lists.get(uid, []),
            target_year_number=target_year_number,
        )
        if src is None:
            n_skip_no_source += 1
            continue
        numeric: dict[str, str] = {}
        lim_v = src.lim
        for attr in _NUMERIC_ATTRS:
            if attr in ("e", "numb", "doptim"):
                continue
            raw = getattr(src, attr, None)
            if raw is None:
                numeric[attr] = ""
            else:
                numeric[attr] = format_decimal_trim_for_display(raw, 0)

        numeric["e"] = ""
        numeric["numb"] = _numb_for_target_from_source(
            src,
            target_year_number=target_year_number,
        )
        numeric["doptim"] = _doptim_from_base_and_calculated_year(
            base_year_number=base_year_number,
            calculated_year_number=target_year_number,
        )

        out.append(
            {
                "id_union_energy_system": uid,
                "id_base_year": id_base_year,
                "id_year": id_year_target,
                "numeric": numeric,
                "lim": lim_v,
            }
        )

    stats: dict[str, Any] = {
        "dp_rows_for_base": len(all_for_base),
        "ues_with_target_row_in_db": len(target_ues_ids),
        "ues_skip_already_have_target": 0,
        "ues_skip_no_filled_source_before_target": n_skip_no_source,
        "new_rows_returned": len(out),
        "numeric_full_db_precision": True,
        "request_rounding_digits_ignored": rounding_digits,
    }
    return out, [], stats


def build_distribution_parameters_bulk_copy_rows_for_period(
    *,
    id_base_year: int,
    id_year_from: int,
    id_year_to: int,
    rounding_digits: int = 0,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """
    Для каждого календарного года расчёта от id_year_from до id_year_to (по номерам годов,
    границы включаются) формирует строки так же, как build_distribution_parameters_bulk_copy_rows.
    Порядок годов в ответе: по возрастанию номера года, внутри года — порядок ОЭС как в справочнике.
    """
    empty_stats: dict[str, Any] = {}
    y_from = db.session.get(Year, id_year_from)
    y_to = db.session.get(Year, id_year_to)
    if y_from is None or y_from.number is None:
        return [], ["Начало периода (расчитываемый год) не найдено в справочнике."], empty_stats
    if y_to is None or y_to.number is None:
        return [], ["Конец периода (расчитываемый год) не найден в справочнике."], empty_stats
    n_a = int(y_from.number)
    n_b = int(y_to.number)
    n_lo, n_hi = (n_a, n_b) if n_a <= n_b else (n_b, n_a)

    missing_numbers = [
        n
        for n in range(n_lo, n_hi + 1)
        if _target_year_id_for_calendar_number(n) is None
    ]
    if missing_numbers:
        return (
            [],
            [
                "Для номеров лет нет записей в справочнике текущей версии БД: "
                + ", ".join(str(x) for x in missing_numbers)
            ],
            {"period_from": n_lo, "period_to": n_hi, "missing_year_numbers_in_refdata": missing_numbers},
        )

    all_rows: list[dict[str, Any]] = []
    for n in range(n_lo, n_hi + 1):
        tid = _target_year_id_for_calendar_number(n)
        if tid is None:
            continue
        chunk, errs, _st = build_distribution_parameters_bulk_copy_rows(
            id_base_year=id_base_year,
            id_year_target=tid,
            rounding_digits=rounding_digits,
        )
        if errs:
            return [], errs, empty_stats
        all_rows.extend(chunk)

    stats: dict[str, Any] = {
        "period_from": n_lo,
        "period_to": n_hi,
        "calendar_years_count": n_hi - n_lo + 1,
        "new_rows_returned": len(all_rows),
        "numeric_full_db_precision": True,
        "request_rounding_digits_ignored": rounding_digits,
    }
    return all_rows, [], stats
