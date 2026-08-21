#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Восстановление MachineName из других версий по external_code.

- заполняет пустые name у существующих строк;
- создаёт недостающие годы (по machine_tes_types / machine_powers / годам донора).

Запуск:
  python scripts/restore_machine_names_by_external_code.py --dry-run
  python scripts/restore_machine_names_by_external_code.py
  python scripts/restore_machine_names_by_external_code.py --version-id 46
  python scripts/restore_machine_names_by_external_code.py --machine-id 84615
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.generation.services.machine_services.machine_name_sync_services import (
    restore_empty_machine_names_by_external_code,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Восстановить названия агрегатов по годам из других версий (external_code)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать статистику, без commit",
    )
    parser.add_argument(
        "--version-id",
        type=int,
        default=None,
        help="Ограничить целевые агрегаты указанной database_version_id",
    )
    parser.add_argument(
        "--machine-id",
        type=int,
        action="append",
        default=None,
        help="Ограничить конкретным id агрегата (можно несколько раз)",
    )
    parser.add_argument(
        "--no-create",
        action="store_true",
        help="Не создавать недостающие строки (только заполнять пустые name)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print("Восстановление machine_names по external_code...")
        if args.version_id is not None:
            print(f"  version_id={args.version_id}")
        if args.machine_id:
            print(f"  machine_ids={args.machine_id}")
        if args.dry_run:
            print("  режим: dry-run (без commit)")

        stats = restore_empty_machine_names_by_external_code(
            machine_ids=args.machine_id,
            database_version_id=args.version_id,
            only_empty=True,
            create_missing=not args.no_create,
        )
        print(
            f"Агрегатов: {stats['machines']}, "
            f"обновлено: {stats['updated']}, "
            f"создано: {stats['created']}, "
            f"без external_code: {stats['skipped_no_code']}, "
            f"без донора: {stats['skipped_no_donor']}"
        )

        if args.dry_run:
            db.session.rollback()
            print("Откат (dry-run).")
        else:
            db.session.commit()
            print("Сохранено.")


if __name__ == "__main__":
    main()
