# -*- coding: utf-8 -*-
"""Разбор мощностей из UI: пробелы тысяч и запятая не ломают DecimalField."""

from decimal import Decimal

from app.generation.services.machine_services.machine_services import (
    _canonical_numeric_form_value,
    _is_machine_power_numeric_form_key,
    to_decimal,
)

_SUFFIXES = ("p_ust", "p_ogr", "p_rasp", "thermal_power_gcalh")


def test_power_form_keys_include_orig():
    assert _is_machine_power_numeric_form_key("adv_powers-9-p_ust", _SUFFIXES)
    assert _is_machine_power_numeric_form_key("adv_powers-9-p_ust_orig", _SUFFIXES)
    assert _is_machine_power_numeric_form_key("adv_powers-10-p_ogr", _SUFFIXES)
    assert not _is_machine_power_numeric_form_key("main_machine_name", _SUFFIXES)


def test_canonical_numeric_form_value_strips_thousand_spaces():
    assert _canonical_numeric_form_value("1 234,0") == "1234.0"
    assert _canonical_numeric_form_value("1 234,5") == "1234.5"
    assert _canonical_numeric_form_value("—") == ""
    assert _canonical_numeric_form_value("") == ""


def test_to_decimal_accepts_grouped_display():
    assert to_decimal("1 234,0") == Decimal("1234.0")
    assert to_decimal("—") is None
    assert to_decimal("90,5") == Decimal("90.5")
