# -*- coding: utf-8 -*-
"""
Первый проход BDis с эталонными Access k/kobl, без записи в БД.

  $env:DB_HOST='10.31.205.27'
  python scripts/diag_first_bdis_access_seed.py

nit=1: ΣE при Access k (без подбора).
inner: полный первый внешний цикл (до 16), без пересчёта kobl на второй проход.
"""
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
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_restriction_model import FuelRestriction
from app.fuel.services.calculation.distribution import distribution_stage_services as dss
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
    d0,
    restriction_subject_targets_unmet,
)

ROOT = Path(__file__).resolve().parents[1]
ETALON = ROOT / "_otet_analysis" / "sipr_etalon"
DP_ID = 144
DB_VERSION_ID = 37
YEAR = 2026
OES = 1

ACCESS_K = Decimal("1.02963561999219")
ACCESS_KOBL = {
    1: Decimal("0.993580411525435"),
    4: Decimal("1.03968376327856"),
    10: Decimal("0.982844660908986"),
    101: Decimal("0.996555407579352"),
}
ACCESS_KN = Decimal("1.08469790940753")
ACCESS_KNPS = Decimal("1.08469790940753")
ACCESS_KNGT = Decimal("1.03304562800717")
ACCESS_KNPG = Decimal("1.16217633150806")
E_TARGET = Decimal("61030")
D03 = Decimal("0.3")


def _load_access_stations():
    path = ETALON / "stations.tsv"
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    by_numb = {}
    by_obl = {}
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) <= idx["YEAR"]:
            continue
        try:
            year = int(float(cols[idx["YEAR"]]))
            oes = int(float(cols[idx["OES"]]))
            numb = int(float(cols[idx["NUMB1120"]]))
        except (ValueError, IndexError):
            continue
        if year != YEAR or oes != OES:
            continue
        e = Decimal(cols[idx["E"]] or "0")
        obl = int(float(cols[idx["OBL"]])) if cols[idx["OBL"]] else None
        hfix = cols[idx["HFIX"]] if cols[idx["HFIX"]] else None
        by_numb[numb] = {"e": e, "obl": obl, "hfix": hfix, "name": cols[idx["NAME"]]}
        if obl is not None:
            by_obl[obl] = by_obl.get(obl, Decimal(0)) + e
    return by_numb, by_obl


def _seed_access(session, *, seed_kn: bool):
    dp = session.get(DistributionParameter, DP_ID)
    dp.k = ACCESS_K
    session.add(dp)
    for r in session.query(FuelRestriction).filter(
        FuelRestriction.database_version_id == DB_VERSION_ID,
        FuelRestriction.oes == OES,
        FuelRestriction.year == YEAR,
    ):
        if r.obl is not None and int(r.obl) in ACCESS_KOBL:
            r.kobl = ACCESS_KOBL[int(r.obl)]
            session.add(r)
    if seed_kn:
        q = session.query(DistributionCoefficientSummary).filter_by(
            distribution_parameter_id=DP_ID,
            year_number=YEAR,
            database_version_id=DB_VERSION_ID,
        )
        summary = q.order_by(DistributionCoefficientSummary.id.desc()).first()
        if summary is not None:
            summary.kn = ACCESS_KN
            summary.knps = ACCESS_KNPS
            summary.kngt = ACCESS_KNGT
            summary.knpg = ACCESS_KNPG
            session.add(summary)
    session.flush()


def _arm_rows(session):
    q = (
        session.query(EquipmentGroupFuelParam, EquipmentGroup)
        .join(EquipmentGroup, EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id)
        .filter(
            EquipmentGroup.database_version_id == DB_VERSION_ID,
            EquipmentGroupFuelParam.year_number == YEAR,
            EquipmentGroupFuelParam.oes == str(OES),
            EquipmentGroupFuelParam.ved > 0,
        )
    )
    out = []
    for fp, eg in q.all():
        numb = eg.numb if eg.numb is not None else fp.numb1120
        out.append((fp, eg, numb))
    return out


def _ecur_by_obl(rows):
    acc = {}
    for fp, eg, _numb in rows:
        obl = int(eg.obl) if eg.obl is not None else None
        if obl is None:
            continue
        acc[obl] = acc.get(obl, Decimal(0)) + d0(fp.e)
    return acc


