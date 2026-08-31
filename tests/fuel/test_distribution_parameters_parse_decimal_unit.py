# -*- coding: utf-8 -*-
from decimal import Decimal
from unittest.mock import patch

from app.common.services.help_services import format_decimal_trim_for_display
from app.fuel.services.distribution_parameters.distribution_parameters_save_services import (
    _parse_dp_row_from_form,
)
from app.fuel.services.distribution_parameters.import_distribution_parameters_services import (
    _parse_decimal,
)


def test_parse_decimal_accepts_thousand_grouped_display():
    """Как на /fuel/distribution_parameters: E ≥ 1000 показывается с пробелами тысяч."""
    assert _parse_decimal("12 345 678") == Decimal("12345678")
    assert _parse_decimal("12 345 678,5") == Decimal("12345678.5")
    assert _parse_decimal("1\u00a0234,56") == Decimal("1234.56")


def test_parse_decimal_roundtrip_e_from_page_display():
    original = Decimal("12345678.123456")
    shown = format_decimal_trim_for_display(original, digits=0)
    assert " " in shown
    assert _parse_decimal(shown) == original


def test_parse_decimal_empty_and_invalid_stay_none():
    assert _parse_decimal(None) is None
    assert _parse_decimal("") is None
    assert _parse_decimal("—") is None
    assert _parse_decimal("12 34abc") is None
    assert _parse_decimal(True) is None


def test_parse_dp_row_from_form_keeps_thousand_grouped_e():
    """Сохранение правки k/doptim не должно затирать E из-за пробелов тысяч в input."""
    form = {
        "dp_144_id_year": "10",
        "dp_144_id_union_energy_system": "311",
        "dp_144_id_base_year": "8",
        "dp_144_e": "12 345 678,5",
        "dp_144_k": "0,95",
        "dp_144_lim": "0",
    }
    with patch(
        "app.fuel.services.distribution_parameters.distribution_parameters_save_services.db.session.get",
        return_value=object(),
    ):
        parsed, errors = _parse_dp_row_from_form(form, "144", label="id=144")
    assert errors == []
    assert parsed is not None
    assert parsed["numeric"]["e"] == Decimal("12345678.5")
    assert parsed["numeric"]["k"] == Decimal("0.95")
