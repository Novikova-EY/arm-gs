# -*- coding: utf-8 -*-
"""Сводный GAZ = gaz + gaz_prir + gazpp, как в Access Станции.GAZ."""
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_services import (
    EquipmentGroupFuelCalculationService,
)


def test_gaz_prir_residual_rolls_into_gaz():
    fp = SimpleNamespace(gaz=Decimal("0"))
    extra = SimpleNamespace(gaz_prir=Decimal("1667.09"), gazpp=Decimal("0"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"gaz_prir"},
    )
    assert fp.gaz == Decimal("1667.09")


def test_gazpp_plus_gaz_prir_sum_to_gaz():
    fp = SimpleNamespace(gaz=Decimal("0"))
    extra = SimpleNamespace(
        gaz_prir=Decimal("587.18"),
        gazpp=Decimal("503.63"),
        intin=None,
        vork=None,
    )
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"gazpp", "gaz_prir"},
    )
    assert fp.gaz == Decimal("587.18") + Decimal("503.63")


def test_formtxt_gaz_token_not_double_counted_without_leaves():
    fp = SimpleNamespace(gaz=Decimal("100"))
    extra = SimpleNamespace(gaz_prir=Decimal("0"), gazpp=Decimal("0"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"gaz"},
    )
    assert fp.gaz == Decimal("100")
