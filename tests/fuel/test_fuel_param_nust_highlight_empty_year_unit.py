# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    build_fuel_param_row_warn_sets,
)


class _EmptyYear:
    """Как _MissingYearFuelParam: год есть, записи параметров нет."""

    def __init__(self, year_number: int):
        self.year_number = year_number
        self.database_version_id = 1

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, name: str):
        return None


def _eg(eid: int):
    return SimpleNamespace(id=eid)


def _param(year: int, **kwargs):
    ns = SimpleNamespace(year_number=year, database_version_id=1)
    for key, value in kwargs.items():
        setattr(ns, key, value)
    return ns


def _changed_keys(rows):
    return build_fuel_param_row_warn_sets(rows)["nust_changed_from_prev_year_rows"]


@patch(
    "app.fuel.services.calculation.fuel_calculation_edit_data_services._bulk_fuel_params_by_group_and_years",
    return_value={},
)
def test_empty_year_is_not_highlighted_and_next_year_compares_to_prior(_mock_load):
    eg = _eg(10)
    rows = [
        (eg, _param(2024, nust=100, qotr=10)),
        (eg, _EmptyYear(2025)),
        (eg, _param(2026, nust=100, qotr=10)),
    ]
    changed = _changed_keys(rows)
    assert "10:2025" not in changed
    assert "10:2026" not in changed


@patch(
    "app.fuel.services.calculation.fuel_calculation_edit_data_services._bulk_fuel_params_by_group_and_years",
    return_value={},
)
def test_nust_change_after_empty_year_uses_year_before(_mock_load):
    eg = _eg(10)
    rows = [
        (eg, _param(2024, nust=100, qotr=10)),
        (eg, _EmptyYear(2025)),
        (eg, _param(2026, nust=150, qotr=10)),
    ]
    changed = _changed_keys(rows)
    assert "10:2025" not in changed
    assert "10:2026" in changed
    assert "10:2026" in build_fuel_param_row_warn_sets(rows)["qotr_composition_warn_rows"]


@patch(
    "app.fuel.services.calculation.fuel_calculation_edit_data_services._bulk_fuel_params_by_group_and_years",
    return_value={},
)
def test_adjacent_years_still_compare_directly(_mock_load):
    eg = _eg(10)
    rows = [
        (eg, _param(2024, nust=100)),
        (eg, _param(2025, nust=150)),
    ]
    changed = _changed_keys(rows)
    assert "10:2025" in changed
    assert "10:2024" not in changed
