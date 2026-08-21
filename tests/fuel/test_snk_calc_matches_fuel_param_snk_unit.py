# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    displayed_fuel_param_snk,
    displayed_fuel_param_snt,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_calc_services import (
    calc_snk_calc,
)


def test_snk_calc_uses_sn_ee_over_e_like_fuel_params_page():
    param = SimpleNamespace(sn_ee=Decimal("100"), e=Decimal("1000"), snk=Decimal("99"))
    expected = Decimal("10")
    assert displayed_fuel_param_snk(param) == expected
    assert calc_snk_calc(param) == expected


def test_snk_calc_falls_back_to_stored_fuel_param_snk():
    param = SimpleNamespace(sn_ee=None, e=Decimal("1000"), snk=Decimal("5.5"))
    assert displayed_fuel_param_snk(param) == Decimal("5.5")
    assert calc_snk_calc(param) == Decimal("5.5")


def test_snk_calc_empty_when_fuel_param_snk_empty():
    param = SimpleNamespace(sn_ee=None, e=None, snk=None)
    assert displayed_fuel_param_snk(param) is None
    assert calc_snk_calc(param) is None
    assert calc_snk_calc(None) is None


def test_displayed_snt_uses_sn_te_over_q():
    param = SimpleNamespace(sn_te=Decimal("50"), q=Decimal("1000"), sn_t=Decimal("99"))
    assert displayed_fuel_param_snt(param) == Decimal("50")


def test_displayed_snt_falls_back_to_stored():
    param = SimpleNamespace(sn_te=None, q=Decimal("1000"), sn_t=Decimal("51.4"))
    assert displayed_fuel_param_snt(param) == Decimal("51.4")
