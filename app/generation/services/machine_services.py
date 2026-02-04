def _coerce_decimal(val):
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        if isinstance(val, str):
            val = val.replace(",", ".")
        return Decimal(val)
    except (InvalidOperation, TypeError, ValueError):
        return None


def is_same_decimal(a, b):
    a_dec = _coerce_decimal(a)
    b_dec = _coerce_decimal(b)

    if a_dec is None and (b_dec is None or b_dec == 0):
        return True
    if b_dec is None and (a_dec is None or a_dec == 0):
        return True

    if a_dec is None or b_dec is None:
        return False

    return a_dec == b_dec
