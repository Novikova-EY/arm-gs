# -*- coding: utf-8 -*-
"""Access Р5.1–Р5.3: потолок часов, в том числе при Hбаз > 7000."""
from decimal import Decimal

from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
)


def _c(**kwargs):
    return DistributionStageService._clamp_hours(**kwargs)


def test_hb_above_7000_still_caps_at_7000():
    """СЗ ТЭЦ: Hбаз=7186, формула гонит выше — Access Else ставит 7000, не оставляет 7186."""
    hb = Decimal("7186.09")
    hours = hb * Decimal("1.03")
    assert hours > hb
    assert _c(hours=hours, hb=hb, hd=Decimal("3900")) == Decimal("7000")


def test_hb_above_7000_equal_hours_caps_at_7000():
    hb = Decimal("7406.5")
    assert _c(hours=hb, hb=hb, hd=Decimal("3900")) == Decimal("7000")


def test_hours_below_7000_unchanged():
    assert _c(
        hours=Decimal("5000"),
        hb=Decimal("4800"),
        hd=Decimal("3900"),
    ) == Decimal("5000")


def test_band_6500_7000_caps_plus_5_percent():
    """Живая Кнопка27: hb > 6500 (не ≥). hb=6500 в полосу не входит."""
    hb = Decimal("6600")
    hours = Decimal("7000")
    got = _c(hours=hours, hb=hb, hd=Decimal("3900"))
    assert got == hb * Decimal("1.05")
    assert got < Decimal("7000")


def test_hb_exactly_6500_does_not_use_plus5_band():
    hb = Decimal("6500")
    hours = Decimal("7000")
    assert _c(hours=hours, hb=hb, hd=Decimal("3900")) == Decimal("7000")


def test_new_capacity_gt_includes_obor_24_and_89():
    """Кнопка27 СиПР: 20|90|24|89 → ch·kngt (Коэфф Кнопка5 по-прежнему 20|90)."""
    ch = Decimal("5000")
    knps, kngt, knpg = Decimal("0.8"), Decimal("0.5"), Decimal("0.3")
    h = DistributionStageService._new_capacity_hours
    for obor in (20, 90, 24, 89):
        assert h(obor=obor, ch=ch, knps=knps, kngt=kngt, knpg=knpg) == ch * kngt
    assert h(obor=21, ch=ch, knps=knps, kngt=kngt, knpg=knpg) == ch * knpg
    assert h(obor=10, ch=ch, knps=knps, kngt=kngt, knpg=knpg) == ch * knps


def test_null_bk_uses_else_branch_not_kplus():
    """Access: Null < 350 не True → Else, z(Bk)=0 → kmin+(kplus-kmin)*2.75."""
    kmin = Decimal("1")
    kplus = Decimal("1.1")
    null_k = DistributionStageService._koptim_from_bk(bk=None, kmin=kmin, kplus=kplus)
    zero_k = DistributionStageService._koptim_from_bk(bk=Decimal("0"), kmin=kmin, kplus=kplus)
    assert zero_k == kplus
    assert null_k == kmin + (kplus - kmin) * Decimal("2.75")


def test_null_hfix_skips_capacity_growth():
    from types import SimpleNamespace
    from app.fuel.services.calculation.distribution.distribution_stage_services import (
        _access_allows_capacity_growth,
    )

    assert _access_allows_capacity_growth(SimpleNamespace(hfix=None)) is False
    assert _access_allows_capacity_growth(SimpleNamespace(hfix=0)) is True
    assert _access_allows_capacity_growth(SimpleNamespace(hfix=1)) is False
