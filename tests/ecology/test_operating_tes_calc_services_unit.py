# -*- coding: utf-8 -*-
"""Юнит-тесты формул расчёта по действующим ТЭС."""

from decimal import Decimal

import pytest

from app.ecology.services.operating_tes_calc_services import (
    apply_capture,
    ash_motkh,
    co_motkh,
    to_natural_by_heat,
    equivalent_energy_billion_kwh,
    nox_motkh,
    pg_motkh,
    pg_tj_energy_and_mass,
    so2_motkh,
    specific_per_energy,
    specific_per_fuel,
    to_natural,
)
from app.ecology.services.operating_tes_fuel_input_services import match_ues_slug


DONETSK = {
    "ash": 25.8,
    "ash_share": 0.9,
    "q_mech": 2,
    "sulfur": 2.5,
    "sulfur_share": 0.1,
    "qh_kj": 18500,
    "bj": 5.6,
    "k_co2": 2.65,
    "tut_per_t": 0.876,
    "k_natural": 0.804,
}


def test_to_natural_uses_tut_per_t():
    assert to_natural(215670.83020545024, {"tut_per_t": 1.2}) == Decimal(
        "215670.83020545024"
    ) / Decimal("1.2")


@pytest.mark.parametrize("fuel,chars,expected", [
    ("100", {"qh_kcal": "3500", "k_natural": "9", "tut_per_t": "8"}, Decimal("200")),
    ("0", {"qh_kcal": "3500"}, Decimal("0")),
    (None, {"qh_kcal": "3500"}, None),
    ("100", {"qh_kcal": "0", "k_natural": "1"}, None),
    ("100", {"qh_kj": "14653.8", "k_natural": "1"}, None),
    ("100", None, None),
])
def test_to_natural_by_heat_uses_only_heat_in_kcal(fuel, chars, expected):
    assert to_natural_by_heat(fuel, chars) == expected


def test_ash_motkh_donetsk_matches_layout():
    bn = Decimal("3006.709049773756")
    got = ash_motkh(bn, DONETSK)
    assert got is not None
    assert abs(got - Decimal("732.1995")) < Decimal("0.5")


def test_so2_and_capture():
    bn = Decimal("3006.709049773756")
    motkh = so2_motkh(bn, DONETSK)
    emitted = apply_capture(motkh, Decimal("0.1"))
    assert motkh is not None
    assert emitted is not None
    assert emitted == motkh * Decimal("0.9")


@pytest.mark.parametrize("fuel,sulfur,share,expected", [
    ("200", "2.5", "0.1", Decimal("9")),
    ("200", "2.5", "0", Decimal("10")),
    ("200", "2.5", "1", Decimal("0")),
    ("200", "0", "0.1", Decimal("0")),
    ("0", "2.5", "0.1", Decimal("0")),
    (None, "2.5", "0.1", None),
])
def test_so2_formula_matches_sulfur_and_binding_share(fuel, sulfur, share, expected):
    assert so2_motkh(fuel, {"sulfur": sulfur, "sulfur_share": share}) == expected


@pytest.mark.parametrize("fuel,q3,r,qh,q4,expected", [
    ("200", "0.5", "0.8", "1013", "2", Decimal("0.0784")),
    ("200", "0.5", "0.8", "2026", "2", Decimal("0.1568")),
    ("200", "0.5", "0.8", "1013", "0", Decimal("0.08")),
    ("200", "0.5", "0.8", "1013", "100", Decimal("0")),
    ("200", "0", "0.8", "1013", "2", Decimal("0")),
    ("200", "0.5", "0", "1013", "2", Decimal("0")),
    ("200", "0.5", "0.8", "0", "2", Decimal("0")),
    ("0", "0.5", "0.8", "1013", "2", Decimal("0")),
    (None, "0.5", "0.8", "1013", "2", None),
])
def test_co_formula_matches_chemical_and_mechanical_heat_losses(fuel, q3, r, qh, q4, expected):
    assert co_motkh(fuel, {
        "q_chem": q3, "r_chem": r, "qh_kj": qh, "q_mech": q4,
    }) == expected


@pytest.mark.parametrize("fuel,q_mech,bj,expected", [
    ("100", "2", "5", Decimal("0.49")),
    ("100", "0", "5", Decimal("0.5")),
    ("100", "100", "5", Decimal("0")),
    ("100", "2", "0", Decimal("0")),
    ("0", "2", "5", Decimal("0")),
    (None, "2", "5", None),
])
def test_nox_formula_uses_conditional_fuel_and_mechanical_losses(fuel, q_mech, bj, expected):
    assert nox_motkh(fuel, {"q_mech": q_mech, "bj": bj}) == expected


def test_nox_without_n():
    # 0.001 * 1898.522 * (1-2/100) * 5.6 ≈ 10.42
    got = nox_motkh(Decimal("1898.522"), DONETSK)
    assert got is not None
    assert abs(got - Decimal("10.419")) < Decimal("0.02")


def test_pg_is_b_times_kco2():
    assert pg_motkh(Decimal("1898.522"), DONETSK) == Decimal("1898.522") * Decimal("2.65")


@pytest.mark.parametrize("fuel,tut_per_t,tj_per_kt,t_co2_per_tj,expected", [
    ("100", "0.5", "10", "20", (Decimal("2000"), Decimal("40"))),
    ("100", "0.25", "10", "20", (Decimal("4000"), Decimal("80"))),
    ("100", "0.5", "20", "20", (Decimal("4000"), Decimal("80"))),
    ("100", "0.5", "10", "40", (Decimal("2000"), Decimal("80"))),
    ("0", "0.5", "10", "20", (Decimal("0"), Decimal("0"))),
    ("100", "0.5", "0", "20", (Decimal("0"), Decimal("0"))),
    ("100", "0.5", "10", "0", (Decimal("2000"), Decimal("0"))),
    (None, "0.5", "10", "20", (None, None)),
    ("100", None, "10", "20", (None, None)),
    ("100", "0", "10", "20", (None, None)),
    ("100", "-1", "10", "20", (None, None)),
    ("100", "0.5", None, "20", (None, None)),
    ("100", "0.5", "10", None, (Decimal("2000"), None)),
])
def test_pg_tj_uses_inventory_coefficients_and_divides_mass_once(
    fuel, tut_per_t, tj_per_kt, t_co2_per_tj, expected,
):
    assert pg_tj_energy_and_mass(fuel, {
        "tut_per_t": tut_per_t, "tj_per_kt": tj_per_kt, "t_co2_per_tj": t_co2_per_tj,
        "k_natural": "999", "qh_kj": "999", "qh_kcal": "999", "ash": "99", "k_co2": "999",
    }) == expected


def test_equivalent_energy():
    # 684528.183 млн кВтч + 626188.74 тыс Гкал * 1.163 → млрд кВт·ч
    got = equivalent_energy_billion_kwh(Decimal("684528.1830318529"), Decimal("626188.7413237388"))
    assert got is not None
    assert abs(got - Decimal("1412.82")) < Decimal("0.05")


def test_specifics():
    assert specific_per_energy(Decimal("435.23"), Decimal("1412.82")) is not None
    assert specific_per_fuel(Decimal("435.23"), Decimal("292114.34")) is not None


def test_match_ues_slug():
    assert match_ues_slug("ОЭС Северо-Запада") == "severo-zapad"
    assert match_ues_slug("Центр") == "centr"
    assert match_ues_slug("Средняя Волга") == "srednyaya-volga"
    assert match_ues_slug("Сибирь") == "sibir"
    assert match_ues_slug("ТИТЭС Востока") is None
