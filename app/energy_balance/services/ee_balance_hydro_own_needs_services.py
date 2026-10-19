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
    station_ids: list[int], station_type_key: str
) -> dict[int, Decimal]:
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
    return {
        int(row.id_station): Decimal(str(row.coefficient))
        for row in rows
    }


def save_hydro_own_needs_coefficient(
    station_id: int,
    station_type_key: str,
    raw_value: Any,
    *,
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

    query = filter_by_db_version(
        EeBalanceStationOwnNeedsCoefficient.query,
        EeBalanceStationOwnNeedsCoefficient,
    ).filter(
        EeBalanceStationOwnNeedsCoefficient.id_station == station_id,
        EeBalanceStationOwnNeedsCoefficient.station_type_key == station_type_key,
    )
    existing = query.one_or_none()
    previous_value = None if existing is None else existing.coefficient
    if coefficient is None:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
            _log_coefficient_change(
                user, station_id, station_name, station_type_key, previous_value, None
            )
        return None
    if existing is None:
        existing = EeBalanceStationOwnNeedsCoefficient(
            id_station=station_id,
            station_type_key=station_type_key,
            coefficient=coefficient,
            database_version_id=get_current_db_version_id(),
        )
        db.session.add(existing)
    else:
        existing.coefficient = coefficient
    _commit_with_retry()
    _log_coefficient_change(
        user, station_id, station_name, station_type_key, previous_value, coefficient
    )
    return Decimal(str(existing.coefficient))


def _log_coefficient_change(
    user: Any,
    station_id: int,
    station_name: str | None,
    station_type_key: str,
    old_value: Any,
    new_value: Any,
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
        ),
    )
