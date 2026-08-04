# -*- coding: utf-8 -*-
"""
Перенос HFIX=1 из Access (выгрузка hfix_all.csv) в АРМ EquipmentGroupFuelParam.hfix.
Сопоставление: EquipmentGroup.numb == NUMB1120, year_number == Year.
Также обновляет h из Access, если значение есть (часы при фиксации).
"""
from __future__ import annotations

import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from sqlalchemy import cast
from sqlalchemy.types import String

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup

CSV_PATH = Path(r"c:\arm_gs\_otet_analysis\sipr_check\hfix_all.csv")


def _to_int(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(Decimal(s))
    except (InvalidOperation, ValueError):
        try:
            return int(float(s))
        except (TypeError, ValueError):
            return None


def _to_decimal(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def main(*, dry_run: bool = False) -> None:
    import os

    print(
        "DB target: host={host} name={name} dry_run={dry}".format(
            host=os.getenv("DB_HOST", "?"),
            name=os.getenv("DB_NAME", "?"),
            dry=dry_run,
        )
    )
    if not CSV_PATH.is_file():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, sep="\t", dtype=str)
    # Normalize column names
    cols = {c.lower(): c for c in df.columns}
    numb_col = cols.get("numb1120")
    year_col = cols.get("yearn") or cols.get("year")
    h_col = cols.get("h")
    if not numb_col or not year_col:
        raise SystemExit(f"Unexpected columns: {list(df.columns)}")

    pairs: dict[tuple[str, int], Decimal | None] = {}
    for _, row in df.iterrows():
        numb = _to_int(row.get(numb_col))
        year = _to_int(row.get(year_col))
        if numb is None or year is None:
            continue
        h_val = _to_decimal(row.get(h_col)) if h_col else None
        pairs[(str(numb), year)] = h_val

    print(f"Access HFIX=1 unique (numb,year): {len(pairs)}")

    app = create_app()
    with app.app_context():
        db.session.rollback()

        # Build group_id list per numb
        groups = EquipmentGroup.query.filter(EquipmentGroup.numb.isnot(None)).all()
        numb_to_gids: dict[str, list[int]] = {}
        for g in groups:
            key = str(int(g.numb)) if g.numb is not None else None
            if not key:
                continue
            numb_to_gids.setdefault(key, []).append(g.id)

        updated = 0
        created = 0
        matched_pairs = 0
        missing_group = 0
        missing_param = 0
        unchanged = 0
        samples_updated = []
        samples_missing = []

        for (numb_str, year), h_val in pairs.items():
            gids = numb_to_gids.get(numb_str) or []
            if not gids:
                missing_group += 1
                if len(samples_missing) < 15:
                    samples_missing.append((numb_str, year, "no_group"))
                continue

            matched_pairs += 1
            for gid in gids:
                param = (
                    EquipmentGroupFuelParam.query.filter_by(
                        equipment_group_id=gid,
                        year_number=year,
                    ).first()
                )
                if param is None:
                    missing_param += 1
                    if len(samples_missing) < 15:
                        samples_missing.append((numb_str, year, f"no_param gid={gid}"))
                    continue

                changed = False
                if param.hfix != 1:
                    param.hfix = 1
                    changed = True
                if h_val is not None and param.h != h_val:
                    # only set h when Access has a value
                    param.h = h_val
                    changed = True
                # ensure numb1120 filled
                if param.numb1120 is None:
                    param.numb1120 = int(numb_str)
                    changed = True

                if changed:
                    updated += 1
                    if len(samples_updated) < 10:
                        samples_updated.append(
                            (numb_str, year, gid, param.name, str(param.h), param.hfix)
                        )
                else:
                    unchanged += 1

        print(f"matched Access pairs with at least one group: {matched_pairs}")
        print(f"missing group for numb: {missing_group}")
        print(f"missing fuel_param row: {missing_param}")
        print(f"rows updated: {updated}")
        print(f"rows already ok: {unchanged}")
        print("samples updated:", samples_updated)
        print("samples missing:", samples_missing)

        if dry_run:
            db.session.rollback()
            print("DRY RUN — rollback")
        else:
            db.session.commit()
            # verify
            n = (
                EquipmentGroupFuelParam.query.filter(
                    EquipmentGroupFuelParam.hfix == 1
                ).count()
            )
            n2026 = (
                EquipmentGroupFuelParam.query.filter(
                    EquipmentGroupFuelParam.hfix == 1,
                    EquipmentGroupFuelParam.year_number == 2026,
                ).count()
            )
            print(f"COMMIT ok. ARM hfix=1 total={n}, year 2026={n2026}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
