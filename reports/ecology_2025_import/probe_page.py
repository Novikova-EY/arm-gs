import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['ENABLE_SCHEDULED_BACKUPS'] = 'False'
from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.ecology.services.operating_tes_fuel_input_services import get_fuel_module_consumption_row_specs

app = create_app()
with app.test_request_context('/ecology/operating_tes/vsego/toplivo/?view_year=2025'):
    db.session.execute(text('SET TRANSACTION READ ONLY'))
    print('ROWS_JSON:' + json.dumps(get_fuel_module_consumption_row_specs(), ensure_ascii=True))
    db.session.rollback()
