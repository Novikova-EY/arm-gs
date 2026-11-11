import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
HOST = "novikova-eyu@10.31.205.27"
payload = json.loads((OUT / "payload.json").read_text(encoding="utf-8"))
stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
backup = f"/var/backups/generation-app/manual_ecology_2024_{stamp}"


def ssh(command, data=None):
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", HOST, command], input=data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.stderr:
        print(result.stderr.decode("utf-8"), end="")
    result.check_returncode()
    return result.stdout


sql = r"""\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '15s';
LOCK TABLE gs_eco.gs_eco_fuel_snapshots IN EXCLUSIVE MODE;
LOCK TABLE gs_eco.gs_eco_operating_tes_inputs IN SHARE MODE;
CREATE TEMP TABLE snapshots_before AS SELECT * FROM gs_eco.gs_eco_fuel_snapshots;
CREATE TEMP TABLE protected_before AS
SELECT 'inputs' AS name, md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) AS hash FROM gs_eco.gs_eco_operating_tes_inputs t
UNION ALL SELECT 'submissions', md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) FROM gs_eco.gs_eco_fuel_submissions t
UNION ALL SELECT 'coefficients', md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) FROM gs_eco.gs_eco_operating_tes_coefficients t
UNION ALL SELECT 'fuel_chars', md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) FROM gs_eco.gs_eco_operating_tes_fuel_chars t;
DO $$ BEGIN
  ASSERT (SELECT array_agg(id) FROM gs_sys.gs_database_versions WHERE is_active) = ARRAY[37], 'Active version changed';
  ASSERT (SELECT count(*) FROM gs_eco.gs_eco_fuel_snapshots WHERE id=65 AND database_version_id=37 AND year_number=2024 AND scope='operating')=1, 'Snapshot scope mismatch';
  ASSERT NOT EXISTS (SELECT 1 FROM gs_eco.gs_eco_operating_tes_inputs WHERE database_version_id=37 AND year_number=2024), 'Manual overrides would mask imported data';
END $$;
UPDATE gs_eco.gs_eco_fuel_snapshots
SET payload = $payload$PAYLOAD_JSON$payload$::json, updated_at=now()
WHERE id=65 AND database_version_id=37 AND year_number=2024 AND scope='operating';
DO $$ BEGIN
  ASSERT (SELECT payload::jsonb FROM gs_eco.gs_eco_fuel_snapshots WHERE id=65) = $payload$PAYLOAD_JSON$payload$::jsonb, 'Payload mismatch';
  ASSERT NOT EXISTS (
    (SELECT to_jsonb(t) AS row FROM gs_eco.gs_eco_fuel_snapshots t WHERE id<>65 EXCEPT SELECT to_jsonb(t) FROM snapshots_before t WHERE id<>65)
    UNION ALL
    (SELECT to_jsonb(t) FROM snapshots_before t WHERE id<>65 EXCEPT SELECT to_jsonb(t) FROM gs_eco.gs_eco_fuel_snapshots t WHERE id<>65)
  ), 'Other snapshots changed';
  ASSERT (SELECT to_jsonb(t)-'payload'-'updated_at' FROM gs_eco.gs_eco_fuel_snapshots t WHERE id=65) =
         (SELECT to_jsonb(t)-'payload'-'updated_at' FROM snapshots_before t WHERE id=65), 'Snapshot metadata changed';
  ASSERT NOT EXISTS (
    SELECT * FROM protected_before EXCEPT (
      SELECT 'inputs', md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) FROM gs_eco.gs_eco_operating_tes_inputs t
      UNION ALL SELECT 'submissions', md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) FROM gs_eco.gs_eco_fuel_submissions t
      UNION ALL SELECT 'coefficients', md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) FROM gs_eco.gs_eco_operating_tes_coefficients t
      UNION ALL SELECT 'fuel_chars', md5(coalesce(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'')) FROM gs_eco.gs_eco_operating_tes_fuel_chars t
    )
  ), 'Protected ecology data changed';
END $$;
SELECT 'unchanged_other_snapshots' AS check, count(*) AS rows FROM snapshots_before WHERE id<>65;
TABLE protected_before;
COMMIT;
""".replace("PAYLOAD_JSON", json.dumps(payload, ensure_ascii=True))
(OUT / "replacement.sql").write_text(sql, encoding="utf-8")

backup_command = (
    "set -e; set -o pipefail; "
    f"sudo -n install -d -m 700 {backup}; "
    "sudo -n -u postgres pg_dump -d gs_gen --data-only "
    "-t gs_eco.gs_eco_fuel_snapshots -t gs_eco.gs_eco_operating_tes_inputs "
    "-t gs_eco.gs_eco_fuel_submissions "
    f"| sudo -n tee {backup}/accepted_fuel_before.sql >/dev/null; "
    f"sudo -n test -s {backup}/accepted_fuel_before.sql"
)
ssh(backup_command)
(OUT / "server_backup_path.txt").write_text(backup + "\n", encoding="utf-8")
(OUT / "accepted_fuel_before.sql").write_bytes(ssh(f"sudo -n cat {backup}/accepted_fuel_before.sql"))
before_sql = "SELECT row_to_json(t) FROM gs_eco.gs_eco_fuel_snapshots t WHERE id=65;"
before = ssh("sudo -n -u postgres psql -X -d gs_gen -At -v ON_ERROR_STOP=1", before_sql.encode())
json.loads(before)
(OUT / "snapshot_before.json").write_bytes(before)
result = ssh("sudo -n -u postgres psql -X -d gs_gen -P pager=off -v ON_ERROR_STOP=1", sql.encode("utf-8"))
(OUT / "apply_result.txt").write_bytes(result)
print(result.decode("utf-8"))
print("SERVER BACKUP:", backup)
