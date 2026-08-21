#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Полная копия БД gs_gen с удалённого сервера gs01 на локальный PostgreSQL.

Использует pg_dump (custom format) + pg_restore.
Перезаписывает объекты и данные в локальной БД gs_gen.

По умолчанию НЕ трогает локальную историю Alembic
(gs_auth.alembic_version / public.alembic_version): перед DROP SCHEMA
версия сохраняется и после restore возвращается обратно.

Запуск из корня репозитория:

  python scripts/sync_gs_gen_from_gs01.py --dry-run
  python scripts/sync_gs_gen_from_gs01.py --yes

Переменные окружения (или .env в корне проекта):
  GS01_DB_HOST   — хост gs01 (по умолчанию 10.31.205.27)
  GS01_DB_PORT   — порт (по умолчанию 5432)
  DB_USER, DB_PASSWORD / DB_PASS, DB_NAME — учётные данные
  DB_HOST        — локальный хост (по умолчанию localhost)
  DB_PORT        — локальный порт
  PG_DUMP, PG_RESTORE, PSQL — пути к утилитам (опционально)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Flask-Migrate хранит ревизию в SCHEMA_AUTH (обычно gs_auth).
_ALEMBIC_TABLES = (
    ("gs_auth", "alembic_version"),
    ("public", "alembic_version"),
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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _find_pg_tool(name: str) -> str:
    explicit = os.environ.get(name.upper().replace("-", "_"))
    if explicit:
        return explicit
    found = shutil.which(name)
    if found:
        return found
    default = Path(r"C:\Program Files\PostgreSQL\17\bin") / f"{name}.exe"
    if default.is_file():
        return str(default)
    raise FileNotFoundError(
        f"Не найден {name}. Укажите PG_DUMP/PSQL/PG_RESTORE в .env или добавьте в PATH."
    )


def _run(cmd: list[str], env: dict[str, str], label: str) -> None:
    print(f"\n>>> {label}")
    print("    ", " ".join(_mask_cmd(cmd)))
    subprocess.run(cmd, env=env, check=True)


def _run_capture(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    # pg_* on Windows often emit CP866/CP1251; avoid crashing on decode.
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _mask_cmd(cmd: list[str]) -> list[str]:
    masked: list[str] = []
    skip_next = False
    for part in cmd:
        if skip_next:
            masked.append("***")
            skip_next = False
            continue
        if part in ("-W",):
            skip_next = True
        masked.append(part)
    return masked


def _psql_scalar(
    psql: str,
    env: dict[str, str],
    host: str,
    port: str,
    user: str,
    db_name: str,
    sql: str,
) -> str:
    cmd = [
        psql,
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        db_name,
        "-At",
        "-c",
        sql,
    ]
    result = _run_capture(cmd, env)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _backup_local_alembic_versions(
    psql: str,
    env: dict[str, str],
    host: str,
    port: str,
    user: str,
    db_name: str,
) -> dict[str, list[str]]:
    """Сохраняет version_num из локальных alembic_version до DROP SCHEMA."""
    backup: dict[str, list[str]] = {}
    for schema, table in _ALEMBIC_TABLES:
        exists = _psql_scalar(
            psql,
            env,
            host,
            port,
            user,
            db_name,
            f"SELECT to_regclass('{schema}.{table}') IS NOT NULL;",
        )
        if exists.lower() not in ("t", "true", "1"):
            continue
        raw = _psql_scalar(
            psql,
            env,
            host,
            port,
            user,
            db_name,
            f"SELECT coalesce(string_agg(version_num, ','), '') FROM {schema}.{table};",
        )
        versions = [v for v in raw.split(",") if v]
        if versions:
            backup[f"{schema}.{table}"] = versions
            print(f"    backup {schema}.{table}: {versions}")
    return backup


def _restore_local_alembic_versions(
    psql: str,
    env: dict[str, str],
    host: str,
    port: str,
    user: str,
    db_name: str,
    backup: dict[str, list[str]],
) -> None:
    """Возвращает сохранённые ревизии после restore (серверные значения вытесняются)."""
    if not backup:
        print("    backup alembic_version пуст — stamp после sync не выполнен")
        return

    for full_name, versions in backup.items():
        schema, table = full_name.split(".", 1)
        # Таблица могла не попасть в дамп (exclude) — создаём при необходимости.
        create_sql = (
            f"CREATE TABLE IF NOT EXISTS {schema}.{table} ("
            f"version_num VARCHAR(32) NOT NULL PRIMARY KEY);"
        )
        clear_sql = f"DELETE FROM {schema}.{table};"
        values_sql = ", ".join(f"('{v}')" for v in versions)
        insert_sql = f"INSERT INTO {schema}.{table}(version_num) VALUES {values_sql};"
        cmd = [
            psql,
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            create_sql + clear_sql + insert_sql,
        ]
        print(f"    restore {full_name} -> {versions}")
        subprocess.run(cmd, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Копия gs_gen с gs01 на localhost")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать команды, не выполнять",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить перезапись локальной БД gs_gen",
    )
    parser.add_argument(
        "--dump-file",
        type=str,
        default="",
        help="Путь к .dump (по умолчанию C:\\temp\\gs_gen_from_gs01_<timestamp>.dump)",
    )
    parser.add_argument(
        "--skip-dump",
        action="store_true",
        help="Не делать pg_dump, только pg_restore из --dump-file",
    )
    parser.add_argument(
        "--local-user",
        type=str,
        default="",
        help="Пользователь для pg_restore/psql локально (по умолчанию DB_USER; для --clean часто postgres)",
    )
    parser.add_argument(
        "--local-password",
        type=str,
        default="",
        help="Пароль локального пользователя (иначе DB_PASSWORD)",
    )
    parser.add_argument(
        "--exclude-migrations",
        action="store_true",
        default=True,
        help="Не копировать alembic_version с сервера (по умолчанию: да)",
    )
    parser.add_argument(
        "--include-migrations",
        action="store_true",
        help="Копировать alembic_version с сервера (локальная история будет перезаписана)",
    )
    args = parser.parse_args()
    exclude_migrations = not args.include_migrations
    if args.exclude_migrations and args.include_migrations:
        # Явный --include-migrations важнее.
        exclude_migrations = False
    args.exclude_migrations = exclude_migrations

    _load_dotenv()

    remote_host = os.environ.get("GS01_DB_HOST", "10.31.205.27")
    remote_port = os.environ.get("GS01_DB_PORT", os.environ.get("DB_PORT", "5432"))
    local_host = os.environ.get("DB_HOST", "localhost")
    local_port = os.environ.get("DB_PORT", "5432")
    remote_user = os.environ.get("DB_USER", "generation")
    local_user = args.local_user or os.environ.get(
        "LOCAL_PG_USER", remote_user
    )
    db_name = os.environ.get("DB_NAME", "gs_gen")
    remote_password = os.environ.get("DB_PASSWORD") or os.environ.get(
        "DB_PASS", ""
    )
    local_password = args.local_password or os.environ.get(
        "LOCAL_PG_PASSWORD", remote_password
    )

    if not remote_password:
        print("Ошибка: задайте DB_PASSWORD или DB_PASS в .env", file=sys.stderr)
        return 1

    if args.dump_file:
        dump_path = Path(args.dump_file)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = Path(r"C:\temp") / f"gs_gen_from_gs01_{stamp}.dump"

    pg_dump = _find_pg_tool("pg_dump")
    pg_restore = _find_pg_tool("pg_restore")
    psql = _find_pg_tool("psql")

    remote_env = os.environ.copy()
    remote_env["PGPASSWORD"] = remote_password
    local_env = os.environ.copy()
    local_env["PGPASSWORD"] = local_password

    print("=" * 60)
    print("Копирование БД gs_gen: gs01 -> localhost")
    print(f"  Источник:  {remote_host}:{remote_port}/{db_name} (user {remote_user})")
    print(f"  Приёмник:  {local_host}:{local_port}/{db_name} (user {local_user})")
    print(f"  Dump file: {dump_path}")
    if args.exclude_migrations:
        print(
            "  Миграции: локальный alembic_version СОХРАНЯЕТСЯ "
            "(gs_auth/public; серверная ревизия не копируется)"
        )
    else:
        print("  Миграции: alembic_version будет скопирован с сервера")
    print("=" * 60)

    if not args.yes and not args.dry_run:
        print(
        "\nВНИМАНИЕ: локальная БД gs_gen будет перезаписана (DROP SCHEMA + restore).\n"
        "Остановите run.py / приложение, использующее БД.\n"
        "Для CREATE SCHEMA нужен пользователь с правом CREATE на БД "
        "(часто --local-user postgres).\n"
        "Повторите с флагом --yes для запуска.\n"
    )
        return 1

    dump_path.parent.mkdir(parents=True, exist_ok=True)

    dump_cmd = [
        pg_dump,
        "-h",
        remote_host,
        "-p",
        str(remote_port),
        "-U",
        remote_user,
        "-d",
        db_name,
        "-Fc",
        "--no-owner",
        "--no-privileges",
        "-f",
        str(dump_path),
        "-v",
    ]
    if args.exclude_migrations:
        dump_cmd.extend(
            [
                "--exclude-table",
                "public.alembic_version",
                "--exclude-table",
                "gs_auth.alembic_version",
            ]
        )

    terminate_sql = (
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid() "
        f"AND usename = current_user;"
    )

    terminate_cmd = [
        psql,
        "-h",
        local_host,
        "-p",
        str(local_port),
        "-U",
        local_user,
        "-d",
        db_name,
        "-c",
        terminate_sql,
    ]

    # All app schemas currently present on gs01 (extend if new schemas appear).
    app_schemas = (
        "gs_auth, gs_bem, gs_ec, gs_ei, gs_ekp, gs_fue, gs_fue_em, "
        "gs_gen, gs_logs, gs_pd, gs_sys, gs_ter"
    )
    drop_schemas_sql = f"DROP SCHEMA IF EXISTS {app_schemas} CASCADE;"
    if not args.exclude_migrations:
        drop_schemas_sql += (
            " DROP TABLE IF EXISTS public.alembic_version;"
            " DROP TABLE IF EXISTS gs_auth.alembic_version;"
        )

    drop_schemas_cmd = [
        psql,
        "-h",
        local_host,
        "-p",
        str(local_port),
        "-U",
        local_user,
        "-d",
        db_name,
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        drop_schemas_sql,
    ]

    restore_cmd = [
        pg_restore,
        "-h",
        local_host,
        "-p",
        str(local_port),
        "-U",
        local_user,
        "-d",
        db_name,
        "--no-owner",
        "--no-privileges",
        "-v",
        str(dump_path),
    ]

    if args.dry_run:
        if not args.skip_dump:
            print("\n[dry-run] pg_dump:")
            print("   ", " ".join(_mask_cmd(dump_cmd)))
        print("\n[dry-run] terminate connections:")
        print("   ", " ".join(_mask_cmd(terminate_cmd)))
        if args.exclude_migrations:
            print("\n[dry-run] backup local alembic_version (gs_auth/public)")
        print("\n[dry-run] drop application schemas:")
        print("   ", " ".join(_mask_cmd(drop_schemas_cmd)))
        print("\n[dry-run] pg_restore:")
        print("   ", " ".join(_mask_cmd(restore_cmd)))
        if args.exclude_migrations:
            print("\n[dry-run] restore local alembic_version after pg_restore")
        return 0

    alembic_backup: dict[str, list[str]] = {}
    try:
        if not args.skip_dump:
            _run(dump_cmd, remote_env, "pg_dump с gs01")
            size_mb = dump_path.stat().st_size / (1024 * 1024)
            print(f"    Дамп сохранён: {dump_path} ({size_mb:.1f} MiB)")
        elif not dump_path.is_file():
            print(f"Ошибка: файл дампа не найден: {dump_path}", file=sys.stderr)
            return 1

        print("\n>>> завершение сессий к локальной gs_gen (не критично при ошибке)")
        try:
            subprocess.run(terminate_cmd, env=local_env, check=True)
        except subprocess.CalledProcessError:
            print(
                "    Не удалось завершить все сессии (нужен superuser или остановите run.py)."
            )

        if args.exclude_migrations:
            print("\n>>> backup локального alembic_version")
            alembic_backup = _backup_local_alembic_versions(
                psql,
                local_env,
                local_host,
                local_port,
                local_user,
                db_name,
            )

        print(
            "\n    Закройте в pgAdmin вкладки Query Tool, подключённые к gs_gen "
            "(иначе DROP SCHEMA может зависнуть)."
        )
        _run(drop_schemas_cmd, local_env, "удаление схем gs_* на локальной БД")
        print("\n>>> pg_restore в локальную gs_gen")
        print("    ", " ".join(_mask_cmd(restore_cmd)))
        restore_result = _run_capture(restore_cmd, local_env)
        if restore_result.stdout:
            print(restore_result.stdout[-8000:])
        if restore_result.stderr:
            print(restore_result.stderr[-4000:], file=sys.stderr)
        if restore_result.returncode != 0:
            print(
                f"\n    pg_restore завершился с кодом {restore_result.returncode}. "
                "Часто это postgres_fdw/sipr_srv с сервера — для локальной разработки не критично."
            )

        if args.exclude_migrations:
            print("\n>>> restore локального alembic_version")
            _restore_local_alembic_versions(
                psql,
                local_env,
                local_host,
                local_port,
                local_user,
                db_name,
                alembic_backup,
            )
    except subprocess.CalledProcessError as exc:
        print(f"\nОшибка (код {exc.returncode}).", file=sys.stderr)
        print(
            "Частые причины: открыты pgAdmin/run.py к gs_gen, нет прав на DROP SCHEMA. "
            "Закройте соединения и повторите с --skip-dump.",
            file=sys.stderr,
        )
        return exc.returncode or 1

    print("\nГотово. Рекомендуется проверить:")
    verify_cmd = [
        psql,
        "-h",
        local_host,
        "-p",
        str(local_port),
        "-U",
        local_user,
        "-d",
        db_name,
        "-c",
        "SELECT schemaname, COUNT(*) AS tables "
        "FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') "
        "GROUP BY 1 ORDER BY 1;",
    ]
    _run(verify_cmd, local_env, "сводка по схемам")

    sample_sql = (
        "SELECT "
        "(SELECT COUNT(*) FROM gs_sys.gs_sys_database_versions) AS db_versions, "
        "(SELECT COUNT(*) FROM gs_gen.gs_gen_stations) AS stations, "
        "(SELECT COUNT(*) FROM gs_pd.gs_pd_regional_energy_system_demand_params) AS res_demand;"
    )
    sample_cmd = [
        psql,
        "-h",
        local_host,
        "-p",
        str(local_port),
        "-U",
        local_user,
        "-d",
        db_name,
        "-c",
        sample_sql,
    ]
    _run(sample_cmd, local_env, "контрольные счётчики (локально)")

    alembic_check_sql = (
        "SELECT schema_name, version_num FROM ("
        "  SELECT 'gs_auth'::text AS schema_name, version_num "
        "  FROM gs_auth.alembic_version "
        "  UNION ALL "
        "  SELECT 'public'::text, version_num "
        "  FROM public.alembic_version "
        "  WHERE EXISTS ("
        "    SELECT 1 FROM information_schema.tables "
        "    WHERE table_schema='public' AND table_name='alembic_version'"
        "  )"
        ") t ORDER BY 1;"
    )
    alembic_check_cmd = [
        psql,
        "-h",
        local_host,
        "-p",
        str(local_port),
        "-U",
        local_user,
        "-d",
        db_name,
        "-c",
        alembic_check_sql,
    ]
    try:
        _run(alembic_check_cmd, local_env, "локальный alembic_version после sync")
    except subprocess.CalledProcessError:
        print("    Не удалось прочитать alembic_version (проверьте вручную).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
