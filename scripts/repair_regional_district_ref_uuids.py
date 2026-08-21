#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Исправляет ref_uuid субъектов РФ:

- в одной версии БД uuid не повторяется;
- у одного названия во всех версиях один и тот же uuid.

Запуск из корня репозитория:

  python scripts/repair_regional_district_ref_uuids.py
  python scripts/repair_regional_district_ref_uuids.py --target local --apply
  python scripts/repair_regional_district_ref_uuids.py --target gs01 --apply
  python scripts/repair_regional_district_ref_uuids.py --target local,gs01 --apply

Цели:
  local — DB_HOST из .env (локальная машина)
  gs01  — GS01_DB_HOST (по умолчанию 10.31.205.27), те же DB_USER/DB_NAME
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.refdata.services.repair_ref_uuid_services import (  # noqa: E402
    mapping_uuid_rewrites,
    norm_uuid,
    plan_ref_uuid_repairs,
)


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _parse_targets(raw: str) -> list[str]:
    allowed = {"local", "gs01"}
    targets = []
    seen = set()
    for item in (raw or "local").split(","):
        name = item.strip().lower()
        if not name or name in seen:
            continue
        if name not in allowed:
            raise SystemExit(f"Неизвестная цель {item!r}. Допустимо: local, gs01")
        seen.add(name)
        targets.append(name)
    return targets or ["local"]


def _engine_for_target(target: str) -> Engine:
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD") or os.environ.get("DB_PASS") or ""
    database = os.environ.get("DB_NAME", "gs_gen")
    driver = os.environ.get("DB_DRIVER", "psycopg2")
    if target == "local":
        host = os.environ.get("DB_HOST", "localhost")
        port = int(os.environ.get("DB_PORT", "5432"))
    else:
        host = os.environ.get("GS01_DB_HOST", "10.31.205.27")
        port = int(os.environ.get("GS01_DB_PORT", os.environ.get("DB_PORT", "5432")))
    if not user:
        raise SystemExit("Задайте DB_USER в .env")
    url = URL.create(
        f"postgresql+{driver}",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    return create_engine(url)


def _print_target(target: str, engine: Engine) -> None:
    url = engine.url
    print("=" * 60)
    print(f"Цель: {target}")
    print(f"  host:     {url.host}")
    print(f"  port:     {url.port}")
    print(f"  database: {url.database}")
    print(f"  user:     {url.username}")
    print("=" * 60)


def _schema() -> tuple[str, str]:
    ref = os.environ.get("SCHEMA_REFDATA", "gs_sys")
    fue_em = os.environ.get("SCHEMA_FUE_EM", "gs_fue_em")
    return ref, fue_em


def _load_rows(engine: Engine, schema: str) -> list[dict]:
    sql = text(
        f"""
        SELECT id, name, ref_uuid, database_version_id
        FROM {schema}.gs_sys_regional_districts
        ORDER BY database_version_id NULLS FIRST, id
        """
    )
    with engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(sql)]


def _load_version_labels(engine: Engine, schema: str) -> dict[int, str]:
    sql = text(
        f"""
        SELECT id, version_number
        FROM {schema}.gs_database_versions
        """
    )
    labels = {}
    with engine.connect() as conn:
        for row in conn.execute(sql):
            labels[int(row.id)] = str(row.version_number or row.id)
    return labels


def _version_label(version_id, labels: dict[int, str]) -> str:
    if version_id is None:
        return "без версии"
    return labels.get(int(version_id), str(version_id))


def _print_plan(plan, labels: dict[int, str]) -> None:
    if plan.within_version_collisions:
        print("\nОдинаковый ref_uuid у разных субъектов в одной версии:")
        for item in plan.within_version_collisions:
            print(
                f"  версия {_version_label(item['database_version_id'], labels)}: "
                f"{item['ref_uuid']} -> {', '.join(item['names'])} "
                f"(id={item['ids']})"
            )
    if plan.split_names:
        print("\nОдно название, разные ref_uuid по версиям:")
        for item in plan.split_names:
            print(
                f"  {item['name']}: {', '.join(item['ref_uuids'])} "
                f"(id={item['ids']})"
            )
    if not plan.updates:
        print("\nОбновления не нужны.")
        return
    print(f"\nПлан обновлений: {len(plan.updates)}")
    for update in plan.updates:
        print(
            f"  id={update.row_id} "
            f"[{_version_label(update.version_id, labels)}] "
            f"{update.name}: {update.old_uuid or '∅'} -> {update.new_uuid}"
        )


