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
    station_id: int, station_type_key: str, raw_value: Any
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
    if coefficient is None:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
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
    return Decimal(str(existing.coefficient))
