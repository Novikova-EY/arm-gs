import re
from datetime import datetime
from wtforms.validators import ValidationError

def validate_year_or_date(form, field):
    """
    Разрешает ввод в следующих форматах:
    - YYYY (год, 4 цифры) → 2025
    - DD.MM.YYYY (обычный формат) → 14.10.2022
    - YYYY-MM-DD (ISO 8601) → 2022-10-14 (НЕ вызывает ошибку)
    
    Год не может быть больше 2050.
    """
    value = (field.data or '').strip()  # Убираем пробелы, обрабатываем None

    if not value:
        return  # Пустое поле — пропускаем валидацию

    # 1️⃣ Проверяем формат YYYY-MM-DD (ISO 8601) ✅
    if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        try:
            date_obj = datetime.strptime(value, '%Y-%m-%d')
            if date_obj.year > 2050:
                raise ValidationError('Год в дате не может быть больше 2050.')
            return  # Всё ОК
        except ValueError:
            raise ValidationError(f'Некорректная дата {value}. Используйте YYYY или DD.MM.YYYY.')

    # 2️⃣ Проверяем, является ли это просто годом (YYYY) ✅
    if re.match(r'^\d{4}$', value):
        year = int(value)
        if year > 2050:
            raise ValidationError('Год не может быть больше 2050.')
        return  # Всё ОК

    # 3️⃣ Проверяем формат DD.MM.YYYY ✅
    if re.match(r'^\d{2}\.\d{2}\.\d{4}$', value):
        try:
            date_obj = datetime.strptime(value, '%d.%m.%Y')
            if date_obj.year > 2050:
                raise ValidationError('Год в дате не может быть больше 2050.')
            return  # Всё ОК
        except ValueError:
            raise ValidationError(f'Некорректная дата {value}. Используйте YYYY или DD.MM.YYYY.')

    # 4️⃣ Если ничего не подошло → ошибка ❌
    raise ValidationError(f'Некорректный формат даты: {value}. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.')
