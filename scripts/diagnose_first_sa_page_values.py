#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Значения 1-й СЗ на странице /energy_consumption/summary/oes/ после формул."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2025


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
        codes = {
            "with_nt_with_gaes_kaliningrad": "с НТ с зарядом ГАЭС",
            "with_nt_without_gaes_kaliningrad": "с НТ без заряда ГАЭС",
            "without_nt_with_gaes_kaliningrad": "без НТ с зарядом ГАЭС",
            "without_nt_without_gaes_kaliningrad": "без НТ без заряда ГАЭС",
        }

        print(f"=== Страница /summary/oes/, год {YEAR} ===\n")
        page_vals: dict[str, str] = {}
        for row in ctx["summary_rows"]:
            if (
                row.get("demand_model_name")
                != "SynchronousAreaEnergyConsumptionParameter"
            ):
                continue
            code = str(row.get("perimeter_variant_code") or "")
            if code not in codes:
                continue
            if row.get("parameter_key") != "energy_consumption_mln_kvt_ch":
                continue
            val = (row.get("year_values") or [None] * len(years))[yi]
            tip = (row.get("year_numeric_tooltips") or [""])[yi]
            derived = row.get("pd_ec_formula_derived_row")
            page_vals[code] = str(val)
            print(f"{codes[code]}:")
            print(f"  на экране: {val}")
            print(f"  tooltip (точное): {tip}")
            print(f"  pd_ec_formula_derived_row: {derived}")
            ft = row.get("pd_ec_summary_row_formula_tooltip")
            if ft:
                print(f"  формула: {ft}")
            print()

        fid = svc._resolve_first_synchronous_area_id()
        pk = "energy_consumption_mln_kvt_ch"
        y = [YEAR]
        sum_wnt_wg = svc._year_values_sum_ues_in_first_sa_with_nt_with_gaes_with_kaliningrad_es(
            fid, y, pk
        )[YEAR]
        print("=== Компоненты расчёта (из кода, до UI) ===\n")
        print(f"Σ ОЭС (с НТ с зарядом): {sum_wnt_wg}")
        for ues_id in svc._union_energy_system_ids_for_synchronous_area(fid):
            if int(ues_id) in svc._first_sa_with_nt_with_gaes_ues_exclude_ids():
                continue
            from app.refdata.models.energy_systems.union_energy_system_model import (
                UnionEnergySystem,
            )

            ues = UnionEnergySystem.query.get(int(ues_id))
            vc = svc._first_sa_with_nt_with_gaes_ues_variant_codes_for_ues_id(int(ues_id))
            v = svc._year_values_from_ues_demand_first_variant_with_data(
                int(ues_id), y, pk, vc
            )[YEAR]
            mark = " ← Юг" if svc._resolve_union_energy_system_id_by_name_cf(
                svc.SOUTH_UES_NAME_CF
            ) == int(ues_id) else ""
            print(f"  + {ues.name if ues else ues_id}{mark}: {v} ({vc[0] if vc else '?'})")

        gaes_rows = [
            r
            for r in ctx["summary_rows"]
            if r.get("demand_model_name") == "SynchronousAreaEnergyConsumptionParameter"
            and r.get("parameter_key") == svc.GAES_CHARGE_PARAMETER_KEY
            and "с нт" in str(r.get("entity_label") or "").casefold()
            and "без нт" not in str(r.get("entity_label") or "").casefold()
        ]
        print("\nЗаряд ГAЭС (с НТ) на странице:")
        gaes_total = None
        for r in gaes_rows:
            name = r.get("gaes_charge_row_station_name") or r.get("entity_label")
            val = (r.get("year_values") or [None] * len(years))[yi]
            tip = (r.get("year_numeric_tooltips") or [""])[yi]
            print(f"  {name}: {val} (точное {tip})")
            if str(name).casefold() == "всего":
                gaes_total = tip or val

        if gaes_total and sum_wnt_wg:
            from decimal import Decimal

            diff = Decimal(str(sum_wnt_wg)) - Decimal(str(gaes_total))
            print(f"\nΣ ОЭС − заряд = {diff}")
            wnt_wg_page = page_vals.get("with_nt_with_gaes_kaliningrad")
            wnt_wog_page = page_vals.get("with_nt_without_gaes_kaliningrad")
            if wnt_wg_page and wnt_wog_page:
                d = Decimal(str(wnt_wg_page.replace(",", ".").replace(" ", ""))) - Decimal(
                    str(wnt_wog_page.replace(",", ".").replace(" ", ""))
                )
                print(f"Разница строк на экране (с зарядом − без): {d}")


if __name__ == "__main__":
    main()
