# -*- coding: utf-8 -*-
"""Границы годов вариантов периметра «с НТ»."""

from __future__ import annotations

from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
    WITH_NT_EFFECTIVE_FROM_YEAR,
)

CODE_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_ES = (
    "without_nt_without_gaes_with_kaliningrad_es"
)
from app.common.perimeter_variant.registry import perimeter_variant_year_bounds_for_code
from app.power_demand.services import demand_parameter_services as dps
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


def test_mask_power_demand_unrestricted_perimeter_variant_input_keeps_all_years() -> None:
    """На /summary/oes|fo|ez строки с вариантом ≠ «не указано» не маскируются по Год с/по."""
    years = [2022, 2023, 2024]
    rows = [
        {
            "perimeter_variant_code": "with_nt_without_gaes",
            "year_values": ["100", "200", "300"],
            "year_numeric_tooltips": ["100", "200", "300"],
            "year_row_ids": [1, 2, 3],
        },
        {
            "perimeter_variant_code": None,
            "year_values": ["10", "20", "30"],
            "year_numeric_tooltips": ["10", "20", "30"],
            "year_row_ids": [4, 5, 6],
        },
    ]
    mask_power_demand_summary_rows_perimeter_variant_year_display(
        rows,
        years,
        unrestricted_perimeter_variant_input=True,
    )
    coded = rows[0]
    assert coded.get("pd_pd_skip_perimeter_variant_year_bounds") is True
    # Границы оставляем для формул / live JS даже при неограниченном вводе.
    assert coded.get("perimeter_variant_from_year") == 2023
    assert coded["year_values"] == ["100", "200", "300"]
    assert coded["year_row_ids"] == [1, 2, 3]

    unset = rows[1]
    assert unset.get("pd_pd_skip_perimeter_variant_year_bounds") is not True
    assert unset["year_values"] == ["10", "20", "30"]


def test_first_sa_with_kaliningrad_variant_has_no_year_bounds() -> None:
    for code in (
        CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
        CODE_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_ES,
    ):
        fy, ty = perimeter_variant_year_bounds_for_code(code)
        assert fy is None
        assert ty is None


def test_first_sa_without_kaliningrad_variant_year_bounds_from_2025() -> None:
    fy, ty = perimeter_variant_year_bounds_for_code(
        CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES
    )
    assert fy == 2025
    assert ty is None


def test_kaliningrad_sync_area_year_bounds_fallback_from_2025() -> None:
    from app.common.perimeter_variant.constants import (
        KALININGRAD_SYNC_AREA_EFFECTIVE_FROM_YEAR,
    )
    from app.common.perimeter_variant.registry import kaliningrad_sync_area_year_bounds

    fy, ty = kaliningrad_sync_area_year_bounds()
    assert fy == KALININGRAD_SYNC_AREA_EFFECTIVE_FROM_YEAR == 2025
    assert ty is None


def test_mask_power_demand_kaliningrad_sa_null_variant_from_2025() -> None:
    years = [2024, 2025, 2026]
    rows = [
        {
            "entity_label": "Синхронная зона Калининградской области",
            "demand_model_name": "SynchronousAreaDemandParameter",
            "perimeter_variant_code": None,
            "year_values": ["100", "200", "300"],
            "year_numeric_tooltips": ["100", "200", "300"],
            "year_row_ids": [1, 2, 3],
        }
    ]
    mask_power_demand_summary_rows_perimeter_variant_year_display(rows, years)
    row = rows[0]
    assert row["perimeter_variant_from_year"] == 2025
    assert row["year_values"] == ["—", "200", "300"]
    assert row["year_row_ids"] == [None, 2, 3]


def test_mask_power_demand_summary_keeps_2025_for_first_sa_with_kaliningrad() -> None:
    years = [2024, 2025, 2026]
    rows = [
        {
            "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_ES,
            "year_values": ["100", "200", "300"],
            "year_numeric_tooltips": ["100", "200", "300"],
            "year_row_ids": [1, 2, 3],
        },
        {
            "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
            "year_values": ["10", "20", "30"],
            "year_numeric_tooltips": ["10", "20", "30"],
            "year_row_ids": [4, 5, 6],
        },
    ]
    mask_power_demand_summary_rows_perimeter_variant_year_display(rows, years)
    with_kal = rows[0]
    without_kal = rows[1]
    assert "perimeter_variant_to_year" not in with_kal
    assert with_kal["year_values"] == ["100", "200", "300"]
    assert with_kal["year_row_ids"] == [1, 2, 3]
    assert without_kal["perimeter_variant_from_year"] == 2025
    assert without_kal["year_values"] == ["—", "20", "30"]
    assert without_kal["year_row_ids"] == [None, 5, 6]


def test_save_demand_summary_cell_allows_2025_for_first_sa_with_kaliningrad() -> None:
    dps._assert_perimeter_variant_year_allowed(
        CODE_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_ES,
        2025,
    )
