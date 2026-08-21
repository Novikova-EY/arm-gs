# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.station_ewtp import (
    apply_access_coeff_ewtp,
    fill_ewtp_if_empty,
    formula_ewtp,
    resolve_station_ewtp,
)


def test_formula_ewtp():
    assert formula_ewtp(Decimal("900"), Decimal("1646.774")) == Decimal("1482.0966")


def test_resolve_keeps_imported_ewtp_even_if_y_would_zero_it():
    fp = SimpleNamespace(ewtp=Decimal("1482.0966391152"), qotr=Decimal("900"))
    assert resolve_station_ewtp(fp, y=Decimal("0")) == Decimal("1482.0966391152")
    assert fill_ewtp_if_empty(fp, Decimal("0")) is False
    assert fp.ewtp == Decimal("1482.0966391152")


def test_resolve_fills_empty_from_formula():
    fp = SimpleNamespace(ewtp=None, qotr=Decimal("900"))
    assert resolve_station_ewtp(fp, y=Decimal("1646.774")) == Decimal("1482.0966")
    assert fill_ewtp_if_empty(fp, Decimal("1646.774")) is True
    assert fp.ewtp == Decimal("1482.0966")


def test_fill_skips_when_no_y_and_empty():
    fp = SimpleNamespace(ewtp=None, qotr=Decimal("900"))
    assert fill_ewtp_if_empty(fp, None) is False
    assert fp.ewtp is None


def test_coeff_always_overwrites_ewtp_like_access_button5():
    fp = SimpleNamespace(ewtp=Decimal("10"), qotr=Decimal("900"))
    assert apply_access_coeff_ewtp(fp, Decimal("1646.774")) is True
    assert fp.ewtp == Decimal("1482.0966")
