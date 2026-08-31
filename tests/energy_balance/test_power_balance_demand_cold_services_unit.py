# -*- coding: utf-8 -*-
"""Юнит-тесты ручного ввода максимума для холодной пятидневки 0,92."""

from __future__ import annotations

import pytest

from app.energy_balance.services.power_balance_demand_cold_services import (
    DEMAND_MAX_COLD_ROW_KEY,
    load_power_balance_demand_cold_inputs,
    update_power_balance_demand_cold_value,
)


def test_cold_demand_row_key():
    assert DEMAND_MAX_COLD_ROW_KEY == "demand_max_cold_092"


def test_update_cold_demand_rejects_empty_slug():
    with pytest.raises(ValueError, match="лист"):
        update_power_balance_demand_cold_value("", 2026, "1")


def test_update_cold_demand_rejects_bad_year():
    with pytest.raises(ValueError, match="год"):
        update_power_balance_demand_cold_value("oes-417", "xx", "1")


def test_update_cold_demand_rejects_bad_number():
    with pytest.raises(ValueError, match="число"):
        update_power_balance_demand_cold_value("oes-417", 2026, "abc")


def test_load_cold_demand_inputs_empty_years():
    assert load_power_balance_demand_cold_inputs([]) == {}
