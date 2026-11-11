"""Операционный запуск переноса с резервными копиями и проверкой характеристик."""
import argparse
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values
import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("gs_rs_technical_inspection_codes", "gs_rs_equipment_technical_characteristics")


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def connect(host):
    values = dotenv_values(ROOT / ".env")
    return psycopg2.connect(host=host, port=values.get("DB_PORT", "5432"),
                            dbname=values["DB_NAME"], user=values["DB_USER"],
                            password=values["DB_PASSWORD"], connect_timeout=10)


def snapshot(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), inet_server_addr()::text, inet_server_port()")
        database, address, port = cursor.fetchone()
        cursor.execute("""
            SELECT count(*), md5(coalesce(string_agg(
                (to_jsonb(t) - ARRAY['machine_id','pgu_machine_id','match_status','match_details',
                                    'modified_by','modified_at','updated_at'])::text,
                E'\n' ORDER BY id), ''))
            FROM gs_rs.gs_rs_equipment_technical_characteristics t
        """)
        count, business_hash = cursor.fetchone()
        cursor.execute("SELECT database_version_id, count(*) FROM gs_rs.gs_rs_technical_inspection_codes GROUP BY 1 ORDER BY 1")
        codes_by_version = dict(cursor.fetchall())
        cursor.execute("""
            SELECT count(*)
            FROM gs_rs.gs_rs_technical_inspection_codes c
            LEFT JOIN gs_gen.gs_gen_machines m ON m.id=c.machine_id
            LEFT JOIN gs_gen.gs_gen_pgu_machines p ON p.id=c.pgu_machine_id
            WHERE m.id IS NULL OR m.database_version_id IS DISTINCT FROM c.database_version_id
               OR (c.pgu_machine_id IS NOT NULL AND
                   (p.id IS NULL OR p.database_version_id IS DISTINCT FROM c.database_version_id
                    OR p.id_parent_machine IS DISTINCT FROM c.machine_id))
        """)
        invalid_codes = cursor.fetchone()[0]
        return {"database": database, "address": address, "port": port,
                "characteristic_rows": count, "characteristic_business_md5": business_hash,
                "codes_by_version": codes_by_version, "code_rows": sum(codes_by_version.values()),
                "invalid_code_links": invalid_codes}


def run_script(host, apply, directory, name):
    env = os.environ.copy()
    env.update(DB_HOST=host, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    command = [sys.executable, str(ROOT / "scripts/backfill_technical_inspection_codes.py")]
    if apply:
        command.append("--apply")
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, encoding="utf-8")
    (directory / (name + ".stdout.log")).write_text(result.stdout, encoding="utf-8")
    (directory / (name + ".stderr.log")).write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Transfer failed with exit code {result.returncode}; inspect {directory / (name + '.stderr.log')}")
    lines = result.stdout.splitlines(keepends=True)
    start = next(index for index, line in enumerate(lines) if line.strip() == "{")
    report = json.JSONDecoder().raw_decode("".join(lines[start:]))[0]
    write_json(directory / (name + ".json"), report)
    print(name, json.dumps({key: len(value) if isinstance(value, list) else value
                           for key, value in report.items()}, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("local", "server"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    host = "localhost" if args.target == "local" else dotenv_values(ROOT / ".env.deploy")["DEPLOY_SERVER"]
    directory = Path(__file__).resolve().parent / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + args.target)
    directory.mkdir(exist_ok=False)
    print("report_directory", directory, flush=True)
    with connect(host) as connection:
        connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
        before = snapshot(connection)
        write_json(directory / "before.json", before)
        print("before", json.dumps(before), flush=True)
        if args.apply:
            for table in TABLES:
                backup_path = directory / (table + ".csv.gz")
                with connection.cursor() as cursor, gzip.open(backup_path, "wb") as output:
                    cursor.copy_expert(sql.SQL("COPY (SELECT * FROM {}.{} ORDER BY id) TO STDOUT WITH CSV HEADER").format(
                        sql.Identifier("gs_rs"), sql.Identifier(table)).as_string(connection), output)
                print("backup", backup_path.name, backup_path.stat().st_size,
                      hashlib.sha256(backup_path.read_bytes()).hexdigest(), flush=True)
    if not args.apply:
        run_script(host, False, directory, "preview")
        return
    applied = run_script(host, True, directory, "applied")
    with connect(host) as connection:
        connection.set_session(readonly=True)
        after = snapshot(connection)
    write_json(directory / "after.json", after)
    assert before["characteristic_rows"] == after["characteristic_rows"], "Characteristic row count changed"
    assert before["characteristic_business_md5"] == after["characteristic_business_md5"], "Characteristic values changed"
    assert after["invalid_code_links"] <= before["invalid_code_links"], "Invalid links increased"
    assert after["code_rows"] - before["code_rows"] == applied["created"], "Created code count differs"
    verify = run_script(host, False, directory, "verification")
    assert verify["created"] == verify["linked_rows"] == 0, "Repeat run is not empty"
    write_json(directory / "verified.json", {"verified": True, "target": args.target, "host": host,
                                             "before": before, "after": after})
    print("verified", json.dumps(after), flush=True)


if __name__ == "__main__":
    main()
