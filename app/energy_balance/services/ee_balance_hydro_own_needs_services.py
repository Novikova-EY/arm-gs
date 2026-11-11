# -*- coding: utf-8 -*-
"""Сохранение коэффициентов СН для станций ГЭС и ГАЭС."""
from decimal import Decimal, InvalidOperation
from typing import Any

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.ee_balance_station_own_needs_coefficient_model import (
    EeBalanceStationOwnNeedsCoefficient,
)
from app.extensions import db


HYDRO_STATION_TYPE_KEYS = frozenset({"ges", "gaes"})


def load_hydro_own_needs_coefficients(
    station_ids: list[int], station_type_key: str, years: list[int] | None = None
) -> dict[int, Decimal] | dict[int, dict[int, Decimal | None]]:
    if not station_ids:
        return {}
    rows = (
        filter_by_db_version(
            EeBalanceStationOwnNeedsCoefficient.query,
            EeBalanceStationOwnNeedsCoefficient,
        )
        .filter(
            EeBalanceStationOwnNeedsCoefficient.id_station.in_(station_ids),
            EeBalanceStationOwnNeedsCoefficient.station_type_key == station_type_key,
        )
        .all()
    )
    defaults = {
        int(row.id_station): Decimal(str(row.coefficient))
        for row in rows if row.year_number is None and row.coefficient is not None
    }
    if years is None:
        return defaults
    coefficients = {
        station_id: {year: defaults.get(station_id) for year in years}
        for station_id in station_ids
    }
    for row in rows:
        if row.year_number in years:
            coefficients[int(row.id_station)][row.year_number] = (
                Decimal(str(row.coefficient)) if row.coefficient is not None else None
            )
    return coefficients


def save_hydro_own_needs_coefficient(
    station_id: int,
    station_type_key: str,
    raw_value: Any,
    *,
    year: int | None = None,
    end_year: int | None = None,
    user: Any = None,
    station_name: str | None = None,
) -> Decimal | None:
    if station_type_key not in HYDRO_STATION_TYPE_KEYS:
        raise ValueError("Коэффициент доступен только для ГЭС и ГАЭС")
    try:
        coefficient = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверный коэффициент") from exc
    if coefficient is not None and (
        not coefficient.is_finite() or coefficient < 0
    ):
        raise ValueError("Коэффициент должен быть неотрицательным числом")

    if end_year is not None and (
        station_type_key != "ges" or year is None or end_year < year or end_year - year > 200
    ):
        raise ValueError("Неверный период пролонгации СН")
    years = list(range(year, end_year + 1)) if end_year is not None and coefficient is not None else [year]
    query = filter_by_db_version(
        EeBalanceStationOwnNeedsCoefficient.query,
        EeBalanceStationOwnNeedsCoefficient,
    ).filter(
        EeBalanceStationOwnNeedsCoefficient.id_station == station_id,
        EeBalanceStationOwnNeedsCoefficient.station_type_key == station_type_key,
    )
    if year is None:
        existing = query.filter(EeBalanceStationOwnNeedsCoefficient.year_number == year).one_or_none()
        existing_by_year = {None: existing} if existing is not None else {}
        previous_values = {None: existing.coefficient if existing is not None else None}
    else:
        existing_by_year = {
            row.year_number: row for row in query.filter(
                EeBalanceStationOwnNeedsCoefficient.year_number.in_(years)
            ).all()
        }
        previous_values = load_hydro_own_needs_coefficients([station_id], station_type_key, years)[station_id]
    for target_year in years:
        existing = existing_by_year.get(target_year)
        if coefficient is None and target_year is None:
            if existing is not None:
                db.session.delete(existing)
        elif existing is None:
            db.session.add(EeBalanceStationOwnNeedsCoefficient(
                id_station=station_id,
                station_type_key=station_type_key,
                year_number=target_year,
                coefficient=coefficient,
                database_version_id=get_current_db_version_id(),
            ))
        else:
            existing.coefficient = coefficient
    _commit_with_retry()
    for target_year in years:
        _log_coefficient_change(
            user, station_id, station_name, station_type_key, previous_values[target_year], coefficient,
            year=target_year,
        )
    return coefficient


def _log_coefficient_change(
    user: Any,
    station_id: int,
    station_name: str | None,
    station_type_key: str,
    old_value: Any,
    new_value: Any,
    *,
    year: int | None = None,
) -> None:
    from app.energy_balance.services.change_log_services import log_cell_change

    log_cell_change(
        user,
        "Изменения в балансе ЭЭ, коэффициент собственных нужд ГЭС/ГАЭС",
        "Коэффициент собственных нужд",
        old_value,
        new_value,
        context=(
            f"Станция: {station_name or f'id={station_id}'} "
            f"({station_type_key.upper()})"
            + (f", {year} г." if year is not None else "")
        ),
    )
