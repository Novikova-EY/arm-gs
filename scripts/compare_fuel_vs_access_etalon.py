# -*- coding: utf-8 -*-
"""
Сверка расчёта АРМ с эталоном Access (после scripts/fuel_access_etalon.py).

  python scripts/compare_fuel_vs_access_etalon.py
  python scripts/compare_fuel_vs_access_etalon.py --oes 1 --year 2026
  python scripts/compare_fuel_vs_access_etalon.py --db-version-id 37

Эталон: _otet_analysis/sipr_etalon/stations.tsv (+ extra.tsv, params.tsv).
АРМ: EquipmentGroupFuelParam текущей БД (версия --db-version-id).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app
from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
    DistributionCoefficientSummary,
)
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup

ETALON_DIR = ROOT / "_otet_analysis" / "sipr_etalon"
YEARS = (2026, 2027, 2028, 2029, 2030, 2031)

STATION_FIELDS = [
    ("E", "e"),
    ("EWTP", "ewtp"),
    ("H", "h"),
    ("HFIX", "hfix"),
    ("NUST", "nust"),
    ("NR", "nr"),
    ("Q", "q"),
    ("QOTR", "qotr"),
    ("EOTP", "eotp"),
    ("EURT", "eurt"),
    ("EUST", "eust"),
    ("TURT", "turt"),
    ("TUST", "tust"),
    ("B", "b"),
    ("GAZ", "gaz"),
    ("ISK_GAZ", "isk_gaz"),
    ("MAZUT", "mazut"),
    ("TORF", "torf"),
    ("SLAN", "slan"),
    ("PROCH", "proch"),
    ("UGOL", "ugol"),
    ("DON", "don"),
    ("PODM", "podm"),
    ("PECH", "pech"),
    ("ALT", "arkt"),
    ("KUZN", "kuzn"),
    ("URAL", "ural"),
    ("BASHK", "bashk"),
    ("KAZAH", "kazah"),
    ("KAN", "kan"),
    ("TUNG", "tung"),
    ("IRKUT", "irkut"),
    ("HAK", "hak"),
    ("TUV", "tuv"),
    ("BUR", "bur"),
    ("CHIT", "chit"),
    ("YAKUT", "yakut"),
    ("AMUR", "amur"),
    ("URG", "urg"),
    ("USHUM", "ushum"),
    ("PRIM", "prim"),
    ("MAG", "mag"),
    ("KAMCH", "kamch"),
    ("CHUKOT", "chukot"),
    ("SAH", "sah"),
]
CORE_DIST = ["E", "EWTP", "H", "HFIX", "NUST", "Q", "QOTR"]
CORE_FUEL = ["EOTP", "EURT", "EUST", "TURT", "TUST", "B"]
CORE_FUELS = ["GAZ", "MAZUT", "PROCH", "UGOL", "ISK_GAZ", "TORF", "SLAN"]
DOP_FIELDS = [
    "gaz_prir",
    "gazpp",
    "disel",
    "maztop",
    "gtt",
    "nft_proch",
    "domen_g",
    "koks_g",
    "prochgaz",
    "tvproch",
    "szh_gaz",
    "inoe",
]
ABS_TOL = 1e-4
REL_TOL = 1e-6
PARAM_ABS_TOL = 1e-3


def _f(v):
    if v is None or v == "":
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _eq(a, b, abs_tol=ABS_TOL, rel_tol=REL_TOL) -> bool:
    fa, fb = _f(a), _f(b)
    if fa is None and fb is None:
        return True
    if fa is None or fb is None:
        if (fa is None and abs(fb or 0) < abs_tol) or (fb is None and abs(fa or 0) < abs_tol):
            return True
        return False
    if abs(fa - fb) <= abs_tol:
        return True
    denom = max(abs(fa), abs(fb), 1e-12)
    return abs(fa - fb) / denom <= rel_tol


def _delta(a, b):
    fa, fb = _f(a), _f(b)
    if fa is None and fb is None:
        return 0.0
    if fa is None:
        return -(fb or 0.0)
    if fb is None:
        return fa
    return fa - fb


def _oes_from_filter(text: str | None) -> int | None:
    m = re.search(r"oes\s*=\s*(\d+)", text or "", flags=re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1))


def _read_tsv(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"нет выгрузки эталона: {path} (python scripts/fuel_access_etalon.py export)")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _key_ci(row: dict, *names: str) -> str | None:
    lower = {k.lower(): k for k in row}
    for n in names:
        k = lower.get(n.lower())
        if k is not None:
            return k
    return None


def load_access(oes: int | None, year: int | None):
    stations = _read_tsv(ETALON_DIR / "stations.tsv")
    extras = _read_tsv(ETALON_DIR / "extra.tsv") if (ETALON_DIR / "extra.tsv").is_file() else []
    params = _read_tsv(ETALON_DIR / "params.tsv")

    by_st: dict[tuple[int, int], dict] = {}
    for r in stations:
        yk = _key_ci(r, "YEAR", "year")
        nk = _key_ci(r, "NUMB1120")
        ok = _key_ci(r, "OES", "oes")
        y = int(float(r[yk])) if yk and r.get(yk) not in (None, "") else None
        n = int(float(r[nk])) if nk and r.get(nk) not in (None, "") else None
        o = int(float(r[ok])) if ok and r.get(ok) not in (None, "") else None
        if y is None or n is None:
            continue
        if year is not None and y != year:
            continue
        if oes is not None and o != oes:
            continue
        by_st[(n, y)] = r

    by_dop: dict[tuple[int, int], dict] = {}
    for r in extras:
        yk = _key_ci(r, "YEAR", "year")
        nk = _key_ci(r, "NUMB1120", "numb1")
        ok = _key_ci(r, "oes", "OES")
        y = int(float(r[yk])) if yk and r.get(yk) not in (None, "") else None
        n = int(float(r[nk])) if nk and r.get(nk) not in (None, "") else None
        o = int(float(r[ok])) if ok and r.get(ok) not in (None, "") else None
        if y is None or n is None:
            continue
        if year is not None and y != year:
            continue
        if oes is not None and o is not None and o != oes:
            continue
        by_dop[(n, y)] = r

    by_param: dict[tuple[int | None, int], dict] = {}
    for r in params:
        y = int(float(r["year"])) if r.get("year") not in (None, "") else None
        o = _oes_from_filter(r.get("filter") or "")
        if y is None:
            continue
        if year is not None and y != year:
            continue
        if oes is not None and o != oes:
            continue
        by_param[(o, y)] = r
    return by_st, by_dop, by_param


def load_arm(app, *, db_version_id: int, oes: int | None, years: tuple[int, ...]):
    with app.app_context():
        q = (
            db.session.query(EquipmentGroupFuelParam, EquipmentGroup)
            .join(
                EquipmentGroup,
                EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
            )
            .filter(
                EquipmentGroupFuelParam.year_number.in_(years),
                EquipmentGroup.database_version_id == db_version_id,
                EquipmentGroupFuelParam.ved.isnot(None),
                EquipmentGroupFuelParam.ved > 0,
            )
        )
        if oes is not None:
            q = q.filter(EquipmentGroupFuelParam.oes == str(oes))
        rows = q.order_by(EquipmentGroup.id).all()
        by_st: dict[tuple[int, int], dict] = {}
        for fp, eg in rows:
            numb = eg.numb if eg.numb is not None else fp.numb1120
            y = fp.year_number
            if numb is None or y is None:
                continue
            key = (int(numb), int(y))
            if key in by_st:
                continue
            by_st[key] = {"fp": fp, "eg": eg}

        extra: dict[tuple[int, int], EquipmentGroupExtraFuelParam] = {}
        eg_ids = [v["eg"].id for v in by_st.values()]
        if eg_ids:
            extras = EquipmentGroupExtraFuelParam.query.filter(
                EquipmentGroupExtraFuelParam.equipment_group_id.in_(eg_ids),
                EquipmentGroupExtraFuelParam.year_number.in_(years),
            ).all()
            by_eg_year = {(e.equipment_group_id, e.year_number): e for e in extras}
            for key, v in by_st.items():
                e = by_eg_year.get((v["eg"].id, key[1]))
                if e is not None:
                    extra[key] = e

        dps = DistributionParameter.query.filter(
            DistributionParameter.database_version_id == db_version_id,
        ).all()
        dp_by: dict[tuple[int | None, int], tuple] = {}
        for dp in dps:
            y = dp.year.number if dp.year else None
            o = _oes_from_filter(dp.filter_text)
            if y not in years:
                continue
            if oes is not None and o != oes:
                continue
            summ = DistributionCoefficientSummary.query.filter_by(
                distribution_parameter_id=dp.id,
                year_number=y,
                database_version_id=db_version_id,
            ).first()
            dp_by[(o, int(y))] = (dp, summ)
        return by_st, extra, dp_by


def _row_get(row: dict, field: str):
    k = _key_ci(row, field)
    return row.get(k) if k else None


def compare_one(
    *,
    oes: int | None,
    year: int,
    acc_st,
    acc_dop,
    acc_params,
    arm_st,
    arm_extra,
    dp_by,
) -> dict:
    acc_keys = set()
    for (n, y), r in acc_st.items():
        if y != year:
            continue
        if oes is not None and _f(_row_get(r, "OES")) != float(oes):
            continue
        acc_keys.add((n, y))
    arm_keys = {(n, y) for (n, y) in arm_st if y == year}
    if oes is not None:
        arm_keys = {
            (n, y)
            for (n, y), v in arm_st.items()
            if y == year and str(getattr(v["fp"], "oes", None)) == str(oes)
        }
    both = sorted(acc_keys & arm_keys)
    only_acc = sorted(n for n, y in acc_keys - arm_keys)
    only_arm = sorted(n for n, y in arm_keys - acc_keys)

    field_stats = {acc: {"match": 0, "mismatch": 0, "diffs": []} for acc, _ in STATION_FIELDS}
    row_mismatches = []
    for numb, y in both:
        a = acc_st[(numb, y)]
        arm = arm_st[(numb, y)]["fp"]
        name = (_row_get(a, "NAME") or arm.name or "").strip() or f"numb={numb}"
        mismatches = []
        for acc_f, arm_f in STATION_FIELDS:
            av = _row_get(a, acc_f)
            bv = getattr(arm, arm_f, None)
            if _eq(av, bv):
                field_stats[acc_f]["match"] += 1
            else:
                field_stats[acc_f]["mismatch"] += 1
                d = _delta(bv, av)
                item = {
                    "numb": numb,
                    "year": y,
                    "oes": oes,
                    "name": name,
                    "field": acc_f,
                    "access": _f(av),
                    "arm": _f(bv),
                    "delta": d,
                    "abs_delta": abs(d),
                }
                field_stats[acc_f]["diffs"].append(item)
                mismatches.append(item)
        dop_mism = []
        if (numb, y) in acc_dop and (numb, y) in arm_extra:
            ad = acc_dop[(numb, y)]
            ae = arm_extra[(numb, y)]
            for f in DOP_FIELDS:
                av = _row_get(ad, f)
                bv = getattr(ae, f, None)
                if not _eq(av, bv):
                    dop_mism.append(
                        {
                            "numb": numb,
                            "field": f,
                            "access": _f(av),
                            "arm": _f(bv),
                            "delta": _delta(bv, av),
                        }
                    )
        if mismatches or dop_mism:
            row_mismatches.append(
                {
                    "numb": numb,
                    "name": name,
                    "n_mismatches": len(mismatches),
                    "core_dist_mism": [m for m in mismatches if m["field"] in CORE_DIST],
                    "core_fuel_mism": [m for m in mismatches if m["field"] in CORE_FUEL],
                    "all": mismatches,
                    "dop_mism": dop_mism,
                }
            )

    def sum_field(field: str, is_access: bool) -> float:
        s = 0.0
        for numb, y in both:
            if is_access:
                v = _f(_row_get(acc_st[(numb, y)], field))
            else:
                arm_f = dict(STATION_FIELDS)[field]
                v = _f(getattr(arm_st[(numb, y)]["fp"], arm_f, None))
            if v is not None:
                s += v
        return s

    field_summary = []
    for acc_f, _ in STATION_FIELDS:
        st = field_stats[acc_f]
        compared = st["match"] + st["mismatch"]
        sa, sb = sum_field(acc_f, True), sum_field(acc_f, False)
        field_summary.append(
            {
                "field": acc_f,
                "match": st["match"],
                "mismatch": st["mismatch"],
                "compared": compared,
                "pct_ok": (100.0 * st["match"] / compared) if compared else 100.0,
                "max_abs_delta": max((d["abs_delta"] for d in st["diffs"]), default=0.0),
                "sum_access": sa,
                "sum_arm": sb,
                "sum_delta": sb - sa,
            }
        )

    acc_p = acc_params.get((oes, year), {})
    arm_pair = dp_by.get((oes, year))
    param_compare = []
    if arm_pair:
        dp, summ = arm_pair
        for af, arm_attr in [
            ("e", "e"),
            ("k", "k"),
            ("kn", "kn"),
            ("knps", "knps"),
            ("kngt", "kngt"),
            ("knpg", "knpg"),
        ]:
            av = None
            for k, v in acc_p.items():
                if k.lower() == af:
                    av = v
                    break
            bv = getattr(dp, arm_attr, None)
            param_compare.append(
                {
                    "field": af,
                    "access": _f(av),
                    "arm": _f(bv),
                    "delta": _delta(bv, av),
                    "ok": _eq(av, bv, abs_tol=PARAM_ABS_TOL, rel_tol=1e-5),
                    "dp_id": dp.id,
                }
            )
            _ = summ

    row_mismatches.sort(
        key=lambda r: (len(r["core_fuel_mism"]) + len(r["core_dist_mism"]), r["n_mismatches"]),
        reverse=True,
    )
    sum_e_acc = sum_field("E", True)
    sum_e_arm = sum_field("E", False)
    e_target_acc = _f(next((v for k, v in acc_p.items() if k.lower() == "e"), None))
    e_target_arm = _f(arm_pair[0].e) if arm_pair else None
    return {
        "oes": oes,
        "year": year,
        "coverage": {
            "access_rows": len(acc_keys),
            "arm_rows": len(arm_keys),
            "both": len(both),
            "only_access": only_acc,
            "only_arm": only_arm,
            "stations_with_any_mismatch": len(row_mismatches),
            "stations_perfect": len(both) - len(row_mismatches),
        },
        "energy_balance": {
            "sum_e_access": sum_e_acc,
            "sum_e_arm": sum_e_arm,
            "sum_e_delta": sum_e_arm - sum_e_acc,
            "e_target_access": e_target_acc,
            "e_target_arm": e_target_arm,
        },
        "field_summary": field_summary,
        "param_compare": param_compare,
        "top_stations": row_mismatches[:25],
        "mismatches": [m for st in row_mismatches for m in st["all"]],
        "perfect_core_dist": sum(
            1
            for numb, y in both
            if all(
                _eq(
                    _row_get(acc_st[(numb, y)], f),
                    getattr(arm_st[(numb, y)]["fp"], dict(STATION_FIELDS)[f], None),
                )
                for f in CORE_DIST
            )
        ),
        "perfect_core_fuel": sum(
            1
            for numb, y in both
            if all(
                _eq(
                    _row_get(acc_st[(numb, y)], f),
                    getattr(arm_st[(numb, y)]["fp"], dict(STATION_FIELDS)[f], None),
                )
                for f in CORE_FUEL
            )
        ),
    }


def _print_block(rep: dict) -> None:
    cov = rep["coverage"]
    eb = rep["energy_balance"]
    print(
        f"\n=== oes={rep['oes']} year={rep['year']} "
        f"Access={cov['access_rows']} ARM={cov['arm_rows']} both={cov['both']} "
        f"perfect={cov['stations_perfect']} mism={cov['stations_with_any_mismatch']} ==="
    )
    print(
        f"  CORE_DIST {rep['perfect_core_dist']}/{cov['both']}  "
        f"CORE_FUEL {rep['perfect_core_fuel']}/{cov['both']}"
    )
    print(
        f"  ΣE Access={eb['sum_e_access']:.4f} ARM={eb['sum_e_arm']:.4f} "
        f"d={eb['sum_e_delta']:.4f}  Eраспред Acc={eb['e_target_access']} ARM={eb['e_target_arm']}"
    )
    for fs in rep["field_summary"]:
        if fs["mismatch"] == 0:
            continue
        if fs["field"] not in CORE_DIST + CORE_FUEL + CORE_FUELS:
            continue
        print(
            f"  DIFF {fs['field']:8s} {fs['match']:3d}/{fs['compared']:3d} "
            f"({fs['pct_ok']:5.1f}%) max|d|={fs['max_abs_delta']:.6g} sumD={fs['sum_delta']:.6g}"
        )
    for st in rep["top_stations"][:8]:
        cf = ",".join(m["field"] for m in st["core_fuel_mism"] + st["core_dist_mism"])
        print(f"  numb={st['numb']:5d} n={st['n_mismatches']:2d} [{cf}] {st['name'][:50]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Сверка АРМ с эталоном Access")
    parser.add_argument("--oes", type=int, default=None)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--db-version-id", type=int, default=int(os.environ.get("COMPARE_DB_VERSION_ID", "37")))
    args = parser.parse_args()
    years = (args.year,) if args.year else YEARS

    acc_st, acc_dop, acc_params = load_access(args.oes, args.year)
    app = create_app()
    with app.app_context():
        ver = DatabaseVersion.query.get(args.db_version_id)
        ver_name = ver.version_number if ver is not None else f"id={args.db_version_id}"
    arm_st, arm_extra, dp_by = load_arm(
        app, db_version_id=args.db_version_id, oes=args.oes, years=years
    )

    oes_years: list[tuple[int | None, int]] = []
    if args.oes is not None and args.year is not None:
        oes_years = [(args.oes, args.year)]
    else:
        seen = set()
        for (_n, y), r in acc_st.items():
            o = int(_f(_row_get(r, "OES")) or 0) or None
            if args.oes is not None:
                o = args.oes
            if args.year is not None:
                y = args.year
            key = (o, y)
            if y in years and key not in seen:
                seen.add(key)
                oes_years.append(key)
        oes_years.sort(key=lambda x: (x[0] or 99, x[1]))

    reports_dir = ETALON_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    all_reports = []
    tsv_path = reports_dir / "mismatches.tsv"
    with tsv_path.open("w", encoding="utf-8", newline="") as tf:
        w = csv.writer(tf, delimiter="\t")
        w.writerow(["oes", "year", "numb", "name", "field", "access", "arm", "delta", "abs_delta"])
        for oes, year in oes_years:
            rep = compare_one(
                oes=oes,
                year=year,
                acc_st=acc_st,
                acc_dop=acc_dop,
                acc_params=acc_params,
                arm_st=arm_st,
                arm_extra=arm_extra,
                dp_by=dp_by,
            )
            all_reports.append(rep)
            _print_block(rep)
            stem = f"compare_oes{oes}_{year}"
            (reports_dir / f"{stem}_report.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            for m in rep["mismatches"]:
                w.writerow(
                    [
                        oes,
                        year,
                        m["numb"],
                        m.get("name"),
                        m["field"],
                        m["access"],
                        m["arm"],
                        m["delta"],
                        m["abs_delta"],
                    ]
                )

    summary = {
        "arm_db_version": ver_name,
        "arm_db_version_id": args.db_version_id,
        "etalon_dir": str(ETALON_DIR),
        "abs_tol": ABS_TOL,
        "scenarios": [
            {
                "oes": r["oes"],
                "year": r["year"],
                "both": r["coverage"]["both"],
                "perfect": r["coverage"]["stations_perfect"],
                "mismatched": r["coverage"]["stations_with_any_mismatch"],
                "perfect_core_dist": r["perfect_core_dist"],
                "perfect_core_fuel": r["perfect_core_fuel"],
                "sum_e_delta": r["energy_balance"]["sum_e_delta"],
            }
            for r in all_reports
        ],
    }
    (reports_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nсводка: {reports_dir / 'summary.json'}")
    print(f"расхождения: {tsv_path}")
    n_bad = sum(1 for r in all_reports if r["coverage"]["stations_with_any_mismatch"])
    print(f"сценариев с расхождениями: {n_bad}/{len(all_reports)}")
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
