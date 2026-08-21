# -*- coding: utf-8 -*-
"""Сводный PROCH с 2018: tvproch + szh_gaz + inoe (как Access Станции)."""
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_services import (
    EquipmentGroupFuelCalculationService,
)


def _extra(**kwargs):
    base = {
        "tvproch": Decimal("0"),
        "szh_gaz": Decimal("0"),
        "inoe": Decimal("0"),
        "koks_g": Decimal("0"),
        "prochgaz": Decimal("0"),
        "domen_g": Decimal("0"),
        "intin": None,
        "vork": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_proch_is_tvproch_plus_inoe_from_2018():
    fp = SimpleNamespace(proch=Decimal("0"), ugol=None, year_number=2026)
    extra = _extra(tvproch=Decimal("154.88"), inoe=Decimal("499.09"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"tvproch", "inoe"},
    )
    assert fp.proch == Decimal("154.88") + Decimal("499.09")


def test_inoe_residual_alone_rolls_into_proch():
    fp = SimpleNamespace(proch=Decimal("0"), ugol=None, year_number=2026)
    extra = _extra(inoe=Decimal("154.22"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"inoe"},
    )
    assert fp.proch == Decimal("154.22")


def test_prochgaz_goes_to_isk_gaz_not_proch():
    fp = SimpleNamespace(
        proch=Decimal("0"),
        isk_gaz=Decimal("0"),
        ugol=None,
        year_number=2026,
    )
    extra = _extra(prochgaz=Decimal("19.55"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"prochgaz"},
    )
    assert fp.isk_gaz == Decimal("19.55")
    assert fp.proch == Decimal("0")


def test_legacy_year_keeps_old_proch_basket():
    fp = SimpleNamespace(proch=Decimal("0"), ugol=None, year_number=2016)
    extra = _extra(tvproch=Decimal("10"), prochgaz=Decimal("3"), koks_g=Decimal("2"))
    EquipmentGroupFuelCalculationService()._aggregate_main_fuels(
        fuel_param=fp,
        extra_param=extra,
        used_names={"tvproch", "prochgaz", "koks_g"},
    )
    assert fp.proch == Decimal("15")
