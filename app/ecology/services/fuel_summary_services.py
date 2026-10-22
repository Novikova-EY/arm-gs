"""Состав топливной сводки по признакам d, r и годовой мощности NUST групп."""
from collections import defaultdict
from decimal import Decimal

from app.ecology.services.fuel_summary_constants import FUEL_SUMMARY_LABELS
from app.ecology.services.operating_tes_constants import FUEL_MAIN_SUM_FIELDS, FUEL_EXTRA_SUM_FIELDS
from app.ecology.services.operating_tes_fuel_input_services import (
    _distribute, _load_group_territory_slugs, empty_fuel_bucket, load_group_fuel_rows,
)


class FuelSummaryError(ValueError):
    pass


def build_fuel_summary(years):
    """Возвращает суммы и ошибки отдельно по каждой категории, без записи в БД."""
    inputs = {scope: {year: defaultdict(empty_fuel_bucket) for year in years} for scope in FUEL_SUMMARY_LABELS}
    errors = {scope: [] for scope in FUEL_SUMMARY_LABELS}
    if not years:
        return inputs, errors
    rows_by_scope = {scope: load_group_fuel_rows(years, fuel_scope=scope) for scope in inputs}
    group_ids = {row[2] for rows in rows_by_scope.values() for row in rows}
    territories = _load_group_territory_slugs(group_ids)
    fields = FUEL_MAIN_SUM_FIELDS + FUEL_EXTRA_SUM_FIELDS
    for scope, rows in rows_by_scope.items():
        for year, ved, group_id, *amounts in rows:
            values = {field: Decimal(amount or 0) for field, amount in zip(fields, amounts)}
            if any(values.values()):
                _distribute(inputs[scope][year], ved, territories.get(group_id, set()), values)
    return inputs, errors


def load_fuel_summary(years, scope="operating"):
    inputs, errors = build_fuel_summary(years)
    if errors[scope]:
        raise FuelSummaryError("\n".join(errors[scope]))
    return inputs[scope]
