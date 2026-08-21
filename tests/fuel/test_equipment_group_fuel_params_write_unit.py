# -*- coding: utf-8 -*-
"""Разбор значений формы топливных параметров (в т.ч. вставка из UI с пробелами тысяч)."""
from decimal import Decimal

from app.fuel.services.equipment_groups.equipment_group_fuel_params_write_services import (
    _parse_fuel_param_value,
)


def test_parse_e_accepts_thousand_grouped_display():
    assert _parse_fuel_param_value("e", "1 234,5") == Decimal("1234.5")
    assert _parse_fuel_param_value("e", "1\u00a0234,56") == Decimal("1234.56")
    assert _parse_fuel_param_value("e", "1234.5") == Decimal("1234.5")


def test_parse_e_empty_and_dash():
    assert _parse_fuel_param_value("e", "") is None
    assert _parse_fuel_param_value("e", "—") is None
    assert _parse_fuel_param_value("e", None) is None


def test_parse_e_invalid_stays_none():
    assert _parse_fuel_param_value("e", "12 34abc") is None
