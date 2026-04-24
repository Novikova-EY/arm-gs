# -*- coding: utf-8 -*-
"""Обратная совместимость: реэкспорт из ``tep_capital_cost_current_year_services``."""

from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
    create_price_conversion_coefficient,
    delete_price_conversion_coefficient,
    get_price_coefficients_snapshot,
    get_tep_price_coefficient_by_year_map,
    update_price_conversion_coefficient,
    update_price_conversion_coefficient_from_request,
)

__all__ = (
    "create_price_conversion_coefficient",
    "delete_price_conversion_coefficient",
    "get_price_coefficients_snapshot",
    "get_tep_price_coefficient_by_year_map",
    "update_price_conversion_coefficient",
    "update_price_conversion_coefficient_from_request",
)
