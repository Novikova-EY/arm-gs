# -*- coding: utf-8 -*-
"""Разбор H = hb·koptim·k·ke·kobl vs Access на первом шаге (без записи)."""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from app import create_app
from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_restriction_model import FuelRestriction
from app.fuel.services.calculation.access_bdis_cursor import (
    AccessBdisCursorState,
    fuel_param_access_n1,
    sort_access_filter_rows,
    walk_access_bdis_cursor,
)
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
    d0,
    _is_hfix,
)
from app.fuel.services.calculation.equipment_group_selection import (
    access_ved_filter_year_row_participates,
)

DP_ID = 144
DB_VERSION_ID = 37
YEAR = 2026
BYEAR = 2024
OES = 1
ACCESS_K = Decimal("1.02963561999219")
ACCESS_KOBL = {
    1: Decimal("0.993580411525435"),
    4: Decimal("1.03968376327856"),
    10: Decimal("0.982844660908986"),
    101: Decimal("0.996555407579352"),
}
FOCUS = {1, 26, 91, 58, 833, 834, 1477, 3, 31, 66, 75, 1044, 1403, 1404}
ETALON = Path(__file__).resolve().parents[1] / "_otet_analysis" / "sipr_etalon"


def _access_stations():
    lines = (ETALON / "stations.tsv").read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    idx = {n: i for i, n in enumerate(header)}
    by = {}
    for line in lines[1:]:
        cols = line.split("\t")
        try:
            y = int(float(cols[idx["YEAR"]]))
            o = int(float(cols[idx["OES"]]))
            n = int(float(cols[idx["NUMB1120"]]))
        except Exception:
            continue
        if o != OES:
            continue
        by.setdefault(n, {})[y] = {
            "h": Decimal(cols[idx["H"]] or "0"),
            "e": Decimal(cols[idx["E"]] or "0"),
            "nust": Decimal(cols[idx["NUST"]] or "0"),
            "hfix": cols[idx["HFIX"]],
            "name": cols[idx["NAME"]],
        }
    return by


