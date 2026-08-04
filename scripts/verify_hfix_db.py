# -*- coding: utf-8 -*-
"""Verify hfix on target DB (set DB_HOST before run)."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"c:\arm_gs")

from sqlalchemy import func

from app import create_app
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.common.services.database_version_filter import get_current_db_version_id

print(f"DB_HOST={os.getenv('DB_HOST')} DB_NAME={os.getenv('DB_NAME')}")
app = create_app()
with app.app_context():
    vid = get_current_db_version_id()
    print("active version", vid)

    by_year = (
        EquipmentGroupFuelParam.query.with_entities(
            EquipmentGroupFuelParam.year_number,
            func.count(EquipmentGroupFuelParam.id),
        )
        .filter(EquipmentGroupFuelParam.hfix == 1)
        .group_by(EquipmentGroupFuelParam.year_number)
        .order_by(EquipmentGroupFuelParam.year_number)
        .all()
    )
    print("hfix=1 by year:", by_year)

    total_2026 = (
        EquipmentGroupFuelParam.query.filter(
            EquipmentGroupFuelParam.year_number == 2026
        ).count()
    )
    print("fuel_param rows year 2026 total:", total_2026)

    g = EquipmentGroup.query.filter_by(numb=875, database_version_id=vid).first()
    print("875 group", None if not g else (g.id, g.name))
    if g:
        for r in (
            EquipmentGroupFuelParam.query.filter_by(equipment_group_id=g.id)
            .filter(EquipmentGroupFuelParam.year_number.in_([2024, 2025, 2026]))
            .order_by(EquipmentGroupFuelParam.year_number)
        ):
            print(f"  y={r.year_number} hfix={r.hfix!r} h={r.h}")