def _print_ecur(label, ecur, access_obl):
    named = [
        (1, "Архангельск", Decimal("6313"), Decimal("6312.99739196228")),
        (4, "Коми", Decimal("10053"), Decimal("10052.9994921115")),
        (10, "Калининград", Decimal("5099"), Decimal("5099")),
        (101, "прочие", None, Decimal("39564.9741258639")),
    ]
    print(f"\n{label}")
    print(
        f"{'obl':>4} {'субъект':<14} {'ARM ecur':>16} {'Access ecur':>16} "
        f"{'δ Access':>12} {'emin':>8} {'δ emin':>10} {'tsv ΣE':>14}"
    )
    unmet = False
    for obl, name, emin, acc_e in named:
        arm = ecur.get(obl, Decimal(0))
        d_acc = arm - acc_e
        d_emin = (arm - emin) if emin is not None else None
        tsv = access_obl.get(obl, Decimal(0))
        emin_s = f"{emin:.0f}" if emin is not None else "—"
        d_emin_s = f"{d_emin:+.4f}" if d_emin is not None else "—"
        print(
            f"{obl:4d} {name:<14} {arm:16.6f} {acc_e:16.6f} {d_acc:+12.4f} "
            f"{emin_s:>8} {d_emin_s:>10} {tsv:14.4f}"
        )
        if emin is not None:
            if arm + D03 < emin or arm > emin + D03:
                unmet = True
    print(f"  restriction_subject_targets_unmet (допуск 0.3): {unmet}")
    return unmet


def _top_station_diffs(rows, access_by_numb, n=12):
    diffs = []
    for fp, eg, numb in rows:
        if numb is None or numb not in access_by_numb:
            continue
        acc = access_by_numb[numb]
        d_e = d0(fp.e) - acc["e"]
        diffs.append(
            (
                abs(d_e),
                d_e,
                numb,
                (eg.name or acc["name"] or "")[:28],
                d0(fp.e),
                acc["e"],
                int(fp.hfix or 0),
                acc["obl"],
            )
        )
    diffs.sort(reverse=True)
    print(f"\nТоп |δE| vs Access ({n}):")
    print(
        f"{'numb':>6} {'hfix':>4} {'obl':>4} {'δE':>12} {'ARM E':>12} {'Acc E':>12} name"
    )
    for _ad, d_e, numb, name, arm_e, acc_e, hfix, obl in diffs[:n]:
        print(
            f"{numb:6d} {hfix:4d} {obl or 0:4d} {d_e:+12.4f} {arm_e:12.4f} {acc_e:12.4f} {name}"
        )
    n_close = sum(1 for _ad, d_e, *_ in diffs if abs(d_e) < Decimal("0.05"))
    print(f"  станций |δE|<0.05: {n_close}/{len(diffs)}")


def _would_multiply_kobl(ecur):
    print("\nЧто сделал бы Ограничения_Click (kobl *= (emin-ecur+ecurdis)/ecurdis), ecurdis=ecur:")
    for obl, name, emin in (
        (1, "Архангельск", Decimal("6313")),
        (4, "Коми", Decimal("10053")),
        (10, "Калининград", Decimal("5099")),
    ):
        arm = ecur.get(obl, Decimal(0))
        factor = Decimal(1)
        if arm < emin and arm > 0:
            factor = emin / arm
        elif arm > emin and arm > 0:
            factor = emin / arm
        print(
            f"  obl={obl} {name}: ecur {arm:.6f} vs {emin}  "
            f"{'домножит kobl × ' + format(factor, '.8f') if factor != 1 else 'не трогает (ecur==emin строго? нет: формула если ecur<emin или >emax)'}"
        )
        if arm < emin:
            print(f"           ecur < emin → множитель {factor:.8f}")
        elif arm > emin:
            print(f"           ecur > emax → множитель {factor:.8f}")
        else:
            print("           ecur == emin → не трогает")


