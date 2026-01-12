"""
Восстановление связей РЭС ↔ Субъекты РФ (M2M) из данных станций.

Когда чекбоксы в форме не отправляются, связи могли быть обнулены.
Этот скрипт пересобирает недостающие пары (regional_district_id, regional_energy_system_id)
по данным Generation.Station (id_regional_district + id_regional_energy_system) для выбранной версии БД.

Запуск (Windows):
  c:/arm_gs/.venv/Scripts/python.exe scripts/rebuild_res_rd_links_from_stations.py --dry-run
  c:/arm_gs/.venv/Scripts/python.exe scripts/rebuild_res_rd_links_from_stations.py
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-id", type=int, default=None, help="database_version_id; по умолчанию берется активная версия")
    parser.add_argument("--dry-run", action="store_true", help="только показать статистику без записи в БД")
    args = parser.parse_args()

    from app import create_app
    from app.extensions import db
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.generation.models.station.station_model import Station
    from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
        regional_district_regional_energy_system as assoc,
    )

    app = create_app()
    with app.app_context():
        vid = args.version_id or get_current_db_version_id()
        if vid is None:
            raise SystemExit("Не удалось определить active database_version_id (is_active=True).")

        desired = set(
            db.session.query(Station.id_regional_district, Station.id_regional_energy_system)
            .filter(
                Station.database_version_id == vid,
                Station.id_regional_district.isnot(None),
                Station.id_regional_energy_system.isnot(None),
            )
            .distinct()
            .all()
        )

        existing = set(db.session.execute(db.select(assoc.c.regional_district_id, assoc.c.regional_energy_system_id)).all())
        missing = desired - existing

        print(f"db_version_id={vid} desired_pairs={len(desired)} existing_pairs={len(existing)} missing_pairs={len(missing)}")
        if args.dry_run:
            if missing:
                print("missing_sample:", list(missing)[:30])
            return 0

        if not missing:
            print("Нечего вставлять: недостающих связей не найдено.")
            return 0

        rows = [{"regional_district_id": rd, "regional_energy_system_id": res} for (rd, res) in missing]
        db.session.execute(assoc.insert(), rows)
        db.session.commit()
        print(f"Вставлено связей: {len(rows)}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())







