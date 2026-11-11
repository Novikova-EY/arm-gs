"""Локальные для баланса параметры групп электростанций."""
from decimal import InvalidOperation

from app.common.services.database_version_filter import filter_by_db_version, get_current_db_version_id
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.ee_balance_station_group_value_model import EeBalanceStationGroupValue
from app.energy_balance.services.change_log_services import log_cell_change
from app.energy_balance.services.energy_balance_cache import clear_energy_balance_cache
from app.extensions import db

GROUP_PAGE_KEYS = {"aes", "ges", "ses-ves"}
GROUP_VALUE_KINDS = {"energy", "own_needs", "own_needs_percent"}


def load_group_values(group_ids, page_key, years):
    if not group_ids:
        return {}
    rows = filter_by_db_version(EeBalanceStationGroupValue.query, EeBalanceStationGroupValue).filter(
        EeBalanceStationGroupValue.id_station_group.in_(group_ids),
        EeBalanceStationGroupValue.page_key == page_key,
        EeBalanceStationGroupValue.year_number.in_(years),
    ).all()
    return {(row.id_station_group, row.year_number): row for row in rows}


def save_group_value(group, page_key, year, kind, raw_value, *, user, end_year=None):
    if page_key not in GROUP_PAGE_KEYS or kind not in GROUP_VALUE_KINDS:
        raise ValueError("Неверный показатель группы")
    try:
        value = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверное числовое значение") from exc
    if value is not None and (not value.is_finite() or value < 0):
        raise ValueError("Значение должно быть неотрицательным числом")
    if kind == "own_needs_percent" and value is not None and value > 100:
        raise ValueError("СН, % не могут превышать 100")
    last_year = year if end_year is None else end_year
    if not 1900 <= year <= last_year <= 2200:
        raise ValueError("Неверный год или период СН")
    years = range(year, last_year + 1) if kind == "own_needs_percent" and value is not None else [year]
    rows = load_group_values([group.id], page_key, years)
    selected = rows.get((group.id, year))
    if kind == "own_needs_percent" and selected is not None and selected.own_needs is not None:
        raise ValueError("СН, % рассчитывается автоматически, пока заполнено СН, млн.кВт·ч")
    changes = []
    for target_year in years:
        row = rows.get((group.id, target_year))
        if kind == "own_needs_percent" and row is not None and row.own_needs is not None:
            continue
        previous = getattr(row, kind) if row is not None else None
        if previous == value:
            continue
        if row is None:
            row = EeBalanceStationGroupValue(id_station_group=group.id, page_key=page_key,
                year_number=target_year, database_version_id=get_current_db_version_id())
            db.session.add(row)
        setattr(row, kind, value)
        changes.append((target_year, previous))
    if changes:
        try:
            _commit_with_retry()
        except Exception:
            db.session.rollback()
            raise
        if kind == "energy":
            clear_energy_balance_cache()
        for target_year, previous in changes:
            log_cell_change(user, "Изменения параметров групп в балансе ЭЭ", kind, previous, value,
                            context=f"Группа: {group.name}, {page_key}, {target_year} г.")
    return value
