#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Для каждой версии БД (gs_sys.gs_database_versions): по минимальному номеру года
в gs_sys.gs_sys_years для этой версии добавляет недостающие годы с 2015 включительно
до (min_year - 1) с признаком года «факт»: Year.id_year_feature = id строки
gs_sys_year_features с name='факт' и тем же database_version_id, куда вставляются годы.

Идемпотентно: уже существующие пары (number, database_version_id) не дублируются;
если год в этом диапазоне есть, но id_year_feature не «факт» — проставляется «факт».

Если в версии нет ни одного года или min_year <= 2015 — для версии ничего не делается.
Если для версии нет признака «факт» — версия пропускается с предупреждением.

Запуск из корня репозитория:

  python scripts/backfill_fact_years_from_2015_per_version.py --dry-run
  python scripts/backfill_fact_years_from_2015_per_version.py --apply --yes

Опции:
  --from-year N   нижняя граница (по умолчанию 2015)
  --version-id ID обработать только одну версию
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year

# Имя признака в gs_sys_year_features (как в year_management_services / UI)
FACT_FEATURE_NAME = "факт"


def fact_year_feature_id_for_version(version_id: int) -> int | None:
    """
    id строки YearFeature с name='факт' для указанной версии БД.
    Именно его нужно писать в Year.id_year_feature при вставке годов в эту версию.
    """
    row = (
        db.session.query(YearFeature.id)
        .filter(
            YearFeature.name == FACT_FEATURE_NAME,
            YearFeature.database_version_id == version_id,
        )
        .order_by(YearFeature.id.asc())
        .first()
    )
    return int(row[0]) if row else None


def _clear_year_caches() -> None:
    try:
        from app.common.services.get_services.years.year_feature_services import (
            get_year_feature_dict_for_version,
        )
        from app.common.services.get_services.years.years_get_services import (
            get_year_list_full,
            _get_filter_end_year_for_version,
            _get_filter_start_year_for_version,
            _get_sipr_end_year_for_version,
            _get_sipr_start_year_for_version,
        )

        get_year_feature_dict_for_version.cache_clear()
        get_year_list_full.cache_clear()
        _get_filter_start_year_for_version.cache_clear()
        _get_filter_end_year_for_version.cache_clear()
        _get_sipr_start_year_for_version.cache_clear()
        _get_sipr_end_year_for_version.cache_clear()
    except Exception:
        pass


def process_version(version_id: int, from_year: int, apply: bool) -> dict[str, int | str]:
    out: dict[str, int | str] = {
        "inserted": 0,
        "feature_updated": 0,
        "min_year": "",
        "note": "",
    }

    min_year = (
        db.session.query(func.min(Year.number))
        .filter(Year.database_version_id == version_id)
        .scalar()
    )

    if min_year is None:
        out["note"] = "нет годов для версии"
        return out

    out["min_year"] = str(min_year)

    if min_year <= from_year:
        out["note"] = f"min={min_year} <= {from_year}, диапазон пуст"
        return out

    fact_feature_id = fact_year_feature_id_for_version(version_id)
    if fact_feature_id is None:
        out["note"] = "нет YearFeature «факт» для версии"
        return out

    for num in range(from_year, min_year):
        row = Year.query.filter_by(
            number=num,
            database_version_id=version_id,
        ).first()
        if row is None:
            out["inserted"] = int(out["inserted"]) + 1
            if apply:
                # Year.id_year_feature -> тот же database_version_id, что и у Year
                db.session.add(
                    Year(
                        number=num,
                        id_year_feature=fact_feature_id,
                        database_version_id=version_id,
                    )
                )
        elif row.id_year_feature != fact_feature_id:
            out["feature_updated"] = int(out["feature_updated"]) + 1
            if apply:
                row.id_year_feature = fact_feature_id

    out["note"] = "ok"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Добавить годы [from_year, min_year) с признаком «факт» для каждой версии БД."
        )
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=2015,
        help="Нижняя граница включительно (по умолчанию 2015).",
    )
    parser.add_argument(
        "--version-id",
        type=int,
        default=None,
        help="Обработать только эту database_version_id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="План без изменений (режим по умолчанию, если нет --apply).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить вставки/обновления и commit.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="С --apply: не спрашивать подтверждение в консоли.",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    if not apply_changes:
        args.dry_run = True

    from_year = args.from_year
    if from_year < 1900 or from_year > 2100:
        raise SystemExit("--from-year вне разумного диапазона")

    app = create_app()
    with app.app_context():
        q = DatabaseVersion.query.order_by(DatabaseVersion.id.asc())
        if args.version_id is not None:
            q = q.filter(DatabaseVersion.id == args.version_id)
        versions = q.all()
        if args.version_id is not None and not versions:
            raise SystemExit(f"Нет версии БД с id={args.version_id}")

        if apply_changes and not args.yes:
            print(
                "Режим --apply без --yes: добавьте --yes для записи в БД "
                "(или используйте --dry-run)."
            )
            raise SystemExit(1)

        print(f"[{datetime.now().isoformat(timespec='seconds')}] Режим: {'APPLY' if apply_changes else 'DRY-RUN'}")
        print(f"Диапазон годов к заполнению: [{from_year}; min_year) по каждой версии\n")

        total_ins = 0
        total_upd = 0

        for v in versions:
            st = process_version(v.id, from_year, apply_changes)
            note = str(st["note"])
            min_y = st["min_year"]
            ins = int(st["inserted"])
            upd = int(st["feature_updated"])

            print(
                f"version_id={v.id} ({v.version_number!r}): "
                f"min_year={min_y or '-'} insert={ins} feature_fix={upd} — {note}"
            )

            total_ins += ins
            total_upd += upd

        print(f"\nИтого: вставок={total_ins}, обновлений признака={total_upd}")

        if apply_changes and (total_ins or total_upd):
            db.session.commit()
            _clear_year_caches()
            print("Commit выполнен, кэши справочников годов сброшены.")
        elif apply_changes:
            print("Нечего менять — commit не требуется.")


if __name__ == "__main__":
    main()
