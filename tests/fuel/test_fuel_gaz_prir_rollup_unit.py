# -*- coding: utf-8 -*-
"""Сводный GAZ = gaz_prir + gazpp, как родитель в /refdata/fuel."""
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


def test_gaz_equals_gaz_prir_plus_gazpp():
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


def test_formtxt_gaz_not_added_on_top_of_children():
    """Старое gaz += gazpp не используем: родитель только сумма листьев."""
    fp = SimpleNamespace(gaz=Decimal("100"))
    extra = SimpleNamespace(gaz_prir=Decimal("40"), gazpp=Decimal("10"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"gaz", "gaz_prir", "gazpp"},
    )
    assert fp.gaz == Decimal("50")


def test_formtxt_gaz_token_kept_without_leaves():
    fp = SimpleNamespace(gaz=Decimal("100"))
    extra = SimpleNamespace(gaz_prir=Decimal("0"), gazpp=Decimal("0"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"gaz"},
    )
    assert fp.gaz == Decimal("100")
