#!/bin/bash
set -euo pipefail

APP_DIR=/opt/generation-app/app
VENV=/opt/generation-app/venv
REMOTE_SRC=/tmp

sudo cp -f "$REMOTE_SRC/r7s8t9u0v1w2.py" \
  "$APP_DIR/migrations/versions/r7s8t9u0v1w2_add_pvc_to_energy_system_type_demand_params.py"
sudo cp -f "$REMOTE_SRC/s8t9u0v1w2x3.py" \
  "$APP_DIR/migrations/versions/s8t9u0v1w2x3_drop_legacy_ees_russia_demand_unique_indexes.py"
sudo cp -f "$REMOTE_SRC/migrate_pd_ees.py" \
  "$APP_DIR/scripts/migrate_misplaced_ees_unified_pd_demand_params.py"
sudo chown generation-app:generation-app \
  "$APP_DIR/migrations/versions/r7s8t9u0v1w2_add_pvc_to_energy_system_type_demand_params.py" \
  "$APP_DIR/migrations/versions/s8t9u0v1w2x3_drop_legacy_ees_russia_demand_unique_indexes.py" \
  "$APP_DIR/scripts/migrate_misplaced_ees_unified_pd_demand_params.py"

# На сервере head = 7c7536d495c6 (merge), q6r7s8t9u0v1 уже в истории.
sudo sed -i 's/down_revision = "q6r7s8t9u0v1"/down_revision = "7c7536d495c6"/' \
  "$APP_DIR/migrations/versions/r7s8t9u0v1w2_add_pvc_to_energy_system_type_demand_params.py"

sudo -u generation-app bash -c "
set -a
. /etc/generation-app/app.env
set +a
cd $APP_DIR
source $VENV/bin/activate
export FLASK_APP=run.py FLASK_ENV=production
flask db upgrade
python scripts/migrate_misplaced_ees_unified_pd_demand_params.py
python scripts/migrate_misplaced_ees_unified_pd_demand_params.py --apply --yes
"

echo "--- counts after migration ---"
sudo -u generation-app bash -c "
set -a
. /etc/generation-app/app.env
set +a
cd $APP_DIR
source $VENV/bin/activate
export FLASK_APP=run.py FLASK_ENV=production
python - <<'PY'
from app import create_app
from app.extensions import db
from sqlalchemy import text
app = create_app()
with app.app_context():
    for t in (
        'gs_pd_ees_russia_demand_params',
        'gs_pd_ees_demand_params',
        'gs_pd_energy_system_type_demand_params',
    ):
        c = db.session.execute(text(f'SELECT COUNT(*) FROM gs_pd.{t}')).scalar()
        print(t, c)
PY
"

sudo systemctl restart generation-app
echo "PD EES/EEs data migration complete."
