def comma_decimal(value):
    if value is None:
        return ''
    try:
        return str(value).replace('.', ',')
    except Exception:
        return value
