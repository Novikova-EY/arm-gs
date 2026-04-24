# -*- coding: utf-8 -*-
"""
Расчет полей _calc для EquipmentGroupSpecificFuelConsumption.
param — EquipmentGroupFuelParam (ewtp, qotr, ved и т.д.).
"""
from decimal import Decimal

D0 = Decimal("0")
D1 = Decimal("1")
D100 = Decimal("100")
D1000 = Decimal("1000")


def z(value):
    """
    Возвращает value как Decimal или D0, если None.
    Для сравнений (ved > 1) и для арифметики (eurt, coeff_k).
    """
    if value is None:
        return D0
    try:
        return Decimal(str(value))
    except Exception:
        return D0


def is_positive(value) -> bool:
    """Проверяет, что значение положительное (> 0)."""
    if value is None:
        return False
    try:
        d = Decimal(str(value))
        return d > 0
    except Exception:
        return False


def safe_div(a, b, default=None):
    """Безопасное деление a/b. При b=0 или не positive возвращает default (D0 по умолчанию)."""
    if not is_positive(b):
        return default if default is not None else D0
    if a is None:
        return default if default is not None else D0
    try:
        da = Decimal(str(a))
        db = Decimal(str(b))
        return da / db
    except Exception:
        return default if default is not None else D0


def calc_y_calc(param) -> Decimal:
    """
    Удельная выработка эл.эн. на тепловом потреблении (расчет).
    param — EquipmentGroupFuelParam (ved, qotr, ewtp).
    """
    if param is None:
        return D0
    if z(getattr(param, "ved", None)) > 1:
        if is_positive(getattr(param, "qotr", None)):
            return safe_div(
                getattr(param, "ewtp", None),
                getattr(param, "qotr", None),
                default=D0,
            ) * D1000
    return D0


def calc_btp_calc(param, coeff_k) -> Decimal:
    """
    Удельный расход усл.топлива на отпуск эл.эн. в теплофик.режиме (расчет).
    param — EquipmentGroupFuelParam (ved, ewtp, e, eurt).
    coeff_k — consumption.k (коэффициент экономии от теплофикации, привязан к году).
    """
    if param is None:
        return D0
    if z(getattr(param, "ved", None)) > 1 and is_positive(getattr(param, "ewtp", None)):
        e_val = getattr(param, "e", None)
        ewtp_val = getattr(param, "ewtp", None)
        if z(e_val) != z(ewtp_val):
            if z(e_val) == 0:
                return D0
            return (
                z(getattr(param, "eurt", None))
                - z(coeff_k) * (D1 - safe_div(ewtp_val, e_val, default=D0)) * D100
            )
        return z(getattr(param, "eurt", None))
    return D0


def calc_sntp_calc(param) -> Decimal:
    """
    Эл.энергия на собственные нужды в теплофикационном режиме (расчет).
    param — EquipmentGroupFuelParam (ved, ewtp, eotp, e, snk).
    """
    if param is None:
        return D0
    if z(getattr(param, "ved", None)) > 1 and is_positive(getattr(param, "ewtp", None)):
        numerator = (
            z(getattr(param, "eotp", None))
            - (z(getattr(param, "e", None)) - z(getattr(param, "ewtp", None)))
            * (D1 - z(getattr(param, "snk", None)) / D100)
        )
        return safe_div(numerator, getattr(param, "ewtp", None))
    return D0


def calc_bk_calc(param, btp_calc, sntp_calc) -> Decimal:
    """
    Удельный расход усл.топлива на отпуск эл.эн. в конд.режиме (расчет).
    Зависит от уже посчитанных btp_calc и sntp_calc.
    param — EquipmentGroupFuelParam (ved, ewtp, e, eust, snk, eurt).
    """
    if param is None:
        return D0
    ved = z(getattr(param, "ved", None))
    if ved > 1 and ved < 4 and is_positive(getattr(param, "ewtp", None)):
        e_val = getattr(param, "e", None)
        ewtp_val = getattr(param, "ewtp", None)
        if z(e_val) > z(ewtp_val):
            denominator = (
                (z(e_val) - z(ewtp_val))
                * (D1 - z(getattr(param, "snk", None)) / D100)
            )
            if denominator == 0:
                return D0
            numerator = (
                z(getattr(param, "eust", None))
                - z(ewtp_val) * z(sntp_calc) * z(btp_calc) / D1000
            )
            return numerator / denominator * D1000
        return z(btp_calc)
    return z(getattr(param, "eurt", None))
