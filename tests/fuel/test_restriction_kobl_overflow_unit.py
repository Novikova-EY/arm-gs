# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.distribution.distribution_stage_services import (
    KOBL_ABS_MAX,
    clamp_restriction_kobl,
    oes_ved_restriction_filter_text,
    restriction_subject_targets_unmet,
)


def test_oes_ved_restriction_filter_matches_access_ecur_universe():
    assert oes_ved_restriction_filter_text(1) == "(oes=1) and (ved>0)"


def test_clamp_restriction_kobl_caps_overflow():
    exploded = Decimal("5482189818539061938384.639386")
    assert clamp_restriction_kobl(exploded) == KOBL_ABS_MAX
    assert clamp_restriction_kobl(-exploded) == -KOBL_ABS_MAX
    assert KOBL_ABS_MAX == Decimal("100")


def test_clamp_restriction_kobl_keeps_access_scale():
    assert clamp_restriction_kobl(Decimal("0.961816729100354")) == Decimal("0.961816729100354")
    assert clamp_restriction_kobl(Decimal("1.03946070540255")) == Decimal("1.03946070540255")


def test_restriction_subject_unmet_ignores_prochie():
    rows = [
        SimpleNamespace(obl=1, emin=6313, emax=6313, ecur=6313),
        SimpleNamespace(obl=101, emin=None, emax=None, ecur=40000),
    ]
    assert restriction_subject_targets_unmet(rows, 1) is False


def test_restriction_subject_unmet_when_below_emin():
    rows = [
        SimpleNamespace(obl=4, emin=10053, emax=10053, ecur=9857),
        SimpleNamespace(obl=101, emin=None, emax=None, ecur=40000),
    ]
    assert restriction_subject_targets_unmet(rows, 1) is True
    rows[0].ecur = Decimal("10053")
    assert restriction_subject_targets_unmet(rows, 1) is False


def test_all_versions_ecur_would_explode_kobl():
    """ecur со всех версий БД (~8×), ecurdis только текущая → множитель ~−8 за проход."""
    emax = Decimal("6313")
    ecur = Decimal("56019.98428036")
    ecurdis = Decimal("5515.98341636")
    factor = (emax - ecur + ecurdis) / ecurdis
    assert factor < Decimal("-7")
    kobl = Decimal("0.99")
    for _ in range(14):
        kobl = kobl * factor
    assert abs(kobl) > Decimal("10") ** 12
    assert abs(clamp_restriction_kobl(kobl)) == KOBL_ABS_MAX
