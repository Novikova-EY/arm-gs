# -*- coding: utf-8 -*-
"""
Перепривязка истории справочников после миграции ref_uuid.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from flask import session
from app.extensions import db
from app.refdata.models.history.refdata_entity_model import RefdataEntity, RefdataEntityYear
from app.refdata.models.years.year_model import Year
from app.refdata.services.history.refdata_history_services import (
    _get_current_year_number,
    snapshot_territories,
    snapshot_energy_systems,
    snapshot_station_machine_types,
    snapshot_fuels,
)


def _parse_years(value: str | None) -> list[int]:
    if not value:
        return []
    parts = [item.strip() for item in value.split(",") if item.strip()]
    years = []
    for part in parts:
        try:
            years.append(int(part))
        except ValueError:
            raise SystemExit(f"Invalid year value: {part!r}")
    return years


def _resolve_years(version_id: int, args: argparse.Namespace) -> list[int]:
    if args.all_years:
        return [
            y.number
            for y in Year.query.filter_by(database_version_id=version_id)
            .order_by(Year.number.asc())
            .all()
        ]
    if args.years:
        return _parse_years(args.years)
    current_year = _get_current_year_number(version_id)
    if current_year is None:
        raise SystemExit("Current year not found for version.")
    return [current_year]


def _delete_refdata_history(version_id: int) -> None:
    db.session.query(RefdataEntityYear).filter(
        RefdataEntityYear.database_version_id == version_id
    ).delete(synchronize_session=False)
    db.session.query(RefdataEntity).filter(
        RefdataEntity.database_version_id == version_id
    ).delete(synchronize_session=False)
    db.session.query(RefdataEntity).filter(
        ~RefdataEntity.history_entries.any()
    ).delete(synchronize_session=False)
    db.session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebind refdata history after ref_uuid migration")
    parser.add_argument("--version-id", type=int, required=True, help="Database version id")
    parser.add_argument(
        "--years",
        type=str,
        default="",
        help="Comma-separated years list (e.g. 2022,2023)",
    )
    parser.add_argument(
        "--all-years",
        action="store_true",
        help="Rebuild history for all years in the version",
    )
    parser.add_argument(
        "--no-delete",
        action="store_true",
        help="Do not delete existing history before rebuild",
    )
    parser.add_argument("--user", type=str, default="refdata_rebind", help="Username for audit")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        with app.test_request_context():
            session["username"] = args.user
            version_id = args.version_id
            years = _resolve_years(version_id, args)

            if not args.no_delete:
                _delete_refdata_history(version_id)

            for year in years:
                snapshot_territories(version_id, year, args.user, do_commit=False)
                snapshot_energy_systems(version_id, year, args.user, do_commit=False)
                snapshot_station_machine_types(version_id, year, args.user, do_commit=False)
                snapshot_fuels(version_id, year, args.user, do_commit=False)

            db.session.commit()
            print(f"Refdata history rebuilt for version {version_id} years={years}")


if __name__ == "__main__":
    main()
