# -*- coding: utf-8 -*-
"""Границы годов вариантов периметра «с НТ»."""

from __future__ import annotations

from app.common.perimeter_variant.constants import WITH_NT_EFFECTIVE_FROM_YEAR
from app.common.perimeter_variant.registry import perimeter_variant_year_bounds_for_code
from app.power_demand.services.demand_summary_services import (
    mask_power_demand_summary_rows_perimeter_variant_year_display,
)


def test_with_nt_legacy_group_year_bounds_from_2023() -> None:
    for code in ("with_nt", "with_nt_without_gaes", "with_nt_with_gaes"):
        fy, ty = perimeter_variant_year_bounds_for_code(code)
        assert fy == WITH_NT_EFFECTIVE_FROM_YEAR == 2023
        assert ty is None


def test_mask_power_demand_summary_hides_years_before_with_nt_from_year() -> None:
    years = [2022, 2023, 2024]
    rows = [
        {
            "perimeter_variant_code": "with_nt_without_gaes",
            "year_values": ["100", "200", "300"],
            "year_numeric_tooltips": ["100", "200", "300"],
            "year_row_ids": [1, 2, 3],
        }
    ]
    mask_power_demand_summary_rows_perimeter_variant_year_display(rows, years)
    row = rows[0]
    assert row["perimeter_variant_from_year"] == 2023
    assert row["year_values"] == ["—", "200", "300"]
    assert row["year_row_ids"] == [None, 2, 3]
