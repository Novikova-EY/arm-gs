# -*- coding: utf-8 -*-

from unittest.mock import patch

from app.energy_balance.services.energy_balance_year_filter_services import (
    get_ee_default_end_year,
    get_ee_default_start_year,
    get_ee_period_base_year,
)


def test_ee_default_year_range_from_current_year():
    with patch(
        "app.energy_balance.services.energy_balance_year_filter_services.get_ges_tep_current_price_year_number",
        return_value=2026,
    ):
        assert get_ee_period_base_year() == 2026
        assert get_ee_default_start_year() == 2017
        assert get_ee_default_end_year() == 2026


def test_ee_default_year_range_fallback_to_filter_end_year():
    with patch(
        "app.energy_balance.services.energy_balance_year_filter_services.get_ges_tep_current_price_year_number",
        return_value=None,
    ), patch(
        "app.energy_balance.services.energy_balance_year_filter_services.get_filter_end_year",
        return_value=2030,
    ):
        assert get_ee_period_base_year() == 2030
        assert get_ee_default_start_year() == 2021
        assert get_ee_default_end_year() == 2030
