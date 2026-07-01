# -*- coding: utf-8 -*-
"""Проверка прав редактирования карточки ДЭЗ для Топливо-админ/редактор."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.auth.models.user_model import User
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_access_services import (
    can_fuel_user_edit_decentralized_station_details,
    is_decentralized_zone_station,
)

STATION_ID = 38138
URL = (
    f"/generation/stations/station_details/{STATION_ID}"
    "?start_year=2024&end_year=2031&rounding_digits=1"
)


def main() -> int:
    app = create_app()
    failures: list[str] = []

    with app.app_context():
        user = User.query.filter_by(username="fuel-test").first()
        if not user:
            print("SKIP: user fuel-test not found")
            return 0

        station = Station.query.get(STATION_ID)
        if not station:
            print(f"FAIL: station {STATION_ID} not found")
            return 1

        print(f"User: {user.username}, roles: {[r.name_full for r in user.roles]}")
        print(f"Station: {station.name}, is_dz={is_decentralized_zone_station(station)}")
        print(f"can_edit_fuel_dz={can_fuel_user_edit_decentralized_station_details(user, station)}")

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        resp = client.get(URL)
        html = resp.get_data(as_text=True)
        print(f"GET status={resp.status_code}")

        if resp.status_code != 200:
            failures.append(f"expected 200, got {resp.status_code}")
        if "Режим просмотра" in html and "Режим редактирования" not in html:
            failures.append("unexpected read-only mode")
        if 'class="form-control station-name"' not in html:
            failures.append("name field not editable")
        if 'name="id_station_group"' not in html:
            failures.append("station group not editable")
        if 'name="id_condition_type"' not in html:
            failures.append("condition not editable")
        if 'name="station_sign"' not in html:
            failures.append("station_sign not editable")
        if 'name="note"' not in html:
            failures.append("note not editable")
        if 'name="id_regional_district"' not in html:
            failures.append("regional district not editable")
        if 'name="location"' not in html:
            failures.append("location not editable")
        if 'name="st_gen_' not in html:
            failures.append("energy generation table not editable")
        if 'name="id_station_type"' in html:
            failures.append("station type should be read-only for fuel dz user")

    if failures:
        print("FAILED:")
        for f in failures:
            print(" -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
