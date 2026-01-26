# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from flask import session
from app.extensions import db
from sqlalchemy import func
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import add_version_service
from app.refdata.models.history.refdata_entity_model import RefdataEntity, RefdataEntityYear
from app.refdata.services.history.refdata_history_services import _get_current_year_number


def main() -> None:
    app = create_app()
    with app.app_context():
        with app.test_request_context():
            session["username"] = "autotest"
            active_version = DatabaseVersion.query.filter_by(is_active=True).first()
            if not active_version:
                raise SystemExit("Active version not found")
            max_version = db.session.query(func.max(DatabaseVersion.version_number)).scalar()
            if max_version and str(max_version).isdigit():
                new_version_number = str(int(max_version) + 1)
            else:
                new_version_number = f"AUTO{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            name = f"Autotest version {new_version_number}"
            data = [
                {
                    "version_number": new_version_number,
                    "name": name,
                    "description": "Autotest snapshots",
                    "refdata_source_version_id": active_version.id,
                }
            ]
            new_id = add_version_service(data, user="autotest")
            if isinstance(new_id, list):
                new_id = new_id[0]

            current_year_number = _get_current_year_number(new_id)

            entity_counts = (
                db.session.query(RefdataEntity.entity_type, func.count())
                .filter(RefdataEntity.database_version_id == new_id)
                .group_by(RefdataEntity.entity_type)
                .all()
            )
            year_query = (
                db.session.query(RefdataEntity.entity_type, func.count(RefdataEntityYear.id))
                .join(RefdataEntityYear, RefdataEntityYear.refdata_entity_id == RefdataEntity.id)
                .filter(
                    RefdataEntity.database_version_id == new_id,
                    RefdataEntityYear.database_version_id == new_id,
                )
            )
            if current_year_number is not None:
                year_query = year_query.filter(RefdataEntityYear.year == current_year_number)
            year_counts = year_query.group_by(RefdataEntity.entity_type).all()

            print("New version:", new_id, name)
            print("Current year:", current_year_number)
            print("RefdataEntity by type:")
            for item in entity_counts:
                print("  ", item[0], item[1])
            print("RefdataEntityYear by type:")
            for item in year_counts:
                print("  ", item[0], item[1])


if __name__ == "__main__":
    main()
