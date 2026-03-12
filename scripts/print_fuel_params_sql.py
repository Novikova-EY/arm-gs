#!/usr/bin/env python3
"""Вывод полного SQL-запроса для stations_equipment_group_fuel_params."""
import sys
sys.path.insert(0, ".")

from app import create_app
app = create_app()
with app.app_context():
    from sqlalchemy import or_, and_
    from app.extensions import db
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
    )

    _start = get_filter_start_year()
    _end = get_filter_end_year()
    current_version_id = get_current_db_version_id()

    version_match = or_(
        and_(
            EquipmentGroupFuelParam.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupFuelParam.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupFuelParam.year_number >= _start,
        EquipmentGroupFuelParam.year_number <= _end,
        version_match,
    )

    base_query = (
        db.session.query(EquipmentGroup, EquipmentGroupFuelParam)
        .outerjoin(EquipmentGroupFuelParam, join_cond)
    )

    if current_version_id is not None:
        base_query = base_query.filter(
            EquipmentGroup.database_version_id == current_version_id
        )
    else:
        base_query = base_query.filter(
            EquipmentGroup.database_version_id.is_(None)
        )

    base_query = base_query.order_by(
        EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id
    )

    compiled = base_query.statement.compile(
        db.engine, compile_kw={"literal_binds": True}
    )
    print("-- Значения: _start=%s, _end=%s, current_version_id=%s" % (_start, _end, current_version_id))
    print(str(compiled))
