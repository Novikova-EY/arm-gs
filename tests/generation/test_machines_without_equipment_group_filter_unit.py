# -*- coding: utf-8 -*-
"""Проверка «агрегаты без группы»: топливная группа на карточке, не тип."""

from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from app.generation.models.machine.machine_model import Machine
from app.generation.services.station_services.filters_services import (
    build_machines_without_equipment_group_filter,
)


def test_without_equipment_group_filter_uses_machine_fuel_param():
    """Ловит агрегаты с типом, но без группы станции в селекте карточки."""
    with patch(
        "app.generation.services.station_services.filters_services.get_current_db_version_id",
        return_value=46,
    ):
        cond = build_machines_without_equipment_group_filter(Machine)

    sql = str(cond.compile(dialect=postgresql.dialect())).lower()
    assert "gs_fue_machine_fuel_param" in sql
    assert "gs_fue_equipment_groups" in sql
    assert "equipment_group_id" in sql
    assert "exists" in sql
    assert "gs_fue_equipment_group_type_stations" in sql
    assert "gs_fue_equipment_group_sets" in sql
    assert "gs_sys_equipment_groups" not in sql
    assert "fue_eg_st_other" not in sql
