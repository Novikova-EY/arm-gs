import re
from datetime import datetime
from wtforms.validators import ValidationError

def validate_year_or_date(form, field):
    """
    Разрешает ввод либо в формате YYYY (4 цифры),
    либо в формате DD.MM.YYYY (например, 31.12.2025).
    Год не может быть больше 2050.
    """
    value = field.data.strip() if field.data else ''
    
    if not value:
        return

    # 1. Проверяем, является ли введённое значение годом (4 цифры)
    if re.match(r'^\d{4}$', value):
        year = int(value)
        if year > 2050:
            raise ValidationError('Год не может быть больше 2050.')
        return

    # 2. Проверяем, соответствует ли значение формату DD.MM.YYYY
    try:
        date_obj = datetime.strptime(value, '%d.%m.%Y')
        if date_obj.year > 2050:
            raise ValidationError('Год в дате не может быть больше 2050.')
    except ValueError:
        raise ValidationError('Некорректный формат: введите год (ГГГГ) или дату (ДД.ММ.ГГГГ02).')
