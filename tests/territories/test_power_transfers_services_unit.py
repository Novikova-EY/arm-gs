# -*- coding: utf-8 -*-
from decimal import Decimal

import pytest

from app.territories.services.power_transfers_services import (
    extract_power_transfer_year_values_from_form,
    load_power_transfer_year_values_map,
    parse_decimal_field,
    power_transfer_year_field_name,
)


def test_power_transfer_year_field_name():
    assert power_transfer_year_field_name(12, 2024) == "transfer_mln_12_2024"


def test_extract_year_values_from_form_empty_cells():
    form = {
        power_transfer_year_field_name(1, 2023): "",
        power_transfer_year_field_name(1, 2024): "1,5",
        power_transfer_year_field_name(2, 2024): "10",
    }
    result = extract_power_transfer_year_values_from_form(form, [1, 2], [2023, 2024])
    assert result[1][2023] is None
    assert result[1][2024] == Decimal("1.5")
    assert result[2][2023] is None
    assert result[2][2024] == Decimal("10")


def test_extract_year_values_invalid_raises():
    form = {power_transfer_year_field_name(1, 2023): "не число"}
    with pytest.raises(ValueError, match="Некорректное"):
        extract_power_transfer_year_values_from_form(form, [1], [2023])


def test_parse_decimal_field_strict():
    assert parse_decimal_field("  2,34  ", strict=True) == Decimal("2.34")
    with pytest.raises(ValueError):
        parse_decimal_field("x", strict=True)


def test_load_year_values_map_empty():
    assert load_power_transfer_year_values_map([], [2023]) == {}
    assert load_power_transfer_year_values_map([1], []) == {}
