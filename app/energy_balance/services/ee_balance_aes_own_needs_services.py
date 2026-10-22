"""Сохранение годовых собственных нужд АЭС и их процента."""
from decimal import InvalidOperation

from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.station_energy_generation_model import (
    STATION_ENERGY_GENERATION_PERIOD_YEAR,
    StationEnergyGeneration,
)
from app.energy_balance.services.change_log_services import log_cell_change
from app.extensions import db
from app.generation.services.station_services.station_services import (
    station_annual_energy_generation_query,
)


def save_aes_own_needs(station, year, raw_value, version_id, *, user=None, kind="own_needs"):
    if kind not in {"own_needs", "own_needs_percent"}:
        raise ValueError("Неверный показатель СН")
    try:
        value = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверное значение СН") from exc
    if value is not None and (not value.is_finite() or value < 0):
        raise ValueError("СН должны быть неотрицательным числом")

    row = station_annual_energy_generation_query(
        station.id, year, year, version_id
    ).one_or_none()
    if kind == "own_needs_percent" and row is not None and row.own_needs is not None:
        raise ValueError("СН, % рассчитывается автоматически, пока заполнено СН, млн.кВт·ч")
    previous = getattr(row, kind) if row is not None else None
    if previous == value:
        return value
    if row is None:
        row = StationEnergyGeneration(
            id_station=station.id,
            year_number=year,
            month_number=STATION_ENERGY_GENERATION_PERIOD_YEAR,
            database_version_id=version_id,
        )
        db.session.add(row)
    setattr(row, kind, value)
    try:
        _commit_with_retry()
    except Exception:
        db.session.rollback()
        raise
    log_cell_change(
        user,
        "Изменения в балансе ЭЭ, собственные нужды АЭС",
        "СН, %" if kind == "own_needs_percent" else "СН, млн.кВт·ч",
        previous,
        value,
        context=f"Станция: {station.name}, {year} г.",
    )
    return value
