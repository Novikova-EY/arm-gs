# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.specific_consumption_lookup import (
    pick_specific_consumption_access_seek,
    pick_specific_consumption_for_fuel,
    pick_specific_consumption_year_stepback,
    resolve_specific_consumption_for_fuel,
    specific_consumption_has_payload,
)


def test_kes_y_zero_with_bk_is_payload():
    row = SimpleNamespace(y=Decimal("0"), snk=None, sntp=Decimal("0"), bk=Decimal("325.5"), btp=None,
                          snbas=None, ksn=None, bbas=None, kh=None)
    assert specific_consumption_has_payload(row) is True


def test_all_zeros_is_empty():
    row = SimpleNamespace(y=Decimal("0"), snk=None, sntp=Decimal("0"), bk=None, btp=Decimal("0"),
                          snbas=None, ksn=None, bbas=None, kh=None)
    assert specific_consumption_has_payload(row) is False


def test_stepback_skips_empty_2026_to_2024():
    empty_2026 = SimpleNamespace(year_number=2026, y=None, snk=None, sntp=None, bk=None, btp=None,
                                 snbas=None, ksn=None, bbas=None, kh=None)
    zeros_2025 = SimpleNamespace(year_number=2025, y=Decimal("0"), snk=None, sntp=Decimal("0"),
                                 bk=None, btp=Decimal("0"), snbas=None, ksn=None, bbas=None, kh=None)
    filled_2024 = SimpleNamespace(year_number=2024, y=Decimal("1646.77"), snk=Decimal("4.1"),
                                  sntp=Decimal("0.92"), bk=Decimal("290.6"), btp=Decimal("193.8"),
                                  snbas=None, ksn=None, bbas=None, kh=None)
    picked = pick_specific_consumption_year_stepback([empty_2026, zeros_2025, filled_2024])
    assert picked is filled_2024
    assert pick_specific_consumption_for_fuel([empty_2026, zeros_2025, filled_2024]) is filled_2024


def test_fuel_lookup_keeps_empty_row_when_no_payload():
    empty_2026 = SimpleNamespace(year_number=2026, y=None, snk=None, sntp=None, bk=None, btp=None,
                                 snbas=None, ksn=None, bbas=None, kh=None)
    zeros_2025 = SimpleNamespace(year_number=2025, y=Decimal("0"), snk=None, sntp=Decimal("0"),
                                 bk=None, btp=Decimal("0"), snbas=None, ksn=None, bbas=None, kh=None)
    assert pick_specific_consumption_year_stepback([empty_2026, zeros_2025]) is None
    assert pick_specific_consumption_for_fuel([empty_2026, zeros_2025]) is empty_2026
    assert pick_specific_consumption_for_fuel([]) is None


def _row(year, **kwargs):
    base = dict(
        year_number=year,
        equipment_group_id=3121,
        k=None,
        y=None,
        snk=None,
        sntp=None,
        bk=None,
        btp=None,
        snbas=None,
        ksn=None,
        bbas=None,
        kh=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_inherit_snk_from_earlier_year_when_picked_row_has_other_payload():
    """3121: лишний 2026 с пустым snk не должен обнулять 13% из 2025."""
    row_2026 = _row(2026, y=Decimal("686.6"), bk=Decimal("290.6"))
    row_2025 = _row(2025, y=Decimal("686.6"), snk=Decimal("13"), bk=Decimal("290.6"))
    row_2024 = _row(2024, y=Decimal("686.6"), bk=Decimal("290.6"))
    picked = resolve_specific_consumption_for_fuel([row_2026, row_2025, row_2024])
    assert picked.year_number == 2026
    assert picked.snk == Decimal("13")
    assert picked.bk == Decimal("290.6")
    assert row_2026.snk is None


def test_inherit_does_not_replace_explicit_zero():
    row_2026 = _row(2026, snk=Decimal("0"), bk=Decimal("100"))
    row_2025 = _row(2025, snk=Decimal("13"), bk=Decimal("100"))
    picked = resolve_specific_consumption_for_fuel([row_2026, row_2025])
    assert picked is row_2026
    assert picked.snk == Decimal("0")


def test_inherit_skips_empty_year_then_uses_earlier_as_is():
    """Нет payload в 2026 — как Access без этой строки: берём 2025 целиком."""
    empty_2026 = _row(2026)
    row_2025 = _row(2025, snk=Decimal("13"), bk=None)
    picked = resolve_specific_consumption_for_fuel([empty_2026, row_2025])
    assert picked is row_2025
    assert picked.snk == Decimal("13")
    assert picked.bk is None


def test_access_seek_skips_empty_arm_year_in_window():
    """Липецк 268: пустой 2026 в АРМ, в Access строки нет — берём 2024."""
    old = _row(2021, bk=Decimal("400"))
    base = _row(2024, y=Decimal("599.65"), bk=Decimal("310"))
    empty_2026 = _row(2026)
    picked = pick_specific_consumption_access_seek(
        [old, base, empty_2026], byear=2024, cyear=2026
    )
    assert picked is base


def test_access_seek_explicit_cyear_payload_wins():
    base = _row(2024, y=Decimal("599.65"), bk=Decimal("310"))
    filled_2026 = _row(2026, y=Decimal("610"), bk=Decimal("310"))
    picked = pick_specific_consumption_access_seek(
        [base, filled_2026], byear=2024, cyear=2026
    )
    assert picked is filled_2026


def test_access_seek_empty_only_row_is_match():
    """УТЭЦ 1330: y=0, Bk Null — Access Match, не Bookmark предыдущей станции."""
    empty_2024 = _row(2024, y=Decimal("0"))
    picked = pick_specific_consumption_access_seek(
        [empty_2024], byear=2024, cyear=2026
    )
    assert picked is empty_2024
    assert picked.bk is None
    assert picked.y == Decimal("0")


def test_access_seek_none_without_rows_in_window():
    old = _row(2021, bk=Decimal("400"))
    assert (
        pick_specific_consumption_access_seek([old], byear=2024, cyear=2026) is None
    )
