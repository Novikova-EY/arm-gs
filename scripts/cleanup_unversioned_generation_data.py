#!/usr/bin/env python
"""Удаление неверсионных станций, агрегатов и групп с защитой именованных данных.

По умолчанию строит план только чтением. Для удаления нужны --apply и
--expected-plan с хешем проверенного плана. Перед DELETE сохраняет COPY CSV
в gzip, проверяет количество строк и контрольные суммы. Общие справочники
не удаляются. Наличие именованных потомков защищает связанную с ними
неверсионную часть графа: родителей, их параметры и связи.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import csv
from dataclasses import dataclass
from datetime import datetime
import gzip
from graphlib import TopologicalSorter
import hashlib
import json
import os
from pathlib import Path
import sys

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

ROOT_TABLES = (
    (config.SCHEMA_GENERATION, "gs_gen_stations"),
    (config.SCHEMA_GENERATION, "gs_gen_machines"),
    (config.SCHEMA_FUEL, "gs_fue_equipment_groups"),
)


@dataclass(frozen=True)
class Table:
    schema: str
    name: str
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]

    @property
    def key(self):
        return self.schema, self.name

    @property
    def qualified(self):
        return sql.Identifier(self.schema, self.name)

    @property
    def versioned(self):
        return "database_version_id" in self.columns


@dataclass(frozen=True)
class ForeignKey:
    child: tuple[str, str]
    parent: tuple[str, str]
    child_columns: tuple[str, ...]
    parent_columns: tuple[str, ...]

    def join(self):
        return sql.SQL(" AND ").join(
            sql.SQL("child.{} = parent.{}").format(sql.Identifier(child), sql.Identifier(parent))
            for child, parent in zip(self.child_columns, self.parent_columns)
        )


def read_catalog(cursor):
    cursor.execute("""
        SELECT n.nspname, t.relname,
               array_agg(a.attname ORDER BY a.attnum),
               ARRAY(SELECT pa.attname FROM pg_index i
                     CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum, ord)
                     JOIN pg_attribute pa ON pa.attrelid=t.oid AND pa.attnum=k.attnum
                     WHERE i.indrelid=t.oid AND i.indisprimary ORDER BY k.ord)
        FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
        JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum>0 AND NOT a.attisdropped
        WHERE t.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')
        GROUP BY n.nspname,t.relname,t.oid
    """)
    tables = {(s, n): Table(s, n, tuple(cols), tuple(pk)) for s, n, cols, pk in cursor.fetchall()}
    cursor.execute("""
        SELECT DISTINCT nc.nspname, c.relname, np.nspname, p.relname,
               ARRAY(SELECT a.attname FROM unnest(f.conkey) WITH ORDINALITY k(attnum, ord)
                     JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum ORDER BY k.ord),
               ARRAY(SELECT a.attname FROM unnest(f.confkey) WITH ORDINALITY k(attnum, ord)
                     JOIN pg_attribute a ON a.attrelid=p.oid AND a.attnum=k.attnum ORDER BY k.ord)
        FROM pg_constraint f JOIN pg_class c ON c.oid=f.conrelid
        JOIN pg_namespace nc ON nc.oid=c.relnamespace JOIN pg_class p ON p.oid=f.confrelid
        JOIN pg_namespace np ON np.oid=p.relnamespace WHERE f.contype='f'
    """)
    foreign_keys = [ForeignKey((cs, cn), (ps, pn), tuple(cc), tuple(pc))
                    for cs, cn, ps, pn, cc, pc in cursor.fetchall()]
    return tables, foreign_keys


def reachable_tables(roots, foreign_keys):
    reached = set(roots)
    while True:
        expanded = reached | {fk.child for fk in foreign_keys if fk.parent in reached}
        if expanded == reached:
            return reached
        reached = expanded


def protect_dependencies(seeds, parents):
    neighbors = defaultdict(set)
    for child, owners in parents.items():
        for parent in owners:
            neighbors[child].add(parent)
            neighbors[parent].add(child)
    protected = dict(seeds)
    pending = deque(seeds)
    while pending:
        row = pending.popleft()
        for neighbor in sorted(neighbors[row]):
            if neighbor not in protected:
                protected[neighbor] = f"Связь с защищенной записью {row[0][0]}.{row[0][1]} id={row[1]}"
                pending.append(neighbor)
    return protected


def deletion_order(keys, foreign_keys):
    graph = {key: set() for key in keys}
    for fk in foreign_keys:
        if fk.parent in graph and fk.child in graph:
            graph[fk.parent].add(fk.child)
    return list(TopologicalSorter(graph).static_order())


def build_plan(cursor, tables, foreign_keys):
    incoming = defaultdict(list)
    for fk in foreign_keys:
        incoming[fk.parent].append(fk)
    candidates = defaultdict(set)
    frontier = deque()
    seeds = {}
    parents = defaultdict(set)
    roots = {}
    for key in ROOT_TABLES:
        cursor.execute(sql.SQL("SELECT id FROM {} WHERE database_version_id IS NULL ORDER BY id").format(tables[key].qualified))
        ids = {row[0] for row in cursor.fetchall()}
        roots[key] = ids
        candidates[key].update(ids)
        frontier.append((key, ids))
    while frontier:
        parent_key, ids = frontier.popleft()
        if not ids:
            continue
        for fk in incoming[parent_key]:
            child = tables[fk.child]
            if child.primary_key != ("id",) or fk.parent_columns != ("id",):
                raise ValueError(f"Нужна отдельная проверка ключей {fk}")
            version = sql.SQL("child.database_version_id") if child.versioned else sql.SQL("NULL")
            query = sql.SQL("SELECT child.id, {}, parent.id FROM {} child JOIN {} parent ON {} WHERE parent.id=ANY(%s)").format(
                version, child.qualified, tables[parent_key].qualified, fk.join())
            cursor.execute(query, (sorted(ids),))
            new = set()
            for child_id, version_id, parent_id in cursor.fetchall():
                row = fk.child, child_id
                parents[row].add((parent_key, parent_id))
                if version_id is not None:
                    seeds[row] = f"Именованная версия БД {version_id}"
                if child_id not in candidates[fk.child]:
                    candidates[fk.child].add(child_id)
                    if version_id is None:
                        new.add(child_id)
            if new:
                frontier.append((fk.child, new))
    # У таблиц связей может не быть своей версии, но один из владельцев версионный.
    for fk in foreign_keys:
        ids = candidates.get(fk.child)
        parent = tables[fk.parent]
        if not ids or not parent.versioned or parent.schema in (config.SCHEMA_REFDATA, config.SCHEMA_AUTH):
            continue
        cursor.execute(sql.SQL("SELECT child.id, parent.id, parent.database_version_id FROM {} child JOIN {} parent ON {} WHERE child.id=ANY(%s) AND parent.database_version_id IS NOT NULL").format(
            tables[fk.child].qualified, parent.qualified, fk.join()), (sorted(ids),))
        for child_id, parent_id, version in cursor.fetchall():
            seeds[(fk.child, child_id)] = f"Ссылка на {parent.schema}.{parent.name} id={parent_id}, версия {version}"
    protected = protect_dependencies(seeds, parents)
    delete = {key: sorted(i for i in ids if (key, i) not in protected) for key, ids in candidates.items()}
    delete = {key: ids for key, ids in delete.items() if ids}
    serial = {".".join(key): ids for key, ids in sorted(delete.items())}
    digest = hashlib.sha256(json.dumps(serial, sort_keys=True).encode()).hexdigest()
    return {
        "sha256": digest,
        "delete": serial,
        "protected_roots": {
            ".".join(key): [{"id": i, "reason": protected[(key, i)]} for i in sorted(ids) if (key, i) in protected]
            for key, ids in roots.items()
        },
        "initial_roots": {".".join(key): len(ids) for key, ids in roots.items()},
    }


def fingerprint(cursor, table, excluded):
    cursor.execute(sql.SQL("SELECT count(*), md5(COALESCE(string_agg(md5(row_to_json(t)::text), '' ORDER BY id), '')) FROM {} t WHERE NOT (id=ANY(%s))").format(table.qualified), (excluded,))
    return cursor.fetchone()


def backup_rows(cursor, table, ids, directory):
    filename = f"{table.schema}.{table.name}.csv.gz"
    path = directory / filename
    query = sql.SQL("COPY (SELECT * FROM {} WHERE id=ANY(%s) ORDER BY id) TO STDOUT WITH (FORMAT CSV, HEADER TRUE)").format(table.qualified)
    with gzip.open(path, "wb") as stream:
        cursor.copy_expert(cursor.mogrify(query, (ids,)).decode(), stream)
    csv.field_size_limit(2**31 - 1)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        columns = next(reader)
        count = sum(1 for _ in reader)
    if count != len(ids) or columns != list(table.columns):
        raise ValueError(f"Проверка резервной копии не прошла: {filename}")
    return {"file": filename, "rows": count, "columns": columns,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run(connection, directory, *, apply=False, expected_plan=None):
    with connection.cursor() as cursor:
        tables, foreign_keys = read_catalog(cursor)
        reachable = reachable_tables(ROOT_TABLES, foreign_keys)
        for key in reachable:
            if tables[key].primary_key != ("id",):
                raise ValueError(f"Неподдерживаемый первичный ключ: {key}")
            if key[0] in (config.SCHEMA_REFDATA, config.SCHEMA_AUTH, config.SCHEMA_LOGS):
                raise ValueError(f"Служебная таблица в зависимостях: {key}")
        if apply:
            cursor.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
                sql.SQL(", ").join(tables[key].qualified for key in sorted(reachable))))
        cursor.execute("SELECT tgrelid::regclass::text, tgname FROM pg_trigger WHERE NOT tgisinternal AND tgenabled <> 'D' AND (tgtype & 8) <> 0 AND tgrelid=ANY(%s::regclass[])",
                       ([".".join(key) for key in sorted(reachable)],))
        if cursor.fetchall():
            raise ValueError("Найдены пользовательские DELETE-триггеры: нужна проверка их побочных эффектов")
        plan = build_plan(cursor, tables, foreign_keys)
        write_json(directory / "plan.json", plan)
        print("Plan SHA256:", plan["sha256"], flush=True)
        for key, ids in plan["delete"].items():
            print(f"DELETE {key}: {len(ids)}", flush=True)
        for key, items in plan["protected_roots"].items():
            print(f"PROTECTED {key}: {len(items)}", flush=True)
        if not apply:
            return plan
        if expected_plan != plan["sha256"]:
            raise ValueError("План изменился или не подтвержден: удаление отменено")
        delete = {tuple(key.split(".")): ids for key, ids in plan["delete"].items()}
        order = deletion_order(delete, foreign_keys)
        before = {key: fingerprint(cursor, tables[key], delete.get(key, [])) for key in sorted(reachable)}
        backup = {}
        for key in order:
            backup[".".join(key)] = backup_rows(cursor, tables[key], delete[key], directory)
        manifest = {"target": connection.info.host, "database": connection.info.dbname,
                    "plan_sha256": plan["sha256"], "files": backup,
                    "restore_order": [".".join(key) for key in reversed(order)],
                    "retained_before": {".".join(key): value for key, value in before.items()}}
        write_json(directory / "backup_manifest.json", manifest)
        print("Backups verified; deleting in one transaction.", flush=True)
        deleted = {}
        for key in order:
            version_guard = sql.SQL(" AND database_version_id IS NULL") if tables[key].versioned else sql.SQL("")
            cursor.execute(sql.SQL("DELETE FROM {} WHERE id=ANY(%s){}").format(tables[key].qualified, version_guard), (delete[key],))
            if cursor.rowcount != len(delete[key]):
                raise ValueError(f"Изменилось количество строк: {key}")
            deleted[".".join(key)] = cursor.rowcount
        for key in sorted(reachable):
            if fingerprint(cursor, tables[key], delete.get(key, [])) != before[key]:
                raise ValueError(f"Сохраненные данные изменились: {key}; транзакция отменена")
        for key in ROOT_TABLES:
            cursor.execute(sql.SQL("SELECT count(*) FROM {} WHERE database_version_id IS NULL").format(tables[key].qualified))
            if cursor.fetchone()[0] != len(plan["protected_roots"][".".join(key)]):
                raise ValueError(f"Не совпало количество защищенных записей: {key}")
        plan["deleted_counts"] = deleted
        plan["retained_fingerprints_verified"] = True
        return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("local", "gs01"), default="gs01")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/unversioned_data_cleanup" / datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()
    if args.apply and not args.expected_plan:
        parser.error("Для --apply требуется --expected-plan из проверенного dry-run")
    args.output.mkdir(parents=True, exist_ok=False)
    host = config.DB_HOST if args.target == "local" else os.getenv("GS01_DB_HOST", "10.31.205.27")
    port = config.DB_PORT if args.target == "local" else os.getenv("GS01_DB_PORT", config.DB_PORT)
    with psycopg2.connect(host=host, port=port, dbname=config.DB_NAME, user=config.DB_USER,
                          password=config.DB_PASSWORD, connect_timeout=8,
                          options="-c lock_timeout=5000 -c statement_timeout=120000") as connection:
        connection.set_session(isolation_level="REPEATABLE READ", readonly=not args.apply)
        result = run(connection, args.output, apply=args.apply, expected_plan=args.expected_plan)
    result["committed"] = args.apply
    write_json(args.output / "result.json", result)
    print("COMMITTED" if args.apply else "DRY-RUN ONLY", flush=True)
    print("Report:", args.output, flush=True)


if __name__ == "__main__":
    main()
