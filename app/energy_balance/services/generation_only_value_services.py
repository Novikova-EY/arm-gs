"""Inline generation input for generation-only stations."""
from decimal import InvalidOperation

from app.extensions import db
from app.common.services.database_version_filter import filter_by_db_version, set_db_version_on_create
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.station_energy_generation_model import StationEnergyGeneration
from app.energy_balance.services.energy_balance_cache import clear_energy_balance_cache
from app.energy_balance.services.station_ee_generation_page_services import resolve_control_period
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.generation_only_visibility import generation_page_data
from app.logs.services.logging_service import log_to_db


@generation_page_data
def update_generation_only_value(station_id, period, raw_value, *, period_mode, selected_year, user):
    try:
        station_id = int(station_id)
        year, month = resolve_control_period(period, period_mode=period_mode, selected_year=selected_year)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверная станция или период") from exc
    station = filter_by_db_version(Station.query.filter(
        Station.id == station_id, Station.is_generation_only.is_(True)
    ), Station).first()
    if station is None:
        raise ValueError("Станция для агрегации не найдена в текущей версии БД")
    from app.refdata.models.years.year_model import Year
    if not filter_by_db_version(Year.query.filter(Year.number == year), Year).first():
        raise ValueError("Год отсутствует в текущей версии БД")
    try:
        value = parse_decimal_from_display(raw_value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Неверное число") from exc
    if value is not None and (not value.is_finite() or value < 0 or value >= 1000000000):
        raise ValueError("Введите неотрицательное число меньше 1 000 000 000")
    query = StationEnergyGeneration.query.filter_by(
        id_station=station_id, year_number=year, month_number=month,
    )
    record = filter_by_db_version(query, StationEnergyGeneration).one_or_none()
    previous = record.electricity_generation if record else None
    if value is None:
        if record:
            db.session.delete(record)
    else:
        if record is None:
            record = StationEnergyGeneration(id_station=station_id, year_number=year, month_number=month)
            set_db_version_on_create(record)
            db.session.add(record)
        record.electricity_generation = value
    _commit_with_retry()
    clear_energy_balance_cache()
    log_to_db(user, f"Выработка ЭЭ: {station.name}, {year}, месяц {month}: {previous} → {value}",
              entity_type="station", entity_id=station_id)
    return value