def main():
    access = _access_stations()
    app = create_app()
    with app.app_context():
        svc = DistributionStageService(db.session)
        dp = db.session.get(DistributionParameter, DP_ID)
        summary = svc._load_coeff_summary(
            distribution_parameter_id=DP_ID,
            cyear=YEAR,
            effective_db_version=DB_VERSION_ID,
        )
        ph = d0(summary.ph)
        hd = d0(summary.hd)
        ch = d0(summary.ch)
        doptim = d0(dp.doptim)
        kmin, kplus = svc._distribution_bounds_from_ph(ph, doptim)
        print(f"ph={ph} hd={hd} ch={ch} doptim={doptim}")
        print(f"kmin={kmin} kplus={kplus}  Nivh active={ph > Decimal('1.15')}")
        print(f"Access k={ACCESS_K}")

        group_ids = svc._select_equipment_group_ids(row=dp, effective_db_version=DB_VERSION_ID)
        by_key = svc._fuel_param_by_group_year(
            group_ids=group_ids, byear=BYEAR, cyear=YEAR, effective_db_version=DB_VERSION_ID
        )
        cursor_by_key = svc._fuel_param_by_group_year(
            group_ids=group_ids,
            byear=BYEAR,
            cyear=YEAR,
            effective_db_version=DB_VERSION_ID,
            all_years=True,
        )
        groups_by_id = {
            g.id: g
            for g in db.session.query(EquipmentGroup).filter(EquipmentGroup.id.in_(group_ids)).all()
        }
        cursor_rows = sort_access_filter_rows(
            [fp for fp in cursor_by_key.values() if access_ved_filter_year_row_participates(fp)],
            n1_of=lambda fp: fuel_param_access_n1(fp, groups_by_id),
        )
        print(f"cursor rows (ved>0, byear+cyear): {len(cursor_rows)}")

        n_leak = 0
        n_formula = 0
        n_own_better = 0
        focus_lines = []
        sum_pred = Decimal(0)
        sum_own = Decimal(0)
        sum_acc = Decimal(0)
        sum_hfix = Decimal(0)

        state = AccessBdisCursorState()
        for kind, cur_row, cursor in walk_access_bdis_cursor(
            cursor_rows, byear=BYEAR, cyear=YEAR, state=state
        ):
            if kind != "cyear":
                continue
            gid = cur_row.equipment_group_id
            g = groups_by_id.get(gid)
            numb = g.numb if g is not None and g.numb is not None else cur_row.numb1120
            spec = svc._bdis_specific_row(
                equipment_group_id=gid,
                byear=BYEAR,
                cyear=YEAR,
                effective_db_version=DB_VERSION_ID,
            )
            if spec is None:
                continue
            hfix = _is_hfix(cur_row)
            own_base = by_key.get((gid, BYEAR))
            own_hb = svc._hours_from_fuel_row(own_base)
            hb = cursor.hb
            nustb = cursor.nustb
            obl = int(g.obl) if g is not None and g.obl is not None else None
            kobl = ACCESS_KOBL.get(obl, ACCESS_KOBL[101]) if obl is not None else ACCESS_KOBL[101]
            acc = access.get(int(numb), {}).get(YEAR) if numb is not None else None

            if hfix:
                h_cur = svc._hours_from_fuel_row(cur_row)
                e_pred = svc._calc_row_energy(
                    cur_row=cur_row, hb=hb, h_current=h_cur, ch=ch, nustb=nustb, hfix=True
                )
                sum_pred += e_pred
                sum_own += e_pred
                if acc:
                    sum_acc += acc["e"]
                    sum_hfix += acc["e"]
                continue

            n_formula += 1
            if own_hb != hb:
                n_leak += 1
            koptim = svc._koptim_from_bk(bk=spec.bk, kmin=kmin, kplus=kplus)
            ke = svc._nivh_factor(hb=hb, ph=ph)
            if hb == 0:
                h_cur = svc._new_capacity_hours(
                    obor=cur_row.obor, ch=ch, knps=d0(summary.knps),
                    kngt=d0(summary.kngt), knpg=d0(summary.knpg),
                )
                branch = "new"
            else:
                h_cur = hb * koptim * ACCESS_K * ke * kobl
                h_cur = svc._clamp_hours(hours=h_cur, hb=hb, hd=hd)
                branch = "formula"
            e_pred = svc._calc_row_energy(
                cur_row=cur_row, hb=hb, h_current=h_cur, ch=ch, nustb=nustb, hfix=False
            )
            ke_own = svc._nivh_factor(hb=own_hb, ph=ph)
            if own_hb == 0:
                h_own = h_cur
            else:
                h_own = own_hb * koptim * ACCESS_K * ke_own * kobl
                h_own = svc._clamp_hours(hours=h_own, hb=own_hb, hd=hd)
            e_own = svc._calc_row_energy(
                cur_row=cur_row, hb=own_hb, h_current=h_own, ch=ch, nustb=d0(own_base.nust) if own_base else nustb, hfix=False
            )
            sum_pred += e_pred
            sum_own += e_own
            if acc:
                sum_acc += acc["e"]
                d_cur = e_pred - acc["e"]
                d_own = e_own - acc["e"]
                if abs(d_own) + Decimal("0.01") < abs(d_cur):
                    n_own_better += 1

            if numb in FOCUS:
                acc_h = acc["h"] if acc else None
                acc_e = acc["e"] if acc else None
                implied = None
                if acc_h and hb > 0:
                    implied = acc_h / (hb * ACCESS_K * kobl)
                focus_lines.append(
                    dict(
                        numb=numb,
                        name=(g.name or "")[:36],
                        obl=obl,
                        branch=branch,
                        hb=hb,
                        own_hb=own_hb,
                        leak=hb != own_hb,
                        bk=spec.bk,
                        spec_year=spec.year_number,
                        koptim=koptim,
                        ke=ke,
                        kobl=kobl,
                        h_pred=h_cur,
                        h_own=h_own,
                        acc_h=acc_h,
                        e_pred=e_pred,
                        e_own=e_own,
                        acc_e=acc_e,
                        implied_kopt_ke=implied,
                        arm_kopt_ke=koptim * ke,
                    )
                )

        print(f"\nformula stations={n_formula}  cursor hb≠own 2024 H: {n_leak}")
        print(f"own-station hb closer to Access E than cursor: {n_own_better}")
        print(f"ΣE cursor-hb={sum_pred:.4f}  own-hb={sum_own:.4f}  Access={sum_acc:.4f}")
        print(f"  Δ cursor={sum_pred-sum_acc:+.4f}  Δ own={sum_own-sum_acc:+.4f}")
        print(f"  Access hfix subset E≈{sum_hfix:.4f}")

        print(
            f"\n{'numb':>6} {'obl':>3} {'leak':>4} {'bk':>7} {'kopt':>7} {'ke':>5} "
            f"{'hb':>8} {'ownH24':>8} {'Hpred':>8} {'Hacc':>8} {'Epred':>10} {'Eacc':>10} "
            f"{'kopt·ke':>8} {'Hacc/(hb·k·kobl)':>16}"
        )
        for r in focus_lines:
            leak = "Y" if r["leak"] else "."
            acc_h = f"{r['acc_h']:.1f}" if r["acc_h"] is not None else "—"
            acc_e = f"{r['acc_e']:.3f}" if r["acc_e"] is not None else "—"
            impl = f"{r['implied_kopt_ke']:.5f}" if r["implied_kopt_ke"] is not None else "—"
            print(
                f"{r['numb']:6d} {r['obl'] or 0:3d} {leak:>4} {d0(r['bk']):7.1f} {r['koptim']:7.4f} {r['ke']:5.3f} "
                f"{r['hb']:8.1f} {r['own_hb']:8.1f} {r['h_pred']:8.1f} {acc_h:>8} "
                f"{r['e_pred']:10.3f} {acc_e:>10} {r['arm_kopt_ke']:8.5f} {impl:>16}  {r['name']}"
            )
            print(
                f"       spec.year={r['spec_year']} kobl={r['kobl']} "
                f"δE_cursor={r['e_pred']-(r['acc_e'] or 0):+.3f} "
                f"δE_own={r['e_own']-(r['acc_e'] or 0):+.3f}"
            )


if __name__ == "__main__":
    main()
