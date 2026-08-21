# -*- coding: utf-8 -*-
"""Unit-tests: Access «Сумма_частей» — Σ детей на родителя составной станции."""
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.equipment_groups.composite_parts_sum_recalc_services import (
    access_ratio_or_zero,
    build_parent_sums_from_children,
    sum_attr_from_records,
)


def test_sum_treats_null_as_zero():
    rows = [
        SimpleNamespace(e=10, q=None),
        SimpleNamespace(e=None, q=5),
    ]
    assert sum_attr_from_records(rows, "e") == Decimal("10")
    assert sum_attr_from_records(rows, "q") == Decimal("5")


def test_access_eurt_turt_formulas():
    # IIf(EOTP>0, EUST/EOTP*1000, 0)
    assert access_ratio_or_zero(Decimal("20"), Decimal("4")) == Decimal("5000")
    assert access_ratio_or_zero(Decimal("20"), Decimal("0")) == Decimal("0")
    assert access_ratio_or_zero(Decimal("20"), None) == Decimal("0")


def test_build_parent_sums_matches_access_query():
    child1 = SimpleNamespace(
        nust=10, nr=8, e=100, eotp=80, eust=16, q=4, tust=2, b=18, gaz=10, mazut=8
    )
    child2 = SimpleNamespace(
        nust=5, nr=4, e=50, eotp=40, eust=8, q=1, tust=1, b=9, gaz=5, mazut=4
    )
    sums = build_parent_sums_from_children(
        [child1, child2],
        attrs=("nust", "nr", "e", "eotp", "eust", "q", "tust", "b", "gaz", "mazut"),
    )
    assert sums["nust"] == Decimal("15")
    assert sums["e"] == Decimal("150")
    assert sums["eotp"] == Decimal("120")
    assert sums["eust"] == Decimal("24")
    assert sums["q"] == Decimal("5")
    assert sums["tust"] == Decimal("3")
    # EURT = 24/120*1000 = 200; TURT = 3/5*1000 = 600
    assert sums["eurt"] == Decimal("200")
    assert sums["turt"] == Decimal("600")


def test_eurt_zero_when_eotp_zero():
    child = SimpleNamespace(eust=10, eotp=0, tust=2, q=0)
    sums = build_parent_sums_from_children([child], attrs=("eust", "eotp", "tust", "q"))
    assert sums["eurt"] == Decimal("0")
    assert sums["turt"] == Decimal("0")
