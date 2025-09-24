import re
from datetime import datetime, date
from wtforms.validators import ValidationError

def validate_year_or_date(form, field):
    """
    Разрешает ввод:
    - 'YYYY'
    - 'DD.MM.YYYY'
    - 'YYYY-MM-DD'
    - или объект date/datetime (например, при process(obj=...))
    """
    value = field.data

    if not value:
        return  # Пусто — пропускаем

    # ✅ Если пришел объект date/datetime — просто проверим год
    if isinstance(value, (date, datetime)):
        if value.year > 2050:
            raise ValidationError('Год в дате не может быть больше 2050.')
        return

    # ✅ Если пришла строка
    value = value.strip()

    # YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        try:
            dt = datetime.strptime(value, '%Y-%m-%d')
            if dt.year > 2050:
                raise ValidationError('Год в дате не может быть больше 2050.')
            return
        except ValueError:
            raise ValidationError(f'Некорректная дата: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')

    # YYYY
    if re.match(r'^\d{4}$', value):
        year = int(value)
        if year > 2050:
            raise ValidationError('Год не может быть больше 2050.')
        return

    # DD.MM.YYYY
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', value):
        try:
            dt = datetime.strptime(value, '%d.%m.%Y')
            if dt.year > 2050:
                raise ValidationError('Год в дате не может быть больше 2050.')
            return
        except ValueError:
            raise ValidationError(f'Некорректная дата: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')

    # ❌ Все остальное — ошибка
    raise ValidationError(f'Некорректный формат: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')
