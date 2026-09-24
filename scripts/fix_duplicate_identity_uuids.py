#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Разводит совпадающие identity-UUID. Записи НЕ удаляет.

План также доступен в API (без записи):
  GET /api/duplicate_identity_uuids
  GET /api/duplicate_identity_uuids/<database_version>

Запуск из корня репозитория:

  python scripts/fix_duplicate_identity_uuids.py
  python scripts/fix_duplicate_identity_uuids.py --dry-run
  python scripts/fix_duplicate_identity_uuids.py --yes
  python scripts/fix_duplicate_identity_uuids.py --refdata --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.common.services.duplicate_identity_uuid_services import (
    build_duplicate_identity_uuid_report,
)
from app.common.services.unique_uuid_services import IdentityUuidRewrite
from app.extensions import db
from config import SCHEMA_GENERATION


def _print_db_target() -> None:
    url = db.engine.url
    print("Целевая БД:")
    print(f"  host:     {url.host}")
    print(f"  port:     {url.port}")
    print(f"  database: {url.database}")
    print("  записи не удаляются, меняются только UUID")
    print()


def _print_section(title: str, count: int, rows: list[dict]) -> None:
    print(f"{title}: {count}")
    for item in rows[:8]:
        print(
            f"  id={item['id']} ver={item['database_version_id']} "
            f"{item['old_uuid']} -> {item['new_uuid']}"
        )
    if count > 8:
        print(f"  ... ещё {count - 8}")
    print()


def _rewrites_from_rows(rows: list[dict]) -> list[IdentityUuidRewrite]:
    return [
        IdentityUuidRewrite(
            row_id=item["id"],
            version_id=item["database_version_id"],
            old_uuid=item["old_uuid"],
            new_uuid=item["new_uuid"],
        )
        for item in rows
    ]


def _apply_rewrites(schema: str, table: str, column: str, rewrites: list[IdentityUuidRewrite]) -> None:
    if not rewrites:
        return
    has_updated_at = db.session.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = 'updated_at'
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).first()
    set_updated = ", updated_at = NOW()" if has_updated_at else ""
    sql = text(
        f"UPDATE {schema}.{table} SET {column} = :new_uuid{set_updated} WHERE id = :row_id"
    )
    for item in rewrites:
        db.session.execute(sql, {"new_uuid": item.new_uuid, "row_id": item.row_id})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Развести дублирующие UUID станций, агрегатов и справочников без удаления строк."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать план (по умолчанию, если нет --yes)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Записать новые UUID в БД",
    )
    parser.add_argument(
        "--refdata",
        action="store_true",
        help="Также развести ref_uuid справочников (только строки с database_version_id)",
    )
    args = parser.parse_args()
    apply_changes = bool(args.yes) and not args.dry_run

    app = create_app()
    with app.app_context():
        _print_db_target()
        report = build_duplicate_identity_uuid_report(include_refdata=args.refdata)

        print("=" * 80)
        print("Разведение дублирующих identity-UUID (без удаления)")
        print("=" * 80)
        print(f"Старт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if not apply_changes:
            print("[DRY-RUN] Изменения не применяются")
        print()
        _print_section(
            "Station.external_code",
            report["stations"]["count"],
            report["stations"]["rows"],
        )
        _print_section(
            "Machine.external_code",
            report["machines"]["count"],
            report["machines"]["rows"],
        )
        refdata = report["refdata"]
        print(
            "Справочники (ref_uuid), таблиц с дублями: "
            f"{refdata['table_count']}, строк: {refdata['count']}"
        )
        if not args.refdata:
            print("  (пропущено; добавьте --refdata, чтобы проверить версии справочников)")
        for table in refdata["tables"]:
            _print_section(
                f"  {table['schema']}.{table['table']}",
                table["count"],
                table["rows"],
            )

        total = (
            report["stations"]["count"]
            + report["machines"]["count"]
            + refdata["count"]
        )
        if total == 0:
            print("Дублирующих UUID в пределах версии не найдено.")
            return
        if not apply_changes:
            print("Dry-run завершён. Для записи: python scripts/fix_duplicate_identity_uuids.py --yes")
            print("JSON того же плана: GET /api/duplicate_identity_uuids")
            return

        try:
            _apply_rewrites(
                SCHEMA_GENERATION,
                "gs_gen_stations",
                "external_code",
                _rewrites_from_rows(report["stations"]["rows"]),
            )
            _apply_rewrites(
                SCHEMA_GENERATION,
                "gs_gen_machines",
                "external_code",
                _rewrites_from_rows(report["machines"]["rows"]),
            )
            if args.refdata:
                for table in refdata["tables"]:
                    _apply_rewrites(
                        table["schema"],
                        table["table"],
                        "ref_uuid",
                        _rewrites_from_rows(table["rows"]),
                    )
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        print(f"Обновлено Station: {report['stations']['count']}")
        print(f"Обновлено Machine: {report['machines']['count']}")
        print(f"Обновлено справочников: {refdata['count']}")
        print(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
