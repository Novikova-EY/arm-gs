 # -*- coding: utf-8 -*-
"""Заполнить/пересчитать сохраненные годовые агрегаты по ОЭС из данных по РЭС.

По умолчанию скрипт обрабатывает все зарегистрированные версии БД, а также
записи без версии (NULL), если они есть в исходных данных или агрегатах. Сначала
скрипт только показывает пары версия/год; для записи используйте --apply. Можно
ограничить обработку одной версией через --version-id; значение 0 означает
записи без версии БД (NULL).

Примеры:
  python scripts/backfill_ee_import_export_oes_values.py
  python scripts/backfill_ee_import_export_oes_values.py --apply
  python scripts/backfill_ee_import_export_oes_values.py --apply --version-id 3
  python scripts/backfill_ee_import_export_oes_values.py --apply --version-id 0
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import g
from sqlalchemy import distinct

from app import create_app
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.energy_balance.models.ee_import_export_oes_value_model import EeImportExportOesValue
from app.energy_balance.models.ee_receive_transfer_oes_value_model import EeReceiveTransferOesValue
from app.energy_balance.models.regional_energy_system_transfer_model import RegionalEnergySystemTransfer
from app.energy_balance.services.ee_import_export_oes_value_services import (
    recalculate_ee_import_export_oes_values,
)
from app.energy_balance.services.ee_receive_transfer_oes_value_services import (
    recalculate_ee_receive_transfer_oes_values,
)
from app.extensions import db


def _jobs_for_version(version_id: int | None) -> set[int]:
    """Все годы с исходными строками или агрегатами, включая очистку устаревших."""
    jobs: set[int] = set()
    for model in (
        RegionalEnergySystemTransfer,
        EeImportExportOesValue,
        EeReceiveTransferOesValue,
    ):
        query = filter_by_explicit_db_version(model.query, model, version_id)
        jobs.update(
            int(year)
            for (year,) in query.with_entities(distinct(model.year_number)).all()
            if year is not None
        )
    return jobs


def _versions_to_process(selected_version: int | None) -> list[int | None]:
    if selected_version is not None:
        # CLI-параметр 0 служит однозначным обозначением database_version_id IS NULL.
        return [None if selected_version == 0 else selected_version]

    versions = {
        int(version_id)
        for (version_id,) in DatabaseVersion.query.with_entities(DatabaseVersion.id).all()
    }
    for model in (
        RegionalEnergySystemTransfer,
        EeImportExportOesValue,
        EeReceiveTransferOesValue,
    ):
        if any(
            version_id is None
            for (version_id,) in model.query.with_entities(
                distinct(model.database_version_id)
            ).all()
        ):
            versions.add(None)
    return sorted(versions, key=lambda version: (-1 if version is None else version))


def main() -> int:
    parser = argparse.ArgumentParser(description="Бэкфилл годовых агрегатов ЭЭ по ОЭС из строк РЭС")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Записать пересчитанные агрегаты (по умолчанию выполняется dry-run)",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать годы и версии для обработки (режим по умолчанию)",
    )
    parser.add_argument(
        "--version-id",
        type=int,
        help="Обработать только версию БД; 0 означает database_version_id IS NULL",
    )
    args = parser.parse_args()

    if args.version_id is not None and args.version_id < 0:
        parser.error("--version-id должен быть неотрицательным; 0 обозначает NULL")

    app = create_app()
    with app.app_context():
        versions = _versions_to_process(args.version_id)
        jobs = [
            (version_id, year)
            for version_id in versions
            for year in sorted(_jobs_for_version(version_id))
        ]
        print(f"host={os.getenv('DB_HOST', '?')} db={os.getenv('DB_NAME', '?')}")
        print(f"Режим: {'ЗАПИСЬ' if args.apply else 'dry-run'}")
        print(f"Версий: {len(versions)}; пар версия/год: {len(jobs)}")
        for version_id, year in jobs:
            print(f"  version_id={'NULL' if version_id is None else version_id}, year={year}")

        if not args.apply:
            print("Изменений не внесено. Для пересчета запустите скрипт с --apply.")
            return 0

        processed = 0
        previous_version = getattr(g, "current_db_version", None)
        had_previous_version = hasattr(g, "current_db_version")
        try:
            for version_id in versions:
                # Пересчёт использует текущие справочники территорий, поэтому
                # контекст должен совпадать с версией исходных строк.
                g.current_db_version = version_id
                for job_version_id, year in jobs:
                    if job_version_id != version_id:
                        continue
                    recalculate_ee_import_export_oes_values(
                        year_number=year,
                        version_id=version_id,
                    )
                    recalculate_ee_receive_transfer_oes_values(
                        year_number=year,
                        version_id=version_id,
                    )
                    db.session.commit()
                    processed += 1
                    print(
                        f"Обработано: version_id={'NULL' if version_id is None else version_id}, "
                        f"year={year}"
                    )
        except Exception:
            db.session.rollback()
            raise
        finally:
            if had_previous_version:
                g.current_db_version = previous_version
            elif hasattr(g, "current_db_version"):
                del g.current_db_version

        print(f"Готово: пересчитано пар версия/год: {processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
