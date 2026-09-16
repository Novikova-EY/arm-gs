# -*- coding: utf-8 -*-
"""Формулы макета «Расчет по действующим ТЭС (перевод в натур через К)»."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.ecology.services.ecology_decimal_helpers import decimal_or_none as _d

Q_H_DIVISOR = Decimal("32680")
CO_QH_DIVISOR = Decimal("1013")
KCAL_PER_KJ = Decimal("4.1868")


def conversion_k(chars: Mapping[str, Any] | None) -> Decimal | None:
    """K перевода тут → натур. Если нет K, берём тут/тн."""
    if not chars:
        return None
    k = _d(chars.get("k_natural"))
    if k is not None and k != 0:
        return k
    tut = _d(chars.get("tut_per_t"))
    if tut is not None and tut != 0:
        return tut
    return None


def to_natural(b_tce: Any, chars: Mapping[str, Any] | None) -> Decimal | None:
    """Вн = В / K."""
    b = _d(b_tce)
    k = conversion_k(chars)
    if b is None or k is None or k == 0:
        return None
    return b / k


def ash_motkh(bn: Any, chars: Mapping[str, Any] | None) -> Decimal | None:
    """Мотх золы = 0,01·Вн·(аун·Ар + qч·QH/32680)."""
    bn_d = _d(bn)
    if bn_d is None or not chars:
        return None
    aun = _d(chars.get("ash_share")) or Decimal("0")
    ap = _d(chars.get("ash")) or Decimal("0")
    qch = _d(chars.get("q_mech")) or Decimal("0")
    qh = _d(chars.get("qh_kj")) or Decimal("0")
    inner = aun * ap + qch * qh / Q_H_DIVISOR
    return Decimal("0.01") * bn_d * inner


def so2_motkh(bn: Any, chars: Mapping[str, Any] | None) -> Decimal | None:
    """Мотх SO2 = 0,02·Вн·Sp·(1 − x)."""
    bn_d = _d(bn)
    if bn_d is None or not chars:
        return None
    sp = _d(chars.get("sulfur")) or Decimal("0")
    x = _d(chars.get("sulfur_share")) or Decimal("0")
    return Decimal("0.02") * bn_d * sp * (Decimal("1") - x)


def nox_motkh(b_tce: Any, chars: Mapping[str, Any] | None) -> Decimal | None:
    """Мотх NOx без n: 0,001·В·(1 − qч/100)·bj."""
    b = _d(b_tce)
    if b is None or not chars:
        return None
    qch = _d(chars.get("q_mech")) or Decimal("0")
    bj = _d(chars.get("bj")) or Decimal("0")
    return Decimal("0.001") * b * (Decimal("1") - qch / Decimal("100")) * bj


def co_motkh(bn: Any, chars: Mapping[str, Any] | None) -> Decimal | None:
    """Мотх CO, т: 0,001·Вн·(q3·R·QH/1013)·(1 − qч/100)."""
    bn_d = _d(bn)
    if bn_d is None or not chars:
        return None
    q3 = _d(chars.get("q_chem")) or Decimal("0")
    r = _d(chars.get("r_chem")) or Decimal("0")
    qh = _d(chars.get("qh_kj")) or Decimal("0")
    qch = _d(chars.get("q_mech")) or Decimal("0")
    return (
        Decimal("0.001")
        * bn_d
        * (q3 * r * qh / CO_QH_DIVISOR)
        * (Decimal("1") - qch / Decimal("100"))
    )


def pg_motkh(b_tce: Any, chars: Mapping[str, Any] | None) -> Decimal | None:
    """Мотх CO2 = В·KCO2, тыс. т."""
    b = _d(b_tce)
    if b is None or not chars:
        return None
    k = _d(chars.get("k_co2"))
    if k is None:
        return None
    return b * k


def pg_tj_energy_and_mass(
    bn: Any, chars: Mapping[str, Any] | None
) -> tuple[Decimal | None, Decimal | None]:
    """Энергия, ТДж, и масса CO2, млн т, по тепловому коэффициенту."""
    bn_d = _d(bn)
    if bn_d is None or not chars:
        return None, None
    tj_per_kt = _d(chars.get("tj_per_kt"))
    if tj_per_kt is None:
        qh = _d(chars.get("qh_kj"))
        tj_per_kt = (qh / Decimal("1000")) if qh is not None else None
    t_per_tj = _d(chars.get("t_co2_per_tj"))
    if tj_per_kt is None:
        return None, None
    energy_tj = bn_d * tj_per_kt / Decimal("1000")
    if t_per_tj is None:
        return energy_tj, None
    mass_mln_t = energy_tj * t_per_tj / Decimal("1000")
    return energy_tj, mass_mln_t


def apply_capture(motkh: Any, eta: Any) -> Decimal | None:
    """Мвыб = Мотх·(1 − η)."""
    m = _d(motkh)
    if m is None:
        return None
    e = _d(eta) or Decimal("0")
    return m * (Decimal("1") - e)


def equivalent_energy_billion_kwh(e_mln_kwh: Any, q_ths_gcal: Any) -> Decimal | None:
    """Приведённая энергия, млрд кВт·ч = (E + Q·1,163) / 1000."""
    e = _d(e_mln_kwh)
    q = _d(q_ths_gcal)
    if e is None and q is None:
        return None
    e = e or Decimal("0")
    q = q or Decimal("0")
    from app.ecology.services.operating_tes_constants import GCAL_TO_MWH

    return (e + q * GCAL_TO_MWH) / Decimal("1000")


def specific_per_energy(mass: Any, energy_bln_kwh: Any) -> Decimal | None:
    """г/кВт·ч: тыс. т / млрд кВт·ч."""
    m = _d(mass)
    e = _d(energy_bln_kwh)
    if m is None or e is None or e == 0:
        return None
    return m / e


def specific_per_fuel(mass: Any, b_tce: Any) -> Decimal | None:
    """кг/тут = тыс. т / тыс. тут · 1000."""
    m = _d(mass)
    b = _d(b_tce)
    if m is None or b is None or b == 0:
        return None
    return m / b * Decimal("1000")


def qh_kcal_from_kj(qh_kj: Any) -> Decimal | None:
    qh = _d(qh_kj)
    if qh is None:
        return None
    return qh / KCAL_PER_KJ
