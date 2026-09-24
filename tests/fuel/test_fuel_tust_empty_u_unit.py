# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_services import (
    EquipmentGroupFuelCalculationService,
)


def test_boiler_tust_from_q_turt_when_u_is_empty():
    """Котельная 3607: y/bk нет, TUST = Q·TURT/1000, B = TUST."""
    svc = EquipmentGroupFuelCalculationService(session=None)
    fuel_param = SimpleNamespace(
        qotr=None,
        e=Decimal("0"),
        q=Decimal("3188.675"),
        turt=Decimal("151.35"),
        nust=None,
        ved=3,
        equipment_group=None,
        ewtp=None,
    )
    consumption = SimpleNamespace(
        y=None, snk=None, sntp=None, bk=None, btp=None,
        snbas=None, ksn=None, bbas=None, kh=None,
    )
    svc._calculate_energy_part(fuel_param=fuel_param, consumption=consumption)
    expected = Decimal("3188.675") * Decimal("151.35") / Decimal("1000")
    assert fuel_param.tust == expected
    assert fuel_param.b == expected
    assert fuel_param.eust == Decimal("0")


def test_boiler_tust_when_consumption_row_missing():
    """Нет строки U в [byear, cyear] — как пустая U, не Skip: TUST = Q·TURT/1000."""
    svc = EquipmentGroupFuelCalculationService(session=None)
    fuel_param = SimpleNamespace(
        qotr=None,
        e=Decimal("0"),
        q=Decimal("1098.2"),
        turt=Decimal("168.8"),
        nust=None,
        ved=2,
        equipment_group=None,
        ewtp=None,
    )
    svc._calculate_energy_part(fuel_param=fuel_param, consumption=None)
    expected = Decimal("1098.2") * Decimal("168.8") / Decimal("1000")
    assert fuel_param.tust == expected
    assert fuel_param.b == expected
    assert fuel_param.eust == Decimal("0")
