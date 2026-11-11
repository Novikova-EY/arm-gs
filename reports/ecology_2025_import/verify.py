import json
import subprocess
import sys
from pathlib import Path

from backup import ssh

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
expected = json.loads((OUT / 'payload.json').read_text(encoding='utf-8'))
script = '''import os
import sys
import json
from decimal import Decimal
from dotenv import load_dotenv
LOAD_ENV
os.environ['ENABLE_SCHEDULED_BACKUPS'] = 'False'
os.chdir(ROOT_PATH)
sys.path.insert(0, os.getcwd())
from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.common.services.database_version_filter import get_current_db_version_id
from app.ecology.models.fuel_exchange_model import EcologyFuelSnapshot
from app.ecology.services.fuel_exchange_services import load_accepted_fuel_inputs
from app.ecology.services.operating_tes_page_services import build_operating_tes_table_context
expected = json.loads(EXPECTED_JSON)
app = create_app()
url = '/ecology/operating_tes/vsego/toplivo/?start_year=2025&end_year=2030&rounding_digits=1&coefficient_rounding_digits=0&view_year=2025'
with app.test_request_context(url):
    db.session.execute(text('SET TRANSACTION READ ONLY'))
    assert get_current_db_version_id() == 37
    snapshot = EcologyFuelSnapshot.query.filter_by(id=66, database_version_id=37, year_number=2025, scope='operating').one()
    assert snapshot.payload == expected
    accepted = load_accepted_fuel_inputs([2025])[2025]
    assert accepted == {slug: {field: Decimal(value) for field, value in bucket.items()} for slug, bucket in expected.items()}
    context = build_operating_tes_table_context('vsego', 'toplivo', start_year='2025', end_year='2030', rounding_digits='1', coefficient_rounding_digits='0', view_year='2025')
    assert context['view_year'] == 2025
    rows = {row['key']: row for row in context['rows']}
    fields = set(FIELDS_JSON)
    assert fields <= (set(rows) | {'e', 'q'}), fields - (set(rows) | {'e', 'q'})
    assert {col['territory_slug'] for col in context['value_columns']} == set(expected)
    checked = 0
    for column in context['value_columns']:
        slug = column['territory_slug']
        for key, row in rows.items():
            field = {'ee_generation': 'e', 'heat_output': 'q'}.get(key, key)
            if field not in fields:
                continue
            value = Decimal(expected[slug].get(field, '0'))
            if field == 'e':
                value /= 1000
            raw = row['col_values_raw'][column['slug']]
            assert (Decimal(raw) if raw else Decimal(0)) == value, (slug, key, raw, str(value))
            checked += 1
    result = {
        'database_version_id': 37, 'snapshot_id': 66, 'year': 2025,
        'scope': 'operating', 'exact_payload_match': True,
        'stored_numeric_values': sum(map(len, expected.values())),
        'page_cells_verified': checked, 'territories': len(expected),
        'total_fuel_display': rows['b']['col_values']['vsego:2025'],
        'total_generation_display': rows['ee_generation']['col_values']['vsego:2025'],
        'total_heat_display': rows['heat_output']['col_values']['vsego:2025'],
        'gtt_display': rows['gtt']['col_values']['vsego:2025'],
        'gtt_stored': expected['vsego']['gtt'],
    }
    print('VERIFICATION_JSON:' + json.dumps(result, ensure_ascii=True))
    db.session.rollback()
'''.replace('EXPECTED_JSON', repr(json.dumps(expected, ensure_ascii=True))).replace('FIELDS_JSON', repr([row[1] for row in json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))['rows']]))

for target in ['server', 'local']:
    root = '/opt/generation-app/app' if target == 'server' else str(ROOT)
    env = "load_dotenv('/etc/generation-app/app.env')" if target == 'server' else f'load_dotenv({str(ROOT / ".env")!r})'
    code = script.replace('ROOT_PATH', repr(root)).replace('LOAD_ENV', env)
    if target == 'server':
        output = ssh('sudo -n -u generation-app /opt/generation-app/venv/bin/python -', code.encode('utf-8')).decode('utf-8')
    else:
        run = subprocess.run([sys.executable, '-X', 'utf8', '-'], input=code.encode('utf-8'), capture_output=True, cwd=ROOT)
        (OUT / 'local_verify_stderr.txt').write_bytes(run.stderr)
        output = run.stdout.decode('utf-8')
        if run.returncode:
            print(run.stderr.decode('utf-8'))
        run.check_returncode()
    (OUT / f'{target}_verify_output.txt').write_text(output, encoding='utf-8')
    line = next(line.removeprefix('VERIFICATION_JSON:') for line in output.splitlines() if line.startswith('VERIFICATION_JSON:'))
    result = json.loads(line)
    (OUT / f'{target}_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(target, json.dumps(result, ensure_ascii=False))
