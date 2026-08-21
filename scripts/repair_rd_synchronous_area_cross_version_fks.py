#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Починить RD.id_synchronous_area, указывающие на СЗ из другой версии БД.

В ТОПЛИВО часть субъектов РФ ссылалась на «Первую СЗ» версии «сходится УМ»,
из‑за этого Зеленчукская ГАЭС не входила в заряд 1‑й СЗ и «без заряда» был завышен.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reference-version-id",
        type=int,
        default=None,
        help="Версия-эталон для имени СЗ (по умолчанию — РАБОЧАЯ / id=37, если есть)",
    )
    parser.add_argument("--apply", action="store_true", help="Записать исправления в БД")
    args = parser.parse_args()

    from app import create_app
    from app.common.models.database_version_model import DatabaseVersion
    from app.energy_consumption.services.energy_consumption_summary_services import (
        clear_gaes_charge_summary_cache,
    )
    from app.extensions import db
    from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    app = create_app()
    with app.app_context():
        ref_vid = args.reference_version_id
        if ref_vid is None:
            rab = (
                DatabaseVersion.query.filter(
                    DatabaseVersion.version_number.ilike("%РАБОЧАЯ%")
                )
                .order_by(DatabaseVersion.id.desc())
                .first()
            )
            ref_vid = int(rab.id) if rab is not None else 37

        ref_by_name: dict[str, str] = {}
        for rd in RegionalDistrict.query.filter(
            RegionalDistrict.database_version_id == ref_vid
        ).all():
            if not rd.name or not rd.id_synchronous_area:
                continue
            sa = db.session.get(SynchronousArea, int(rd.id_synchronous_area))
            if sa is None or not sa.name:
                continue
            ref_by_name[str(rd.name).strip()] = str(sa.name).strip()

        print(f"reference_version_id={ref_vid}, rd_sa_names={len(ref_by_name)}")

        broken = (
            db.session.query(RegionalDistrict, SynchronousArea)
            .join(
                SynchronousArea,
                RegionalDistrict.id_synchronous_area == SynchronousArea.id,
            )
            .filter(
                SynchronousArea.database_version_id
                != RegionalDistrict.database_version_id
            )
            .order_by(
                RegionalDistrict.database_version_id.asc(),
                RegionalDistrict.name.asc(),
            )
            .all()
        )
        if not broken:
            print("Нет битых RD→SA ссылок.")
            return 0

        sa_name_by_vid: dict[int, dict[str, int]] = {}
        updates: list[tuple[RegionalDistrict, int, str, int, str]] = []
        unresolved: list[str] = []

        for rd, bad_sa in broken:
            vid = int(rd.database_version_id)
            if vid not in sa_name_by_vid:
                sa_name_by_vid[vid] = {
                    str(sa.name).strip(): int(sa.id)
                    for sa in SynchronousArea.query.filter(
                        SynchronousArea.database_version_id == vid
                    ).all()
                    if sa.name
                }
            wanted_sa_name = ref_by_name.get(str(rd.name or "").strip())
            if not wanted_sa_name:
                # запасной путь: то же имя СЗ, что у битой ссылки, но в версии RD
                wanted_sa_name = str(bad_sa.name or "").strip()
            target_sa_id = sa_name_by_vid[vid].get(wanted_sa_name)
            if target_sa_id is None:
                unresolved.append(
                    f"vid={vid} rd={rd.id} {rd.name!r}: нет СЗ {wanted_sa_name!r}"
                )
                continue
            if int(rd.id_synchronous_area) == int(target_sa_id):
                continue
            updates.append(
                (
                    rd,
                    int(rd.id_synchronous_area),
                    str(bad_sa.name),
                    int(target_sa_id),
                    wanted_sa_name,
                )
            )

        print(f"broken={len(broken)} to_update={len(updates)} unresolved={len(unresolved)}")
        for msg in unresolved[:30]:
            print("  UNRESOLVED", msg)
        for rd, old_id, old_name, new_id, new_name in updates[:40]:
            print(
                f"  vid={rd.database_version_id} rd={rd.id} {rd.name!r}: "
                f"{old_id}/{old_name!r} -> {new_id}/{new_name!r}"
            )
        if len(updates) > 40:
            print(f"  ... and {len(updates) - 40} more")

        if not args.apply:
            print("Dry-run. Передайте --apply для записи.")
            return 0

        for rd, _old_id, _old_name, new_id, _new_name in updates:
            rd.id_synchronous_area = new_id
        db.session.commit()
        clear_gaes_charge_summary_cache()
        print(f"Updated {len(updates)} regional districts.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
