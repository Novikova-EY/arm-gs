# -*- coding: utf-8 -*-
"""Юнит-тесты ручного ввода «Экспорт мощности»."""

from __future__ import annotations

import pytest

from app.energy_balance.services.power_balance_export_services import (
    EXPORT_ROW_KEY,
    load_power_balance_export_inputs,
    update_power_balance_export_value,
)


def test_export_row_key():
    assert EXPORT_ROW_KEY == "export"


def test_update_export_rejects_empty_slug():
    with pytest.raises(ValueError, match="лист"):
        update_power_balance_export_value("", 2026, "1")


def test_update_export_rejects_bad_year():
    with pytest.raises(ValueError, match="год"):
        update_power_balance_export_value("centr", "xx", "1")


def test_update_export_rejects_bad_number():
    with pytest.raises(ValueError, match="число"):
        update_power_balance_export_value("centr", 2026, "abc")


def test_load_export_inputs_empty_years():
    assert load_power_balance_export_inputs([]) == {}