def _apply_plan(engine: Engine, schema: str, fue_em: str, plan) -> None:
    rd_sql = text(
        f"""
        UPDATE {schema}.gs_sys_regional_districts
        SET ref_uuid = :new_uuid
        WHERE id = :row_id
        """
    )
    mapping_sql = text(
        f"""
        UPDATE {fue_em}.gs_fue_em_territories_energy
        SET regional_district_ref_uuid = :new_uuid
        WHERE lower(trim(coalesce(regional_district_ref_uuid, ''))) = lower(:old_uuid)
        """
    )
    mapping_by_name_sql = text(
        f"""
        UPDATE {fue_em}.gs_fue_em_territories_energy
        SET regional_district_ref_uuid = :new_uuid
        WHERE lower(trim(coalesce(regional_district_ref_uuid, ''))) = lower(:old_uuid)
          AND (
            lower(trim(coalesce(external_name, ''))) = lower(:name)
            OR lower(trim(coalesce(name_ext, ''))) = lower(:name)
          )
        """
    )
    with engine.begin() as conn:
        for update in plan.updates:
            conn.execute(
                rd_sql,
                {"new_uuid": update.new_uuid, "row_id": update.row_id},
            )
    try:
        with engine.begin() as conn:
            for old_uuid, new_uuid, _name in mapping_uuid_rewrites(plan):
                conn.execute(
                    mapping_sql,
                    {"new_uuid": new_uuid, "old_uuid": old_uuid},
                )
            seen_pairs = set()
            for update in plan.updates:
                pair = (
                    norm_uuid(update.old_uuid),
                    norm_uuid(update.new_uuid),
                    update.name.lower(),
                )
                if pair in seen_pairs or not update.old_uuid:
                    continue
                seen_pairs.add(pair)
                conn.execute(
                    mapping_by_name_sql,
                    {
                        "new_uuid": update.new_uuid,
                        "old_uuid": update.old_uuid,
                        "name": update.name,
                    },
                )
    except Exception as exc:
        print(f"Субъекты обновлены; маппинг топлива пропущен: {exc}")


def _repair_target(target: str, apply: bool) -> int:
    engine = _engine_for_target(target)
    _print_target(target, engine)
    schema, fue_em = _schema()
    try:
        rows = _load_rows(engine, schema)
        labels = _load_version_labels(engine, schema)
    except Exception as exc:
        print(f"Не удалось прочитать БД ({target}): {exc}")
        return 1

    print(f"Строк субъектов: {len(rows)}")
    plan = plan_ref_uuid_repairs(rows)
    _print_plan(plan, labels)
    rewrites = mapping_uuid_rewrites(plan)
    if rewrites:
        print("\nВнешний маппинг топлива (однозначная замена uuid):")
        for old_uuid, new_uuid, name in rewrites:
            print(f"  {name}: {old_uuid} -> {new_uuid}")

    if not plan.updates:
        return 0
    if not apply:
        print("\nЭто просмотр. Для записи добавьте --apply")
        return 0

    _apply_plan(engine, schema, fue_em, plan)
    check = plan_ref_uuid_repairs(_load_rows(engine, schema))
    if check.updates or check.within_version_collisions or check.split_names:
        print("После записи остались расхождения:")
        _print_plan(check, labels)
        return 1
    print("\nЗаписано. Повторная проверка: расхождений нет.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Починить ref_uuid субъектов РФ в локальной БД и/или на gs01"
    )
    parser.add_argument(
        "--target",
        default="local",
        help="local, gs01 или local,gs01",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать изменения (без флага — только план)",
    )
    args = parser.parse_args()
    _load_dotenv()
    status = 0
    for target in _parse_targets(args.target):
        status = max(status, _repair_target(target, args.apply))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
