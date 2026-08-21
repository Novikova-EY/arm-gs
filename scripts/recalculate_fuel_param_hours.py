# -*- coding: utf-8 -*-
"""
Пересчёт H = E/NUST·1000 в gs_fue_equipment_group_fuel_param.

Access calce: If NUST>0 Then H = E/NUST*1000.
Пишет только там, где есть e и nust>0. Уже совпадающие значения не трогает.

Запуск:
  python scripts/recalculate_fuel_param_hours.py
  python scripts/recalculate_fuel_param_hours.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

from app import create_app
from app.extensions import db
from config import SCHEMA_FUEL

TABLE = f"{SCHEMA_FUEL}.gs_fue_equipment_group_fuel_param"

ELIGIBLE_SQL = f"""
SELECT COUNT(*) FROM {TABLE}
WHERE nust IS NOT NULL AND nust > 0 AND e IS NOT NULL
"""

CHANGED_SQL = f"""
SELECT COUNT(*) FROM {TABLE}
WHERE nust IS NOT NULL AND nust > 0 AND e IS NOT NULL
  AND (h IS NULL OR abs(h - (e / nust * 1000)) > 0.0000001)
"""

UPDATE_SQL = f"""
UPDATE {TABLE}
SET h = round(e / nust * 1000, 16)
WHERE nust IS NOT NULL AND nust > 0 AND e IS NOT NULL
  AND (h IS NULL OR abs(h - (e / nust * 1000)) > 0.0000001)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Пересчёт H = E/NUST·1000")
    parser.add_argument("--dry-run", action="store_true", help="Только посчитать, не писать")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        eligible = int(db.session.execute(text(ELIGIBLE_SQL)).scalar() or 0)
        to_change = int(db.session.execute(text(CHANGED_SQL)).scalar() or 0)
        print(f"host={os.getenv('DB_HOST', '?')} db={os.getenv('DB_NAME', '?')}")
        print(f"eligible (nust>0 and e not null): {eligible}")
        print(f"need update: {to_change}")
        if args.dry_run:
            print("DRY RUN — no write")
            return 0
        result = db.session.execute(text(UPDATE_SQL))
        db.session.commit()
        print(f"updated: {result.rowcount}")
        left = int(db.session.execute(text(CHANGED_SQL)).scalar() or 0)
        print(f"still mismatch: {left}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
