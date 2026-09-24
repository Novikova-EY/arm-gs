# -*- coding: utf-8 -*-
"""Access Кнопка5: kn пересчитывается только при cnustn > 0."""
from types import SimpleNamespace
from decimal import Decimal

from app.fuel.services.calculation.coefficient.fuel_coefficient_calculation_services import (
    _access_kn_from_new_capacity,
    _access_kn_star_from_form,
)


def test_weighted_kn_when_new_capacity():
    kn = _access_kn_from_new_capacity(
        cnustn=Decimal("100"),
        cnustnps=Decimal("40"),
        cnustngt=Decimal("50"),
        cnustnpg=Decimal("10"),
        knps=Decimal("1.0"),
        kngt=Decimal("1.2"),
        knpg=Decimal("1.5"),
        form_kn=Decimal("9"),
    )
    assert kn == Decimal("1.15")


def test_south_2026_keeps_form_kn_when_no_new_capacity():
    """Юг 2026: новых нет, Access не пишет kn=0, оставляет kn с формы (1.27)."""
    kn = _access_kn_from_new_capacity(
        cnustn=Decimal("0"),
        cnustnps=Decimal("0"),
        cnustngt=Decimal("0"),
        cnustnpg=Decimal("0"),
        knps=Decimal("1.03494432884272"),
        kngt=Decimal("1.23743343665977"),
        knpg=Decimal("1.55241649326408"),
        form_kn=Decimal("1.27008444873444"),
    )
    assert kn == Decimal("1.27008444873444")


def test_zero_form_kn_stays_zero_when_no_new_capacity():
    kn = _access_kn_from_new_capacity(
        cnustn=Decimal("0"),
        cnustnps=Decimal("0"),
        cnustngt=Decimal("0"),
        cnustnpg=Decimal("0"),
        knps=Decimal("1"),
        kngt=Decimal("1"),
        knpg=Decimal("1"),
        form_kn=Decimal("0"),
    )
    assert kn == Decimal("0")


def test_coeff_button_keeps_form_knps_not_hnps_over_ch():
    """Кнопка5 не делает knps=hnps/ch (это BeforeUpdate поля hnps)."""
    row = SimpleNamespace(
        knps=Decimal("1.19390109569214"),
        kngt=Decimal("1.21255580031233"),
        knpg=Decimal("1.11928227721138"),
        hnps=Decimal("6400"),
        hngt=Decimal("6500"),
        hnpg=Decimal("6000"),
    )
    knps, kngt, knpg = _access_kn_star_from_form(row)
    assert knps == Decimal("1.19390109569214")
    assert kngt == Decimal("1.21255580031233")
    assert knpg == Decimal("1.11928227721138")
    assert knps != Decimal("6400") / Decimal("5287.778740")
