# -*- coding: utf-8 -*-
"""
Прогон АРМ: Коэфф → Распред → Топливо по всем параметрам распределения
за 2026–2031 (как эталон Access, без ограничений).

  python scripts/run_arm_fuel_three_buttons.py
  python scripts/run_arm_fuel_three_buttons.py --oes 1 --year 2026
  python scripts/run_arm_fuel_three_buttons.py --db-version-id 37 --no-fuel
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from app import create_app
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.services.calculation.coefficient.fuel_coefficient_calculation_services import (
    FuelCoefficientCalculationService,
)
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
    d0,
)
from app.fuel.services.calculation.equipment_group_selection import (
    participating_group_ids_for_year,
)
from app.fuel.services.calculation.fuel.fuel_stage_services import FuelStageService
from app.fuel.services.equipment_groups.equipment_group_fuel_batch_calculation_services import (
    EquipmentGroupFuelBatchCalculationService,
)

YEARS = (2026, 2027, 2028, 2029, 2030, 2031)


def _oes_from_filter(text: str | None) -> int | None:
    m = re.search(r"oes\s*=\s*(\d+)", text or "", flags=re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1))


def main() -> int:
    parser = argparse.ArgumentParser(description="АРМ: Коэфф / Распред / Топливо по ОЭС×годам")
    parser.add_argument("--oes", type=int, default=None)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--db-version-id", type=int, default=int(os.environ.get("FUEL_DB_VERSION_ID", "37")))
    parser.add_argument("--apply-restrictions", action="store_true")
    parser.add_argument("--no-coeff", action="store_true")
    parser.add_argument("--no-dist", action="store_true")
    parser.add_argument("--no-fuel", action="store_true")
    args = parser.parse_args()
    years = (args.year,) if args.year else YEARS

    app = create_app()
    with app.app_context():
        dps = DistributionParameter.query.filter(
            DistributionParameter.database_version_id == args.db_version_id,
        ).all()
        selected: list[DistributionParameter] = []
        for dp in dps:
            y = dp.year.number if dp.year else None
            oes = _oes_from_filter(dp.filter_text)
            if y not in years:
                continue
            if args.oes is not None and oes != args.oes:
                continue
            selected.append(dp)
        selected.sort(
            key=lambda dp: (
                _oes_from_filter(dp.filter_text) or 99,
                dp.year.number if dp.year else 0,
                dp.id,
            )
        )
        if not selected:
            print("нет параметров распределения под фильтр")
            return 1

        coeff_svc = FuelCoefficientCalculationService()
        dist_svc = DistributionStageService()
        fuel_svc = FuelStageService()
        batch_svc = EquipmentGroupFuelBatchCalculationService()

        for dp in selected:
            oes = _oes_from_filter(dp.filter_text)
            year = dp.year.number
            name = dp.union_energy_system.name if dp.union_energy_system else None
            print(
                f"\n======== oes={oes} {year} dp_id={dp.id} {name} "
                f"e={dp.e} filter={dp.filter_text} ========"
            )
            if not args.no_coeff:
                cres = coeff_svc.run_for_distribution_parameter(dp.id, commit=True)
                print(
                    f"coeff groups={cres.total_groups} "
                    f"updated={cres.updated_fuel_rows} summary={cres.summary_id}"
                )
            if not args.no_dist:
                dres = dist_svc.run_for_distribution_parameter(
                    distribution_parameter_id=dp.id,
                    database_version_id=args.db_version_id,
                    apply_restrictions=args.apply_restrictions,
                    commit=True,
                )
                print(
                    f"dist updated={dres.updated_fuel_rows} "
                    f"sumE={dres.total_distributed_e} k={dres.final_k} kn={dres.final_kn} "
                    f"iters={dres.iterations}"
                )
            if args.no_fuel:
                continue
            readiness = fuel_svc.get_readiness(dp.id)
            print(
                f"fuel ready={readiness.ready} groups={len(readiness.selected_group_ids)} "
                f"sumE={readiness.sum_e_cyear} target={readiness.e_target} dE={readiness.delta_e}"
            )
            if readiness.reason:
                print("gate:", readiness.reason)
            if not readiness.selected_group_ids:
                print("SKIP: no groups")
                continue
            if readiness.ready:
                run = fuel_svc.run_for_distribution_parameter(dp.id)
                br = run.batch_result
            else:
                print("bypass 0.3 gate")
                effective_db_version = dist_svc._resolve_effective_db_version(dp, None)
                group_ids = participating_group_ids_for_year(
                    dist_svc.session,
                    readiness.selected_group_ids,
                    year_number=int(year),
                    effective_db_version=effective_db_version,
                )
                br = batch_svc.calculate_for_many_groups(
                    equipment_group_ids=group_ids,
                    year_number=int(year),
                    database_version_id=effective_db_version,
                    commit_each=True,
                    final_commit=True,
                    stop_on_error=False,
                    base_year_number=int(dp.base_year.number) if dp.base_year is not None else None,
                )
            n_ok = br.success_count if br else 0
            n_err = br.error_count if br else 0
            n_calc = sum(1 for item in br.items if item.success and item.calculated) if br else 0
            total_b = d0(0)
            errors = []
            if br:
                for item in br.items:
                    if item.success and item.calculated:
                        total_b += d0((item.calculated.get("energy") or {}).get("b"))
                    if not item.success:
                        errors.append((item.equipment_group_id, item.error))
            print(f"ok={n_ok} err={n_err} calculated={n_calc} ΣB={total_b}")
            for gid, err in errors[:10]:
                print(f"  ERR group_id={gid}: {err}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
