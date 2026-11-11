import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

OUT = Path(__file__).resolve().parent
HOST = 'novikova-eyu@10.31.205.27'
TABLES = ['gs_eco_fuel_snapshots', 'gs_eco_fuel_submissions', 'gs_eco_operating_tes_inputs', 'gs_eco_operating_tes_coefficients', 'gs_eco_operating_tes_fuel_chars']


def ssh(command, data=None):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', HOST, command], input=data, capture_output=True)
    if result.stderr:
        print(result.stderr.decode('utf-8'), end='')
    result.check_returncode()
    return result.stdout


def local_connection():
    values = dotenv_values(OUT.parents[1] / '.env')
    return psycopg2.connect(host=values['DB_HOST'], port=values['DB_PORT'], dbname=values['DB_NAME'], user=values['DB_USER'], password=values['DB_PASSWORD'], connect_timeout=15)


if __name__ == '__main__':
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    backup = f'/var/backups/generation-app/manual_ecology_2025_{stamp}'
    flags = ' '.join(f'-t gs_eco.{table}' for table in TABLES)
    ssh(f'set -e; set -o pipefail; sudo -n install -d -m 700 {backup}; sudo -n -u postgres pg_dump -d gs_gen --data-only {flags} | sudo -n tee {backup}/ecology_before.sql >/dev/null; sudo -n test -s {backup}/ecology_before.sql')
    (OUT / 'server_backup_path.txt').write_text(backup + '\n', encoding='utf-8')
    (OUT / 'server_ecology_before.sql').write_bytes(ssh(f'sudo -n cat {backup}/ecology_before.sql'))
    query = 'SELECT json_build_object(' + ','.join(f"'{table}', (SELECT coalesce(json_agg(t), '[]'::json) FROM gs_eco.{table} t)" for table in TABLES) + ');'
    (OUT / 'server_before.json').write_bytes(ssh('sudo -n -u postgres psql -X -d gs_gen -At -v ON_ERROR_STOP=1', query.encode()))
    with local_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute(query)
            data = cursor.fetchone()[0]
    (OUT / 'local_before.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Backups saved:', backup)
