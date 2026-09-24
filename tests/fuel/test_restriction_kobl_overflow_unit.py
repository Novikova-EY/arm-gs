# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.distribution.distribution_stage_services import (
    KOBL_ABS_MAX,
    DistributionStageService,
    clamp_restriction_kobl,
    fuel_param_obl_code,
    oes_ved_restriction_filter_text,
    restriction_subject_targets_unmet,
    restriction_unmet_subjects_hfix_locked,
)


def test_oes_ved_restriction_filter_matches_access_ecur_universe():
    assert oes_ved_restriction_filter_text(1) == "(oes=1) and (ved>0)"


def test_clamp_restriction_kobl_caps_overflow():
    exploded = Decimal("5482189818539061938384.639386")
    assert clamp_restriction_kobl(exploded) == KOBL_ABS_MAX
    assert clamp_restriction_kobl(-exploded) == -KOBL_ABS_MAX
    assert KOBL_ABS_MAX == Decimal("20000")


def test_seed_restriction_kobl_keeps_access_form_values():
    seed = DistributionStageService._seed_restriction_kobl
    assert seed(Decimal("0.980949000537405")) == Decimal("0.980949000537405")
    assert seed(Decimal("1.08598918284594")) == Decimal("1.08598918284594")


def test_seed_restriction_kobl_keeps_large_access_values():
    seed = DistributionStageService._seed_restriction_kobl
    assert seed(Decimal("3920.29334154737")) == Decimal("3920.29334154737")
    assert seed(Decimal("19654.8844481274")) == Decimal("19654.8844481274")
    assert seed(Decimal("0")) == Decimal("1")
    assert seed(None) == Decimal("1")


def test_restriction_loop_starts_from_kobl_one():
    """Без галочки Access пишет kobl=1; с галочкой таблицу не затираем."""
    rows = [
        SimpleNamespace(obl=1, kobl=Decimal("0.9916643031078396")),
        SimpleNamespace(obl=4, kobl=Decimal("1.0376784943153235")),
        SimpleNamespace(obl=101, kobl=Decimal("0.9946334567708093")),
    ]
    DistributionStageService._reset_closed_form_restriction_kobl(rows)
    assert all(r.kobl == Decimal("1") for r in rows)


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


def test_fuel_param_obl_code_from_working_row():
    assert fuel_param_obl_code(SimpleNamespace(obl="53")) == 53
    assert fuel_param_obl_code(SimpleNamespace(obl=79)) == 79
    assert fuel_param_obl_code(SimpleNamespace(obl=None)) is None
    assert fuel_param_obl_code(SimpleNamespace(obl="")) is None
    assert fuel_param_obl_code(None) is None


def test_kobl_for_group_uses_fuel_param_obl():
    kobl_by_obl = {53: Decimal("1.2"), 105: Decimal("0.9")}
    fn = DistributionStageService._kobl_for_group
    assert fn(obl=53, oes_code=5, kobl_by_obl=kobl_by_obl) == Decimal("1.2")
    assert fn(obl=None, oes_code=5, kobl_by_obl=kobl_by_obl) == Decimal("0.9")
    assert fn(obl=99, oes_code=5, kobl_by_obl=kobl_by_obl) == Decimal("0.9")


def test_restriction_hfix_locked_when_yakutia_all_fixed():
    rows = [
        SimpleNamespace(obl=79, emin=2885, emax=2890, ecur=1662),
        SimpleNamespace(obl=107, emin=None, emax=None, ecur=40000),
    ]
    by_key = {
        (1, 2026): SimpleNamespace(ved=1, obl="79", hfix=1, nust=80, h=2000),
        (2, 2026): SimpleNamespace(ved=2, obl="79", hfix=1, nust=12, h=4500),
        (3, 2026): SimpleNamespace(ved=1, obl="64", hfix=0, nust=100, h=5000),
    }
    assert restriction_unmet_subjects_hfix_locked(
        rows, 7, by_key=by_key, group_ids=[1, 2, 3], cyear=2026
    )


def test_restriction_locked_when_unfixed_has_zero_base_hours():
    """Восток 2027: 773 без hfix, Hбаз=0 → kobl не в формуле часов."""
    rows = [
        SimpleNamespace(obl=79, emin=2910, emax=2930, ecur=1436),
        SimpleNamespace(obl=107, emin=None, emax=None, ecur=36874),
    ]
    by_key = {
        (773, 2027): SimpleNamespace(ved=2, obl="79", hfix=None, nust=160, h=6500),
        (773, 2024): SimpleNamespace(ved=2, obl="79", hfix=None, nust=0, h=0),
        (772, 2027): SimpleNamespace(ved=2, obl="79", hfix=1, nust=12, h=4500),
        (766, 2027): SimpleNamespace(ved=1, obl="79", hfix=None, nust=0, h=7000),
        (766, 2024): SimpleNamespace(ved=1, obl="79", hfix=None, nust=170, h=6320),
    }
    assert restriction_unmet_subjects_hfix_locked(
        rows, 7, by_key=by_key, group_ids=[773, 772, 766], cyear=2027, byear=2024
    )


def test_restriction_hfix_not_locked_when_movable_station():
    rows = [
        SimpleNamespace(obl=53, emin=10000, emax=None, ecur=8000),
        SimpleNamespace(obl=105, emin=None, emax=None, ecur=40000),
    ]
    by_key = {
        (1, 2026): SimpleNamespace(ved=4, obl="53", hfix=1),
        (2, 2026): SimpleNamespace(ved=4, obl="53", hfix=0, nust=100),
    }
    assert not restriction_unmet_subjects_hfix_locked(
        rows, 5, by_key=by_key, group_ids=[1, 2], cyear=2026
    )


def test_restriction_hfix_not_locked_when_targets_met():
    rows = [
        SimpleNamespace(obl=79, emin=2885, emax=2890, ecur=2885),
        SimpleNamespace(obl=107, emin=None, emax=None, ecur=40000),
    ]
    by_key = {(1, 2026): SimpleNamespace(ved=1, obl="79", hfix=1)}
    assert not restriction_unmet_subjects_hfix_locked(
        rows, 7, by_key=by_key, group_ids=[1], cyear=2026
    )
