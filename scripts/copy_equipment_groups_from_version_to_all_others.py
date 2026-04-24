#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Копирование строк gs_sys.gs_sys_equipment_groups (EquipmentGroupType) с одного
database_version_id на все остальные id из gs_sys.gs_database_versions.

Для каждой пары (строка источника, целевая версия) вставляется НОВАЯ строка с тем же
ref_uuid, если в этой целевой версии ещё нет записи с таким ref_uuid
(идемпотентно, повторный запуск бесполезных дублей не создаёт).

ID типов технологий и доступности в целевой версии подбираются по ref_uuid справочников
(как в sync_equipment_group_types_from_version.py).

Запуск (из корня репозитория, с настроенным .env / БД):

  python scripts/copy_equipment_groups_from_version_to_all_others.py --dry-run
  python scripts/copy_equipment_groups_from_version_to_all_others.py --apply --yes

По умолчанию источник: database_version_id = 20. Иначе: --source-version 15

Внимание: «полное копирование как дамп» (один в один те же id_technology_type) без
подбора по версиям — отдельная задача; для межверсийной согласованности используйте
режим с разрешением FK по ref_uuid (ниже).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import (
    TechnologyAvailability,
)
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import (
    TechnologyType,
)
from app.common.services.tranzaction_services import _commit_with_retry

# Повторное использование логики сопоставления FK по ref_uuid
from scripts.sync_equipment_group_types_from_version import (  # noqa: E402
    _resolve_related_id_by_ref_uuid,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Copy EquipmentGroupType rows from one database_version_id to all other "
            "versions (insert only, skip if ref_uuid already exists in target version)."
        )
    )
    parser.add_argument(
        "--source-version",
        type=int,
        default=20,
        help="ID версии-источника (database_version_id), по умолчанию 20.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только план, без вставок в БД (по умолчанию, если нет --apply).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить вставки и commit.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Без подтверждения (для --apply).",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    if not apply_changes:
        args.dry_run = True

    app = create_app()
    with app.app_context():
        src = args.source_version
        base_version_row = db.session.get(DatabaseVersion, src)
        if base_version_row is None:
            raise SystemExit(
                f"В gs_sys.gs_database_versions нет id={src}. "
                f"Проверьте --source-version."
            )

        source_rows = (
            EquipmentGroupType.query.filter(EquipmentGroupType.database_version_id == src)
            .order_by(EquipmentGroupType.id.asc())
            .all()
        )
        if not source_rows:
            print(f"Нет строк в gs_sys.gs_sys_equipment_groups с database_version_id={src}.")
            return

        other_versions = (
            DatabaseVersion.query.filter(
                DatabaseVersion.id.isnot(None),
                DatabaseVersion.id != src,
            )
            .order_by(DatabaseVersion.id.asc())
            .all()
        )
        if not other_versions:
            print("Других версий в gs_sys.gs_database_versions нет. Нечего копировать.")
            return

        target_ids = [v.id for v in other_versions]
        print("=" * 72)
        print("Копирование gs_sys.gs_sys_equipment_groups")
        print("=" * 72)
        print(f"Старт:     {datetime.now().isoformat(timespec='seconds')}")
        print(f"Источник:  database_version_id = {src} (строк: {len(source_rows)})")
        print(f"Цели:     database_version_id in {target_ids}")
        print(
            "Режим:    "
            + ("APPLY" if apply_changes else "DRY-RUN (без commit)")
        )
        print()

        if apply_changes and not args.yes:
            q = input(
                f"Вставить отсутствующие копии из версии {src} в {len(target_ids)} "
                f"друг(их) верс(ий)? [y/N]: "
            )
            if str(q).strip().lower() not in ("y", "yes", "д", "да"):
                print("Отмена.")
                return

        created = 0
        skipped = 0
        tech_cache: dict[tuple[int, int], int | None] = {}
        avail_cache: dict[tuple[int, int], int | None] = {}

        try:
            for target_vid in target_ids:
                for base_row in source_rows:
                    ref = getattr(base_row, "ref_uuid", None) or ""
                    if not ref.strip():
                        print(
                            f"Пропуск id={base_row.id}: пустой ref_uuid "
                            f"(нужен для сопоставления между версиями)."
                        )
                        skipped += 1
                        continue

                    exists = (
                        EquipmentGroupType.query.filter(
                            EquipmentGroupType.ref_uuid == ref,
                            EquipmentGroupType.database_version_id == target_vid,
                        )
                        .first()
                    )
                    if exists is not None:
                        skipped += 1
                        continue

                    tt = _resolve_related_id_by_ref_uuid(
                        model=TechnologyType,
                        source_id=base_row.id_technology_type,
                        target_version_id=target_vid,
                        cache=tech_cache,
                    )
                    ta = _resolve_related_id_by_ref_uuid(
                        model=TechnologyAvailability,
                        source_id=base_row.id_technology_availability,
                        target_version_id=target_vid,
                        cache=avail_cache,
                    )

                    if apply_changes:
                        new_row = EquipmentGroupType(
                            database_version_id=target_vid,
                            ref_uuid=ref,
                            name=base_row.name,
                            display_order=base_row.display_order,
                            id_technology_type=tt,
                            id_technology_availability=ta,
                        )
                        if hasattr(EquipmentGroupType, "version") and new_row.version is None:
                            new_row.version = 1
                        db.session.add(new_row)
                        db.session.flush()
                    created += 1

            if apply_changes:
                _commit_with_retry()
            else:
                db.session.rollback()
        except Exception:
            db.session.rollback()
            raise

        print("-" * 72)
        print(
            f"Создано бы записей: {created}"
            if not apply_changes
            else f"Создано записей: {created}"
        )
        print(
            f"Пропущено (уже есть ref_uuid в целевой версии или пустой ref): {skipped}"
        )
        print(f"Конец:     {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