def run_probe(*, label: str, force_first_nit: bool, seed_kn: bool, access_by_numb, access_obl):
    import app.fuel.services.calculation.distribution.distribution_stage_services as mod

    orig_d03 = mod.D03
    orig_unmet = mod.restriction_subject_targets_unmet
    orig_recalc = DistributionStageService._recalculate_restriction_kobl
    if force_first_nit:
        mod.D03 = Decimal("1e18")
    mod.restriction_subject_targets_unmet = lambda *a, **k: False

    def _recalc_keep_kobl(self, **kwargs):
        rows = kwargs["restriction_rows"]
        saved = {id(r): r.kobl for r in rows}
        orig_recalc(self, **kwargs)
        for r in rows:
            r.kobl = saved[id(r)]

    DistributionStageService._recalculate_restriction_kobl = _recalc_keep_kobl
    try:
        _seed_access(db.session, seed_kn=seed_kn)
        svc = DistributionStageService(db.session)
        result = svc.run_for_distribution_parameter(
            distribution_parameter_id=DP_ID,
            database_version_id=DB_VERSION_ID,
            apply_restrictions=True,
            commit=False,
        )
        rows = _arm_rows(db.session)
        ecur = _ecur_by_obl(rows)
        sum_e = sum((d0(fp.e) for fp, _eg, _n in rows), Decimal(0))
        print("\n" + "=" * 78)
        print(label)
        print("=" * 78)
        print(
            f"inner nit={result.iterations}  outer={result.restriction_outer_iterations}  "
            f"k={result.final_k}  kn={result.final_kn}"
        )
        print(
            f"ΣE={sum_e:.6f}  Ераспред={E_TARGET}  Δ={sum_e - E_TARGET:+.6f}  "
            f"|Δ|<0.3: {abs(sum_e - E_TARGET) < D03}"
        )
        unmet = _print_ecur("ecur после этого прохода (kobl не пересчитывали)", ecur, access_obl)
        _would_multiply_kobl(ecur)
        _top_station_diffs(rows, access_by_numb)
        n_hfix = sum(1 for fp, _eg, _n in rows if int(fp.hfix or 0) == 1)
        print(f"  строк ved>0: {len(rows)}, hfix=1: {n_hfix}")
        return unmet, result
    finally:
        mod.D03 = orig_d03
        mod.restriction_subject_targets_unmet = orig_unmet
        DistributionStageService._recalculate_restriction_kobl = orig_recalc
        db.session.rollback()


def main():
    access_by_numb, access_obl = _load_access_stations()
    print(f"Access stations oes=1 2026: {len(access_by_numb)}")
    print(f"Access k={ACCESS_K}")
    print("Access kobl:", ACCESS_KOBL)

    app = create_app()
    with app.app_context():
        dp = db.session.get(DistributionParameter, DP_ID)
        print(f"\nВ БД сейчас (до отката диагностики): k={dp.k}")
        q = db.session.query(DistributionCoefficientSummary).filter_by(
            distribution_parameter_id=DP_ID,
            year_number=YEAR,
            database_version_id=DB_VERSION_ID,
        )
        summary = q.order_by(DistributionCoefficientSummary.id.desc()).first()
        if summary is not None:
            print(
                f"Сводка Коэфф: kn={summary.kn} knps={summary.knps} "
                f"kngt={summary.kngt} knpg={summary.knpg}"
            )
            print(
                f"Access kn={ACCESS_KN}  Δkn={d0(summary.kn) - ACCESS_KN}"
            )

        run_probe(
            label="1) nit=1: Access k×kobl, kn из сводки Коэфф АРМ, без подбора k",
            force_first_nit=True,
            seed_kn=False,
            access_by_numb=access_by_numb,
            access_obl=access_obl,
        )
        run_probe(
            label="2) первый внешний цикл целиком: Access k×kobl, kn АРМ, подбор k до |Δ|<0.3",
            force_first_nit=False,
            seed_kn=False,
            access_by_numb=access_by_numb,
            access_obl=access_obl,
        )
        run_probe(
            label="3) nit=1: Access k×kobl И Access kn/knps/kngt/knpg",
            force_first_nit=True,
            seed_kn=True,
            access_by_numb=access_by_numb,
            access_obl=access_obl,
        )
        dp2 = db.session.get(DistributionParameter, DP_ID)
        print(f"\nПосле rollback k в сессии={dp2.k} (БД не меняли)")


if __name__ == "__main__":
    main()
