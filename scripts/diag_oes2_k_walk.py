# -*- coding: utf-8 -*-
"""Почему АРМ уходит с эталонного k ОЭС Центра 2030/2031 (без записи)."""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from app import create_app
from app.extensions import db
from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
    DistributionCoefficientSummary,
)
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.services.calculation.coefficient.fuel_coefficient_calculation_services import (
    FuelCoefficientCalculationService,
)
from app.fuel.services.calculation.distribution import distribution_stage_services as dss
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
    d0,
)

VID = 37
ACCESS_K = {
    2026: Decimal("0.948277831906249"),
    2027: Decimal("0.952508545015623"),
    2028: Decimal("0.961279296875"),
    2029: Decimal("0.939041137695313"),
    2030: Decimal("0.880781494234374"),
    2031: Decimal("0.843097534460938"),
}
# 2026–2029 — k после вашего прогона; 2030–2031 — коллеги.


def _bounds(ph, doptim):
    return DistributionStageService._distribution_bounds_from_ph(d0(ph), d0(doptim))


def _dump_summary(label, s, dp):
    if s is None:
        print(f"  {label}: нет сводки")
        return
    ph = d0(s.ph)
    dopt = d0(dp.doptim)
    kmin, kplus = _bounds(ph, dopt)
    print(
        f"  {label}: bnust={d0(s.bnust):.4f} be={d0(s.be):.4f} bh={d0(s.bh):.4f} "
        f"cnust={d0(s.cnust):.4f} cnustn={d0(s.cnustn):.4f} hd={d0(s.hd):.4f} "
        f"ph={ph:.6f} kn={d0(s.kn):.8f} ch={d0(s.ch):.4f}"
    )
    print(f"         doptim={dopt} kmin={kmin:.6f} kplus={kplus:.6f} dp.k={d0(dp.k):.12f}")


def first_nit_at_k(dp_id: int, k: Decimal) -> tuple:
    orig = dss.D03
    dss.D03 = Decimal("1e18")
    try:
        dp = db.session.get(DistributionParameter, dp_id)
        saved_k = dp.k
        dp.k = k
        db.session.add(dp)
        db.session.flush()
        svc = DistributionStageService(db.session)
        run = svc.run_for_distribution_parameter(
            distribution_parameter_id=dp_id,
            database_version_id=VID,
            apply_restrictions=False,
            commit=False,
        )
        dp.k = saved_k
        db.session.add(dp)
        return run.total_distributed_e, run.iterations, d0(dp.e)
    finally:
        dss.D03 = orig
        db.session.rollback()


def main():
    app = create_app()
    with app.app_context():
        from sqlalchemy.orm import joinedload

        dps = (
            db.session.query(DistributionParameter)
            .options(joinedload(DistributionParameter.year))
            .filter(DistributionParameter.database_version_id == VID)
            .all()
        )
        by_year = {}
        for dp in dps:
            ft = (dp.filter_text or "").replace(" ", "")
            if "oes=2" not in ft:
                continue
            y = dp.year.number if dp.year else None
            if y in ACCESS_K:
                by_year[y] = dp

        coeff = FuelCoefficientCalculationService()
        print("=== сводка Коэфф: записанная vs живой пересчёт ===")
        for y in sorted(by_year):
            dp = by_year[y]
            stored = (
                db.session.query(DistributionCoefficientSummary)
                .filter_by(
                    distribution_parameter_id=dp.id,
                    year_number=y,
                    database_version_id=VID,
                )
                .order_by(DistributionCoefficientSummary.id.desc())
                .first()
            )
            live = coeff.compute_calc_year_preview_for_distribution_parameter(dp.id)
            base = coeff.compute_base_year_preview_for_distribution_parameter(dp.id)
            print(f"\n{y} dp_id={dp.id} Acc_k={ACCESS_K[y]} ARM_k={d0(dp.k)}")
            _dump_summary("stored", stored, dp)
            if base:
                print(
                    f"  base24:  bnust={d0(base.get('bnust')):.4f} be={d0(base.get('be')):.4f} "
                    f"bh={d0(base.get('bh')):.4f}"
                )
            if live:
                ph = d0(live.get("ph"))
                dopt = d0(dp.doptim)
                kmin, kplus = _bounds(ph, dopt)
                print(
                    f"  live:    cnust={d0(live.get('cnust')):.4f} cnustn={d0(live.get('cnustn')):.4f} "
                    f"hd={d0(live.get('hd')):.4f} ph={ph:.6f} kn={d0(live.get('kn')):.8f} "
                    f"ch={d0(live.get('ch')):.4f}"
                )
                print(f"         kmin={kmin:.6f} kplus={kplus:.6f}")
            if stored and live:
                d_ph = d0(live.get("ph")) - d0(stored.ph)
                d_hd = d0(live.get("hd")) - d0(stored.hd)
                d_kn = d0(live.get("kn")) - d0(stored.kn)
                print(f"  live-stored: d_ph={d_ph:.6f} d_hd={d_hd:.4f} d_kn={d_kn:.8f}")

        print("\n=== nit=1 при эталонном k коллег (без записи, lim закрыт) ===")
        for y in (2026, 2029, 2030, 2031):
            dp = by_year[y]
            se, nit, etgt = first_nit_at_k(dp.id, ACCESS_K[y])
            print(
                f"  {y} k={ACCESS_K[y]} nit={nit} ΣE={se:.4f} цель={etgt:.1f} "
                f"δ={se - etgt:+.4f}"
            )


if __name__ == "__main__":
    main()
