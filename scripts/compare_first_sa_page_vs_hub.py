#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сравнение значений 1-й СЗ: формулы на странице vs hub-sync."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2025


def _val(row, yi):
    return (row.get("year_values") or [None])[yi]


def main() -> None:
    from app import create_app
    from app.energy_consumption.pages.summary_oes_page_services import (
        build_summary_oes_page_context,
    )
    from app.energy_consumption.services import energy_consumption_summary_services as svc

    app = create_app()
    with app.app_context():
        ctx = build_summary_oes_page_context(
            1,
            start_year=2016,
            end_year=2031,
            data_start_year=2016,
            data_end_year=2031,
            filter_year_list=list(range(2016, 2032)),
            oes_territory_ordered=([], [], [], []),
            coeff_base_year=2024,
            include_medium_years=True,
            can_edit_summary_cells=False,
        )
        years = list(ctx["years"])
        yi = years.index(YEAR)
        codes = (
            "with_nt_with_gaes_kaliningrad",
            "with_nt_without_gaes_kaliningrad",
            "without_nt_with_gaes_kaliningrad",
            "without_nt_without_gaes_kaliningrad",
        )
        print("=== PAGE (full pipeline) ===")
        for row in ctx["summary_rows"]:
            if row.get("demand_model_name") != "SynchronousAreaEnergyConsumptionParameter":
                continue
            code = str(row.get("perimeter_variant_code") or "")
            if code not in codes or row.get("parameter_key") != "energy_consumption_mln_kvt_ch":
                continue
            print(f"  {code}: {_val(row, yi)}")

        hub = svc.build_summary_table_hub_oes_formula_pipeline_summary_rows(
            1,
            start_year=2016,
            end_year=2031,
            data_start_year=2016,
            data_end_year=2031,
            filter_year_list=list(range(2016, 2032)),
        )
        print("\n=== HUB pipeline ===")
        for row in hub:
            if row.get("demand_model_name") != "SynchronousAreaEnergyConsumptionParameter":
                continue
            code = str(row.get("perimeter_variant_code") or "")
            if code not in codes or row.get("parameter_key") != "energy_consumption_mln_kvt_ch":
                continue
            print(f"  {code}: {_val(row, yi)}")


if __name__ == "__main__":
    main()
