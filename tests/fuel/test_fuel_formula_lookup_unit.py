# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.fuel.services.calculation.fuel_formula_lookup import pick_fuel_formula_access_seek


def _row(year, formtxt="gaz"):
    return SimpleNamespace(year_number=year, formtxt=formtxt)


def test_formula_seek_uses_last_year_in_byear_cyear_window():
    report_2021 = _row(2021)
    base_2024 = _row(2024, formtxt="gaz=100")
    change_2028 = _row(2028, formtxt="mazut=10;gaz")
    picked = pick_fuel_formula_access_seek(
        [report_2021, base_2024, change_2028], byear=2024, cyear=2026
    )
    assert picked is base_2024


def test_formula_seek_none_without_rows_in_window():
    report_2021 = _row(2021)
    assert pick_fuel_formula_access_seek([report_2021], byear=2024, cyear=2026) is None


def test_formula_seek_empty_formtxt_in_window_is_match():
    empty_2024 = _row(2024, formtxt="")
    picked = pick_fuel_formula_access_seek([empty_2024], byear=2024, cyear=2026)
    assert picked is empty_2024
