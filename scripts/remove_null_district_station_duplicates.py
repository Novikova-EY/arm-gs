#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Удаляет станции-дубликаты без субъекта РФ (id_regional_district IS NULL),
если в той же версии БД есть одноимённая станция с субъектом.

Такие записи ломают сверку external_code: пустой субъект считается
совпадающим с любым, и в жёлтую строку попадает чужой код.

Запуск из корня репозитория:

  python scripts/remove_null_district_station_duplicates.py
  python scripts/remove_null_district_station_duplicates.py --target local --apply
  python scripts/remove_null_district_station_duplicates.py --target gs01 --apply
  python scripts/remove_null_district_station_duplicates.py --target local,gs01 --apply

Цели:
  local — DB_HOST из .env
  gs01  — GS01_DB_HOST (по умолчанию 10.31.205.27), те же DB_USER/DB_NAME
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from app.generation.services.station_services.null_district_duplicate_cleanup_services import (  # noqa: E402
    cleanup_null_district_duplicates,
    find_null_district_name_duplicates,
    schemas_from_env,
)


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


def _print_plan(duplicates) -> None:
    print(f"Найдено дубликатов без субъекта: {len(duplicates)}")
    if not duplicates:
        return
    blocked = [item for item in duplicates if item.blocked_reason]
    ready = [item for item in duplicates if not item.blocked_reason]
    print(f"  к удалению: {len(ready)}")
    print(f"  пропуск:    {len(blocked)}")
    print()
    for item in duplicates:
        keepers = ", ".join(
            f"{kid} {rd}" for kid, rd in zip(item.keeper_ids, item.keeper_rd_names)
        )
        mark = f"ПРОПУСК ({item.blocked_reason})" if item.blocked_reason else "удалить"
        print(
            f"  [{mark}] id={item.id} ver={item.version_number} "
            f"name={item.name!r} code={item.external_code} "
            f"machines={item.machines} boilers={item.boilers} "
            f"gen={item.generations} gaes={item.gaes} "
            f"eg_links={item.eg_links} eg_sets={item.eg_sets} "
            f"-> {keepers}"
        )


def _run_target(target: str, apply: bool) -> int:
    engine = _engine_for_target(target)
    _print_target(target, engine)
    schemas = schemas_from_env()
    try:
        with engine.connect() as conn:
            duplicates = find_null_district_name_duplicates(conn, schemas)
    except Exception as exc:
        print(f"Не удалось прочитать БД ({target}): {exc}")
        return 1

    _print_plan(duplicates)
    if not duplicates:
        print("Нечего удалять.")
        return 0
    if not apply:
        print("\nЭто просмотр. Для удаления добавьте --apply")
        return 0

    try:
        with engine.begin() as conn:
            report = cleanup_null_district_duplicates(
                conn,
                duplicates=duplicates,
                schemas=schemas,
                apply=True,
            )
    except Exception as exc:
        print(f"Ошибка удаления ({target}): {exc}")
        return 1

    print("\nУдалено станций:", len(report.deleted_station_ids))
    print("  перенесено выработок:", report.moved_generations)
    print("  удалено выработок (уже были у оригинала):", report.deleted_generations)
    print("  перенесено заряда ГАЭС:", report.moved_gaes)
    print("  удалено заряда ГАЭС:", report.deleted_gaes)
    print("  перенесено связей ГО:", report.reassigned_eg_links)
    print("  удалено связей ГО:", report.deleted_eg_links)
    print("  перенесено наборов ГО:", report.moved_eg_sets)
    print("  удалено наборов ГО:", report.deleted_eg_sets)
    if report.skipped:
        print("Пропущено:")
        for station_id, reason in report.skipped:
            print(f"  id={station_id}: {reason}")

    with engine.connect() as conn:
        leftover = find_null_district_name_duplicates(conn, schemas)
    leftover_ready = [item for item in leftover if not item.blocked_reason]
    if leftover_ready:
        print("После удаления остались дубликаты:")
        _print_plan(leftover)
        return 1
    print("Повторная проверка: дубликатов без субъекта больше нет.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Удалить станции-дубликаты без субъекта РФ в local и/или gs01"
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
    exit_code = 0
    for target in _parse_targets(args.target):
        exit_code = max(exit_code, _run_target(target, args.apply))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
