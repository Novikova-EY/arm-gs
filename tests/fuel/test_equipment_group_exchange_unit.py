# -*- coding: utf-8 -*-
"""Юнит-тесты JSON-набора equipment_group_params."""
from types import SimpleNamespace

from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.api.services import equipment_group_exchange_services as svc


def test_build_equipment_group_param_row_type_and_power():
    param = SimpleNamespace(nust=120, nr=110, h=4500, snk=5.2)
    row = svc.build_equipment_group_param_row(
        external_code="eg-1",
        station_external_code="st-1",
        name="КЭС-1",
        group_type="КЭС",
        technology_type="паросиловая",
        technology_availability="действующая",
        numb=1120,
        year=2032,
        param=param,
    )
    assert row[svc.KEY_GROUP_CODE] == "eg-1"
    assert row[svc.KEY_STATION_CODE] == "st-1"
    assert row[svc.KEY_GROUP_TYPE] == "КЭС"
    assert row[svc.KEY_TECHNOLOGY_TYPE] == "паросиловая"
    assert row[svc.KEY_TECHNOLOGY_AVAILABILITY] == "действующая"
    assert row[svc.KEY_GROUP_NUMB] == 1120
    assert row[svc.KEY_YEAR] == 2032
    assert row[EquipmentGroupFuelParam.NUST_COLUMN_LABEL] == 120
    assert row[EquipmentGroupFuelParam.NR_COLUMN_LABEL] == 110


def test_build_equipment_group_params_rows_group_times_year():
    group_type = SimpleNamespace(
        name="КЭС",
        technology_type=SimpleNamespace(name="паросиловая"),
        technology_availability=SimpleNamespace(name="действующая"),
    )
    group = SimpleNamespace(
        id=4,
        external_code="eg-1",
        name="КЭС-1",
        numb=10,
        equipment_group_links_v2=[
            SimpleNamespace(
                equipment_group_set_station=SimpleNamespace(
                    station=SimpleNamespace(external_code="st-1"),
                    equipment_group_type=group_type,
                )
            )
        ],
    )
    param = SimpleNamespace(nust=80)
    rows = svc.build_equipment_group_params_rows(
        [group],
        [2032, 2033],
        {(4, 2032): param},
    )
    assert len(rows) == 1
    assert rows[0][svc.KEY_GROUP_TYPE] == "КЭС"
    assert rows[0][EquipmentGroupFuelParam.NUST_COLUMN_LABEL] == 80
    assert rows[0][svc.KEY_YEAR] == 2032
    assert rows[0][svc.KEY_STATION_CODE] == "st-1"
