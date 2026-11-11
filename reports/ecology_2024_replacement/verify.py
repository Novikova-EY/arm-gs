import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
expected = json.loads((OUT / "payload.json").read_text(encoding="utf-8"))
script = '''import json
import os
import sys
from decimal import Decimal
from dotenv import load_dotenv
load_dotenv('/etc/generation-app/app.env')
os.environ['ENABLE_SCHEDULED_BACKUPS'] = 'False'
os.chdir('/opt/generation-app/app')
sys.path.insert(0, os.getcwd())
from app import create_app
app = create_app()
from sqlalchemy import text
from app.extensions import db
from app.common.services.database_version_filter import get_current_db_version_id
from app.ecology.models.fuel_exchange_model import EcologyFuelSnapshot
from app.ecology.services.fuel_exchange_services import load_accepted_fuel_inputs
from app.ecology.services.operating_tes_page_services import build_operating_tes_table_context
expected = json.loads(EXPECTED_JSON)
with app.test_request_context('/ecology/operating_tes/vsego/toplivo/?start_year=2024&end_year=2031&rounding_digits=1&coefficient_rounding_digits=0&view_year=2024'):
    db.session.execute(text('SET TRANSACTION READ ONLY'))
    assert get_current_db_version_id() == 37
    snapshot = EcologyFuelSnapshot.query.filter_by(id=65, database_version_id=37, year_number=2024, scope='operating').one()
    assert snapshot.payload == expected
    accepted = load_accepted_fuel_inputs([2024])[2024]
    assert accepted == {slug: {field: Decimal(value) for field, value in bucket.items()} for slug, bucket in expected.items()}
    context = build_operating_tes_table_context('vsego', 'toplivo', start_year='2024', end_year='2031', rounding_digits='1', coefficient_rounding_digits='0', view_year='2024')
    assert context['view_year'] == 2024
    rows = {row['key']: row for row in context['rows']}
    assert set().union(*(set(bucket) for bucket in expected.values())) <= (set(rows) | {'e', 'q'})
    checked = 0
    for column in context['value_columns']:
        slug = column['territory_slug']
        bucket = expected.get(slug, {})
        for key, row in rows.items():
            field = {'ee_generation': 'e', 'heat_output': 'q'}.get(key, key)
            value = Decimal(bucket.get(field, '0'))
            if field == 'e':
                value /= 1000
            raw = row['col_values_raw'][column['slug']]
            assert (Decimal(raw) if raw else Decimal(0)) == value, (slug, key, raw, value)
            if slug not in expected:
                assert raw == '', (slug, key, raw)
            checked += 1
    result = {
        'database_version_id': 37, 'snapshot_id': 65, 'year': 2024,
        'scope': 'operating', 'exact_payload_match': True,
        'stored_numeric_values': sum(map(len, expected.values())),
        'page_cells_verified': checked,
        'other_territories_empty': True,
        'total_fuel_display': rows['b']['col_values']['vsego:2024'],
        'total_generation_display': rows['ee_generation']['col_values']['vsego:2024'],
    }
    print('VERIFICATION_JSON:' + json.dumps(result, ensure_ascii=True))
    db.session.rollback()
'''.replace('EXPECTED_JSON', repr(json.dumps(expected, ensure_ascii=True)))
result = subprocess.run(
    ['ssh', '-o', 'BatchMode=yes', 'novikova-eyu@10.31.205.27',
     'sudo -n -u generation-app /opt/generation-app/venv/bin/python -'],
    input=script.encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
(OUT / 'verify_output.txt').write_bytes(result.stdout + b'\n' + result.stderr)
print(result.stderr.decode('utf-8'), end='')
print(result.stdout.decode('utf-8'), end='')
result.check_returncode()
verification = next(line.removeprefix('VERIFICATION_JSON:') for line in result.stdout.decode('utf-8').splitlines() if line.startswith('VERIFICATION_JSON:'))
(OUT / 'verification.json').write_text(json.dumps(json.loads(verification), ensure_ascii=False, indent=2), encoding='utf-8')
