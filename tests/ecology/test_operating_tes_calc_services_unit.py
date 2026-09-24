# -*- coding: utf-8 -*-
"""Юнит-тесты формул расчёта по действующим ТЭС."""

from decimal import Decimal

from app.ecology.services.operating_tes_calc_services import (
    apply_capture,
    ash_motkh,
    equivalent_energy_billion_kwh,
    nox_motkh,
    pg_motkh,
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


def test_to_natural_uses_k():
    assert to_natural(215670.83020545024, {"k_natural": 1.154, "tut_per_t": 1.2}) == Decimal(
        "215670.83020545024"
    ) / Decimal("1.154")


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


def test_nox_without_n():
    # 0.001 * 1898.522 * (1-2/100) * 5.6 ≈ 10.42
    got = nox_motkh(Decimal("1898.522"), DONETSK)
    assert got is not None
    assert abs(got - Decimal("10.419")) < Decimal("0.02")


def test_pg_is_b_times_kco2():
    assert pg_motkh(Decimal("1898.522"), DONETSK) == Decimal("1898.522") * Decimal("2.65")


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
