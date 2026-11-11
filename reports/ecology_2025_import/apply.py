import json
from pathlib import Path

from backup import TABLES, local_connection, ssh

OUT = Path(__file__).resolve().parent
payload = json.loads((OUT / 'payload.json').read_text(encoding='utf-8'))
encoded = json.dumps(payload, ensure_ascii=True)


def make_sql(target):
    baseline = json.loads((OUT / f'{target}_before.json').read_text(encoding='utf-8'))
    before = next(row for row in baseline['gs_eco_fuel_snapshots'] if row['id'] == 66)
    before_json = json.dumps(before, ensure_ascii=True)
    protected = TABLES[1:]
    hashes = ' UNION ALL '.join(f"SELECT '{table}' AS name, md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) AS hash FROM gs_eco.{table} t" for table in protected)
    locks = '\n'.join(f'LOCK TABLE gs_eco.{table} IN SHARE MODE;' for table in protected)
    return f"""BEGIN;
SET LOCAL lock_timeout = '15s';
LOCK TABLE gs_eco.gs_eco_fuel_snapshots IN EXCLUSIVE MODE;
{locks}
CREATE TEMP TABLE snapshots_before AS SELECT * FROM gs_eco.gs_eco_fuel_snapshots;
CREATE TEMP TABLE protected_before AS {hashes};
DO $$ BEGIN
 ASSERT (SELECT array_agg(id) FROM gs_sys.gs_database_versions WHERE is_active) = ARRAY[37], 'Active version changed';
 ASSERT (SELECT to_jsonb(t) FROM gs_eco.gs_eco_fuel_snapshots t WHERE id=66) = $before${before_json}$before$::jsonb, 'Target changed since backup';
 ASSERT (SELECT count(*) FROM gs_sys.gs_sys_fuels WHERE id=3852 AND database_version_id=37 AND lower(nazvl)='gtt')=1, 'GTT reference mismatch';
 ASSERT NOT EXISTS (SELECT 1 FROM gs_eco.gs_eco_operating_tes_inputs WHERE database_version_id=37 AND year_number=2025), 'Manual overrides would mask import';
END $$;
UPDATE gs_eco.gs_eco_fuel_snapshots SET payload=$payload${encoded}$payload$::json, updated_at=now()
WHERE id=66 AND database_version_id=37 AND year_number=2025 AND scope='operating';
DO $$ BEGIN
 ASSERT (SELECT payload::jsonb FROM gs_eco.gs_eco_fuel_snapshots WHERE id=66)=$payload${encoded}$payload$::jsonb, 'Payload mismatch';
 ASSERT NOT EXISTS (
  (SELECT to_jsonb(t) FROM gs_eco.gs_eco_fuel_snapshots t WHERE id<>66 EXCEPT SELECT to_jsonb(t) FROM snapshots_before t WHERE id<>66)
  UNION ALL
  (SELECT to_jsonb(t) FROM snapshots_before t WHERE id<>66 EXCEPT SELECT to_jsonb(t) FROM gs_eco.gs_eco_fuel_snapshots t WHERE id<>66)
 ), 'Other snapshots changed';
 ASSERT (SELECT to_jsonb(t)-'payload'-'updated_at' FROM gs_eco.gs_eco_fuel_snapshots t WHERE id=66)=(SELECT to_jsonb(t)-'payload'-'updated_at' FROM snapshots_before t WHERE id=66), 'Metadata changed';
 ASSERT NOT EXISTS (SELECT * FROM protected_before EXCEPT ({hashes})), 'Protected tables changed';
END $$;
COMMIT;
"""


if __name__ == '__main__':
    for target in ['server', 'local']:
        sql = make_sql(target)
        (OUT / f'{target}_import.sql').write_text(sql, encoding='utf-8')
        if target == 'server':
            result = ssh('sudo -n -u postgres psql -X -d gs_gen -P pager=off -v ON_ERROR_STOP=1', sql.encode('utf-8')).decode('utf-8')
        else:
            connection = local_connection()
            connection.autocommit = True
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                result = 'COMMIT: snapshot 66 updated; exact payload and protected data assertions passed.\n'
            finally:
                connection.close()
        (OUT / f'{target}_apply_result.txt').write_text(result, encoding='utf-8')
        print(target, result)
